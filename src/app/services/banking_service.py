from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from secrets import token_urlsafe
from urllib.parse import urlencode

from app.ai.classifier import TransactionCategoryClassifier
from app.core.config import Settings, get_settings
from app.core.exceptions import AppException, ErrorCode
from app.models.transaction import Transaction, create_transaction_id
from app.models.user import User
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.banking import (
    BankingSyncResponse,
    LinkedAccountResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
)


@dataclass(frozen=True)
class MockBankingTransaction:
    external_id: str
    amount: int
    merchant: str
    merchant_mcc: str | None
    occurred_at: datetime


class BankingService:
    def __init__(
        self,
        transaction_repo: TransactionRepository,
        user_repo: UserRepository | None = None,
        classifier: TransactionCategoryClassifier | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.user_repo = user_repo
        self.classifier = classifier or TransactionCategoryClassifier()
        self.settings = settings or get_settings()

    def start_oauth(self, provider: str) -> OAuthStartResponse:
        if provider != "OPEN_BANKING_KR":
            raise AppException(ErrorCode.INVALID_INPUT, 400, "지원하지 않는 금융 연동 제공자입니다")

        state_token = f"state_{token_urlsafe(16)}"
        query = urlencode(
            {
                "client_id": self.settings.open_banking_client_id or "mock-client",
                "redirect_uri": self.settings.open_banking_redirect_uri,
                "response_type": "code",
                "state": state_token,
            }
        )
        return OAuthStartResponse(
            auth_url=f"https://mock.openbanking.local/oauth/authorize?{query}",
            state_token=state_token,
        )

    def handle_callback(self, code: str, state_token: str) -> OAuthCallbackResponse:
        if not code or not state_token:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "오픈뱅킹 인증 정보가 올바르지 않습니다")

        return OAuthCallbackResponse(
            linked_accounts=[
                LinkedAccountResponse(
                    account_id="a_mock_primary",
                    bank_name="신한은행",
                    masked_number="****-1234",
                )
            ]
        )

    async def sync_transactions(self, user: User, from_date: date, to_date: date) -> BankingSyncResponse:
        if from_date > to_date:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "조회 시작일은 종료일보다 늦을 수 없습니다")

        mock_transactions = self.create_mock_transactions(user.id, from_date, to_date)
        new_transactions: list[Transaction] = []

        for mock_transaction in mock_transactions:
            existing_transaction = await self.transaction_repo.find_by_external_id(mock_transaction.external_id)
            if existing_transaction is not None:
                continue

            classification = await self.classifier.classify(
                merchant=mock_transaction.merchant,
                merchant_mcc=mock_transaction.merchant_mcc,
                amount=mock_transaction.amount,
            )
            new_transactions.append(
                Transaction(
                    id=create_transaction_id(),
                    user_id=user.id,
                    external_id=mock_transaction.external_id,
                    account_id="a_mock_primary",
                    amount=mock_transaction.amount,
                    merchant=mock_transaction.merchant,
                    merchant_mcc=mock_transaction.merchant_mcc,
                    category=classification.category.value,
                    category_confidence=classification.confidence,
                    occurred_at=mock_transaction.occurred_at,
                )
            )

        if new_transactions:
            await self.transaction_repo.create_many(new_transactions)
            if self.user_repo is not None and user.onboarding_status == "NEEDS_BANK_LINK":
                from app.core.enums import OnboardingStatus

                await self.user_repo.update_onboarding_status(user, OnboardingStatus.NEEDS_LABELING)

        return BankingSyncResponse(
            synced_count=len(mock_transactions),
            new_count=len(new_transactions),
            sync_id=f"s_{token_urlsafe(12)}",
        )

    @staticmethod
    def create_mock_transactions(user_id: str, from_date: date, to_date: date) -> list[MockBankingTransaction]:
        base_date = min(max(from_date, date(2026, 4, 20)), to_date)
        mock_items = [
            ("스타벅스 강남점", 5814, 6500, "5814", 9),
            ("유니클로", 5651, 89000, "5651", 12),
            ("서울교통공사", 4111, 1450, "4111", 18),
            ("배달의민족", 5812, 23000, "5812", 21),
            ("온라인 강의", 8299, 120000, "8299", 14),
        ]

        transactions = []
        for merchant, mcc_seed, amount, merchant_mcc, hour in mock_items:
            occurred_at = datetime.combine(base_date, time(hour=hour), tzinfo=UTC)
            transactions.append(
                MockBankingTransaction(
                    external_id=f"mock_{user_id}_{base_date.isoformat()}_{mcc_seed}",
                    amount=amount,
                    merchant=merchant,
                    merchant_mcc=merchant_mcc,
                    occurred_at=occurred_at,
                )
            )
        return transactions
