from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time

from app.ai.question_generator import QuestionCandidate, SpendingQuestionGenerator
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
from app.schemas.feedback import (
    FeedbackQuestionContent,
    FeedbackTransactionSnapshot,
    ScoreScale,
)
from app.schemas.onboarding import (
    FirstInsightResponse,
    FirstInsightSupportingData,
    OnboardingProgressResponse,
    OnboardingQuestionItem,
    OnboardingQuestionsResponse,
    OnboardingTransactionItem,
    SubmitOnboardingFeedbackRequest,
    SubmitOnboardingFeedbackResponse,
    TransactionsToLabelResponse,
)
from app.services.spending_summary import build_happy_archive, build_top_happy_consumption

REQUIRED_ONBOARDING_LABEL_COUNT = 5
MIN_ONBOARDING_QUESTION_COUNT = 5
MAX_ONBOARDING_QUESTION_COUNT = 10
CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


class OnboardingService:
    def __init__(
        self,
        transaction_repo: TransactionRepository,
        user_repo: UserRepository,
        question_generator: SpendingQuestionGenerator | None = None,
        today: date | None = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.user_repo = user_repo
        self.question_generator = question_generator or SpendingQuestionGenerator()
        self.today = today

    async def get_questions(
        self,
        user: User,
        limit: int = MAX_ONBOARDING_QUESTION_COUNT,
    ) -> OnboardingQuestionsResponse:
        normalized_limit = min(max(limit, MIN_ONBOARDING_QUESTION_COUNT), MAX_ONBOARDING_QUESTION_COUNT)
        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        since = self.start_of_day(self.subtract_months(self.today or datetime.now(UTC).date(), 3))
        recent_transactions = await self.transaction_repo.list_unlabeled_for_onboarding(user.id, 100, since=since)
        transactions = recent_transactions[:normalized_limit]
        merchant_counts = Counter(transaction.merchant for transaction in recent_transactions)

        await self.sync_onboarding_status(user, labeled_count=labeled_count)
        candidates = [
            self.to_question_candidate(
                transaction=transaction,
                reason=self.resolve_selection_reason(transaction, merchant_counts[transaction.merchant]),
                merchant_count=merchant_counts[transaction.merchant],
            )
            for transaction in transactions
        ]
        generated_questions = await self.question_generator.generate(candidates)

        return OnboardingQuestionsResponse(
            labeled_count=labeled_count,
            required_count=REQUIRED_ONBOARDING_LABEL_COUNT,
            question_count=len(generated_questions),
            min_question_count=MIN_ONBOARDING_QUESTION_COUNT,
            max_question_count=MAX_ONBOARDING_QUESTION_COUNT,
            questions=[
                self.to_question_item(transaction, generated_question, merchant_counts[transaction.merchant])
                for transaction, generated_question in zip(transactions, generated_questions, strict=True)
            ],
        )

    async def get_transactions_to_label(self, user: User, limit: int = 10) -> TransactionsToLabelResponse:
        normalized_limit = min(max(limit, 1), 30)
        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        since = self.start_of_day(self.subtract_months(self.today or datetime.now(UTC).date(), 3))
        transactions = await self.transaction_repo.list_unlabeled_for_onboarding(user.id, normalized_limit, since=since)
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

    async def submit_feedback(
        self,
        user: User,
        request: SubmitOnboardingFeedbackRequest,
    ) -> SubmitOnboardingFeedbackResponse:
        completed_at = datetime.now(UTC)
        for answer in request.answers:
            transaction = await self.transaction_repo.find_by_id(user.id, answer.transaction_id)
            if transaction is None:
                raise AppException(ErrorCode.NOT_FOUND, 404, "온보딩 답변 대상 거래를 찾을 수 없습니다")

            transaction.satisfaction_score = answer.score
            transaction.satisfaction_text = answer.text
            transaction.labeled_at = completed_at
            await self.transaction_repo.save(transaction)

        labeled_count = await self.transaction_repo.count_labeled_by_user(user.id)
        first_insight = None
        if labeled_count >= REQUIRED_ONBOARDING_LABEL_COUNT:
            first_insight = await self.create_first_insight(user)
        else:
            await self.sync_onboarding_status(user, labeled_count=labeled_count)

        labeled_transactions = await self.transaction_repo.list_labeled_for_insight(user.id)
        return SubmitOnboardingFeedbackResponse(
            labeled_count=labeled_count,
            required_count=REQUIRED_ONBOARDING_LABEL_COUNT,
            is_chatbot_unlocked=labeled_count >= REQUIRED_ONBOARDING_LABEL_COUNT,
            chatbot_context_ready=labeled_count >= REQUIRED_ONBOARDING_LABEL_COUNT,
            first_insight=first_insight,
            top_happy_consumption=build_top_happy_consumption(labeled_transactions, nickname=user.nickname),
            happy_purchase_archive=build_happy_archive(labeled_transactions, limit=10),
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

    @classmethod
    def to_question_item(
        cls,
        transaction: Transaction,
        generated_question,
        merchant_count: int,
    ) -> OnboardingQuestionItem:
        reason = cls.resolve_selection_reason(transaction, merchant_count)
        return OnboardingQuestionItem(
            question_id=generated_question.question_id,
            transaction=FeedbackTransactionSnapshot(
                transaction_id=transaction.id,
                amount=transaction.amount,
                merchant=transaction.merchant,
                category=Category(transaction.category),
                occurred_at=transaction.occurred_at,
            ),
            selection_reason=reason,
            pattern_summary=generated_question.pattern_summary,
            question=FeedbackQuestionContent(
                title=generated_question.title,
                body=generated_question.body,
                score_scale=ScoreScale(
                    min_label=generated_question.min_label,
                    max_label=generated_question.max_label,
                ),
            ),
        )

    @classmethod
    def to_question_candidate(
        cls,
        transaction: Transaction,
        reason: OnboardingSelectionReason,
        merchant_count: int,
    ) -> QuestionCandidate:
        return QuestionCandidate(
            question_id=f"oq_{transaction.id}",
            amount=transaction.amount,
            merchant=transaction.merchant,
            category=transaction.category,
            occurred_at=transaction.occurred_at.isoformat(),
            selection_reason=reason.value,
            merchant_count=merchant_count,
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

    @staticmethod
    def start_of_day(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    @staticmethod
    def subtract_months(value: date, months: int) -> date:
        month_index = value.month - months
        year = value.year
        while month_index <= 0:
            month_index += 12
            year -= 1

        last_day = OnboardingService.last_day_of_month(year, month_index)
        return value.replace(year=year, month=month_index, day=min(value.day, last_day))

    @staticmethod
    def last_day_of_month(year: int, month: int) -> int:
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return next_month.toordinal() - date(year, month, 1).toordinal()
