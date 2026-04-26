from collections import defaultdict

from app.core.enums import Category
from app.models.transaction import Transaction
from app.schemas.feedback import HappyArchiveItem, SpendingComparison, TopHappyConsumption

CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


def build_spending_comparison(current_amount: int, previous_amount: int) -> SpendingComparison:
    difference_amount = current_amount - previous_amount
    difference_percent = None
    if previous_amount > 0:
        difference_percent = round((difference_amount / previous_amount) * 100, 1)

    return SpendingComparison(
        current_amount=current_amount,
        previous_amount=previous_amount,
        difference_amount=difference_amount,
        difference_percent=difference_percent,
        difference_display=format_signed_amount(difference_amount),
        difference_percent_display=format_signed_percent(difference_percent),
        saved_amount=max(previous_amount - current_amount, 0),
    )


def format_signed_amount(value: int) -> str:
    return f"{value:+d}" if value != 0 else "0"


def format_signed_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.1f}%" if value != 0 else "0.0%"


def build_happy_archive(transactions: list[Transaction], limit: int | None = None) -> list[HappyArchiveItem]:
    happy_transactions = [
        transaction
        for transaction in transactions
        if transaction.satisfaction_score is not None and transaction.satisfaction_score >= 4
    ]
    related_total_by_category: dict[Category, int] = defaultdict(int)
    for transaction in happy_transactions:
        related_total_by_category[Category(transaction.category)] += transaction.amount

    archive = [
        HappyArchiveItem(
            transaction_id=transaction.id,
            amount=transaction.amount,
            related_total_amount=related_total_by_category[Category(transaction.category)],
            merchant=transaction.merchant,
            category=Category(transaction.category),
            occurred_at=transaction.occurred_at,
            score=transaction.satisfaction_score or 0,
            text=transaction.satisfaction_text,
        )
        for transaction in happy_transactions
    ]
    archive.sort(key=lambda item: (item.score, item.occurred_at), reverse=True)
    if limit is None:
        return archive
    return archive[:limit]


def build_top_happy_consumption(transactions: list[Transaction], nickname: str | None = None) -> TopHappyConsumption:
    scores_by_category: dict[Category, list[int]] = defaultdict(list)
    amount_by_category: dict[Category, int] = defaultdict(int)
    for transaction in transactions:
        if transaction.satisfaction_score is None or transaction.satisfaction_score < 4:
            continue
        category = Category(transaction.category)
        scores_by_category[category].append(transaction.satisfaction_score)
        amount_by_category[category] += transaction.amount

    display_name = nickname or "사용자"
    if not scores_by_category:
        return TopHappyConsumption(
            message=f"{display_name}님의 행복 소비 데이터가 아직 부족합니다.",
            category=None,
            category_name=None,
            avg_score=None,
            total_amount=0,
            count=0,
        )

    best_category = max(
        scores_by_category,
        key=lambda category: (
            sum(scores_by_category[category]) / len(scores_by_category[category]),
            len(scores_by_category[category]),
            amount_by_category[category],
        ),
    )
    scores = scores_by_category[best_category]
    category_name = CATEGORY_LABELS[best_category]
    return TopHappyConsumption(
        message=f"{display_name}님의 행복 소비는 {category_name} 지출입니다.",
        category=best_category,
        category_name=category_name,
        avg_score=round(sum(scores) / len(scores), 1),
        total_amount=amount_by_category[best_category],
        count=len(scores),
    )
