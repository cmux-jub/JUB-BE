from collections import Counter, defaultdict

from app.core.enums import (
    Category,
    OnboardingNextStep,
    OnboardingSelectionReason,
    OnboardingStatus,
)
from app.core.exceptions import AppException, ErrorCode
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.onboarding import (
    FirstInsightResponse,
    FirstInsightSupportingData,
    OnboardingProgressResponse,
    OnboardingTransactionItem,
    TransactionsToLabelResponse,
)

REQUIRED_ONBOARDING_LABEL_COUNT = 5
CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


class OnboardingService:
    def __init__(self, transaction_repo: TransactionRepository, user_repo: UserRepository) -> None:
        self.transaction_repo = transaction_repo
        self.user_repo = user_repo

    async def get_transactions_to_label(self, user: User, limit: int = 10) -> TransactionsToLabelResponse:
        normalized_limit = min(max(limit, 1), 30)
        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        transactions = await self.transaction_repo.list_unlabeled_for_onboarding(user.id, normalized_limit)
        merchant_counts = Counter(transaction.merchant for transaction in transactions)

        await self.sync_onboarding_status(user, labeled_count=labeled_count)

        return TransactionsToLabelResponse(
            labeled_count=labeled_count,
            required_count=REQUIRED_ONBOARDING_LABEL_COUNT,
            transactions=[
                self.to_onboarding_item(transaction, merchant_counts[transaction.merchant])
                for transaction in transactions
            ],
        )

    async def get_progress(self, user: User) -> OnboardingProgressResponse:
        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        total_count = await self.transaction_repo.count_by_user(user.id)
        status = await self.resolve_status(user, labeled_count=labeled_count, total_count=total_count)
        next_step = self.resolve_next_step(status=status, labeled_count=labeled_count)

        return OnboardingProgressResponse(
            labeled_count=labeled_count,
            required_count=REQUIRED_ONBOARDING_LABEL_COUNT,
            is_chatbot_unlocked=labeled_count >= REQUIRED_ONBOARDING_LABEL_COUNT,
            next_step=next_step,
        )

    async def create_first_insight(self, user: User) -> FirstInsightResponse:
        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        if labeled_count < REQUIRED_ONBOARDING_LABEL_COUNT:
            raise AppException(ErrorCode.LABELING_REQUIRED, 409, "5개 이상 라벨링이 필요합니다")

        labeled_transactions = await self.transaction_repo.list_labeled_for_insight(user.id)
        if not labeled_transactions:
            raise AppException(ErrorCode.LABELING_REQUIRED, 409, "인사이트를 만들 라벨 데이터가 부족합니다")

        category, avg_score, count = self.find_best_category(labeled_transactions)
        await self.user_repo.update_onboarding_status(user, OnboardingStatus.READY)
        category_label = CATEGORY_LABELS[category]

        return FirstInsightResponse(
            headline=f"당신은 {category_label}에 쓸 때 만족도가 높네요",
            supporting_data=FirstInsightSupportingData(
                category=category_label,
                avg_score=round(avg_score, 1),
                count=count,
            ),
        )

    async def sync_onboarding_status(self, user: User, labeled_count: int) -> None:
        total_count = await self.transaction_repo.count_by_user(user.id)
        await self.resolve_status(user, labeled_count=labeled_count, total_count=total_count)

    async def resolve_status(self, user: User, labeled_count: int, total_count: int) -> OnboardingStatus:
        if total_count == 0:
            next_status = OnboardingStatus.NEEDS_BANK_LINK
        elif labeled_count < REQUIRED_ONBOARDING_LABEL_COUNT:
            next_status = OnboardingStatus.NEEDS_LABELING
        else:
            next_status = OnboardingStatus.READY

        if user.onboarding_status != next_status.value:
            await self.user_repo.update_onboarding_status(user, next_status)

        return next_status

    @staticmethod
    def resolve_next_step(status: OnboardingStatus, labeled_count: int) -> OnboardingNextStep:
        if status == OnboardingStatus.NEEDS_BANK_LINK:
            return OnboardingNextStep.LINK_BANK
        if labeled_count < REQUIRED_ONBOARDING_LABEL_COUNT:
            return OnboardingNextStep.LABEL_MORE
        if status == OnboardingStatus.READY:
            return OnboardingNextStep.READY
        return OnboardingNextStep.CREATE_FIRST_INSIGHT

    @classmethod
    def to_onboarding_item(cls, transaction: Transaction, merchant_count: int) -> OnboardingTransactionItem:
        category = Category(transaction.category)
        reason = cls.resolve_selection_reason(transaction, merchant_count)
        return OnboardingTransactionItem(
            transaction_id=transaction.id,
            amount=transaction.amount,
            merchant=transaction.merchant,
            category=category,
            occurred_at=transaction.occurred_at,
            selection_reason=reason,
            question=cls.build_question(transaction, category),
        )

    @staticmethod
    def resolve_selection_reason(transaction: Transaction, merchant_count: int) -> OnboardingSelectionReason:
        if transaction.category_confidence < 0.7:
            return OnboardingSelectionReason.HIGH_UNCERTAINTY
        if merchant_count >= 2:
            return OnboardingSelectionReason.REPEATED_PURCHASE
        if transaction.occurred_at.hour >= 21:
            return OnboardingSelectionReason.UNUSUAL_PATTERN
        return OnboardingSelectionReason.LARGE_AMOUNT

    @staticmethod
    def build_question(transaction: Transaction, category: Category) -> str:
        formatted_amount = f"{transaction.amount:,}"
        if category == Category.LASTING:
            return f"이 {formatted_amount}원의 {transaction.merchant}, 지금 봐도 만족스러우세요?"
        if category == Category.IMMEDIATE:
            return f"이 {transaction.merchant} 소비, 다시 보면 만족도가 어떠세요?"
        return f"이 {formatted_amount}원의 필수 지출, 당시 기준으로 부담은 적절했나요?"

    @staticmethod
    def find_best_category(transactions: list[Transaction]) -> tuple[Category, float, int]:
        scores_by_category: dict[Category, list[int]] = defaultdict(list)
        for transaction in transactions:
            if transaction.satisfaction_score is None:
                continue
            scores_by_category[Category(transaction.category)].append(transaction.satisfaction_score)

        best_category = max(
            scores_by_category,
            key=lambda category: (
                sum(scores_by_category[category]) / len(scores_by_category[category]),
                len(scores_by_category[category]),
            ),
        )
        scores = scores_by_category[best_category]
        return best_category, sum(scores) / len(scores), len(scores)
