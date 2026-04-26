from datetime import date

import pytest

from app.ai.classifier import CategoryClassification
from app.core.enums import Category
from app.models.user import User
from app.services.banking_service import BankingService


class FakeTransactionRepository:
    def __init__(self):
        self.transactions_by_external_id = {}

    async def find_by_external_id(self, external_id: str):
        return self.transactions_by_external_id.get(external_id)

    async def create_many(self, transactions):
        for transaction in transactions:
            self.transactions_by_external_id[transaction.external_id] = transaction
        return transactions


class FakeClassifier:
    async def classify(self, merchant: str, merchant_mcc: str | None = None, amount: int | None = None):
        return CategoryClassification(Category.IMMEDIATE, 0.8)


def create_user() -> User:
    return User(id="u_test", email="user@example.com", hashed_password="hashed", nickname="tester", birth_year=1998)


def test_start_oauth_returns_mock_authorization_url():
    service = BankingService(FakeTransactionRepository(), classifier=FakeClassifier())

    result = service.start_oauth("OPEN_BANKING_KR")

    assert result.auth_url.startswith("https://mock.openbanking.local/oauth/authorize")
    assert result.state_token.startswith("state_")


def test_handle_callback_returns_mock_account():
    service = BankingService(FakeTransactionRepository(), classifier=FakeClassifier())

    result = service.handle_callback("code", "state")

    assert result.linked_accounts[0].account_id == "a_mock_primary"


@pytest.mark.asyncio
async def test_sync_transactions_creates_mock_transactions_once():
    repo = FakeTransactionRepository()
    service = BankingService(repo, classifier=FakeClassifier())

    first_result = await service.sync_transactions(create_user(), date(2026, 4, 20), date(2026, 4, 26))
    second_result = await service.sync_transactions(create_user(), date(2026, 4, 20), date(2026, 4, 26))

    assert first_result.synced_count == 5
    assert first_result.new_count == 5
    assert second_result.synced_count == 5
    assert second_result.new_count == 0
