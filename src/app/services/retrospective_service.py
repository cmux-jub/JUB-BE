from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta

from app.ai.question_generator import QuestionCandidate, SpendingQuestionGenerator
from app.core.enums import Category, ChatbotDecision, RetrospectiveSelectionReason
from app.core.exceptions import AppException, ErrorCode
from app.models.chatbot import ChatbotSession
from app.models.retrospective import Retrospective, RetrospectiveEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.chatbot_repo import ChatbotRepository
from app.repositories.retrospective_repo import RetrospectiveRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.feedback import FeedbackQuestionContent, FeedbackTransactionSnapshot, ScoreScale
from app.schemas.retrospective import (
    CurrentWeekRetrospectiveResponse,
    LinkedChatbotSummary,
    RetrospectiveHistoryItem,
    RetrospectiveHistoryResponse,
    RetrospectiveQuestionItem,
    SubmitRetrospectiveRequest,
    SubmitRetrospectiveResponse,
    WeeklyInsight,
    WeeklySummaryResponse,
)
from app.services.spending_summary import build_happy_archive, build_spending_comparison, build_top_happy_consumption

MIN_RETROSPECTIVE_QUESTION_COUNT = 5
MAX_RETROSPECTIVE_QUESTION_COUNT = 10
CATEGORY_LABELS = {
    Category.IMMEDIATE: "즉시 소비",
    Category.LASTING: "지속 소비",
    Category.ESSENTIAL: "필수 소비",
}


class RetrospectiveService:
    def __init__(
        self,
        retrospective_repo: RetrospectiveRepository,
        transaction_repo: TransactionRepository,
        chatbot_repo: ChatbotRepository,
        question_generator: SpendingQuestionGenerator | None = None,
        today: date | None = None,
    ) -> None:
        self.retrospective_repo = retrospective_repo
        self.transaction_repo = transaction_repo
        self.chatbot_repo = chatbot_repo
        self.question_generator = question_generator or SpendingQuestionGenerator()
        self.today = today

    async def get_current_week(self, user: User) -> CurrentWeekRetrospectiveResponse:
        week_start, week_end = self.resolve_week_range(self.today or datetime.now(UTC).date())
        existing_retrospective = await self.retrospective_repo.find_by_week(user.id, week_start)
        transactions = await self.transaction_repo.list_for_retrospective_week(
            user_id=user.id,
            week_start=self.start_of_day(week_start),
            week_end=self.end_of_day(week_end),
            limit=MAX_RETROSPECTIVE_QUESTION_COUNT,
        )
        linked_sessions = await self.find_linked_sessions(user.id, transactions)
        three_months_ago = self.subtract_months(week_start, 3)
        historical_transactions = await self.transaction_repo.list_labeled_since(
            user_id=user.id,
            since=self.start_of_day(three_months_ago),
        )
        merchant_counts = Counter(transaction.merchant for transaction in transactions)
        category_avg_scores = self.average_scores_by_category(historical_transactions)
        candidates = [
            self.to_question_candidate(
                transaction=transaction,
                reason=self.resolve_selection_reason(
                    transaction=transaction,
                    linked_session=self.resolve_linked_session(transaction, linked_sessions),
                    merchant_count=merchant_counts[transaction.merchant],
                ),
                merchant_count=merchant_counts[transaction.merchant],
                linked_session=self.resolve_linked_session(transaction, linked_sessions),
                category_avg_score=category_avg_scores.get(Category(transaction.category)),
            )
            for transaction in transactions
        ]
        generated_questions = await self.question_generator.generate(candidates)

        return CurrentWeekRetrospectiveResponse(
            week_start=week_start,
            week_end=week_end,
            is_completed=existing_retrospective is not None,
            question_count=len(generated_questions),
            min_question_count=MIN_RETROSPECTIVE_QUESTION_COUNT,
            max_question_count=MAX_RETROSPECTIVE_QUESTION_COUNT,
            questions=[
                self.to_current_week_item(
                    transaction=transaction,
                    linked_sessions=linked_sessions,
                    generated_question=generated_question,
                    merchant_count=merchant_counts[transaction.merchant],
                )
                for transaction, generated_question in zip(transactions, generated_questions, strict=True)
            ],
        )

    async def submit_retrospective(
        self,
        user: User,
        request: SubmitRetrospectiveRequest,
    ) -> SubmitRetrospectiveResponse:
        existing_retrospective = await self.retrospective_repo.find_by_week(user.id, request.week_start)
        if existing_retrospective is not None:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "이미 제출된 회고입니다")

        week_end = request.week_start + timedelta(days=6)
        await self.ensure_answers_match_current_questions(user.id, request.week_start, week_end, request.answers)
        transactions_by_id: dict[str, Transaction] = {}
        completed_at = datetime.now(UTC)
        entries: list[RetrospectiveEntry] = []

        for answer in request.answers:
            transaction = await self.transaction_repo.find_by_id(user.id, answer.transaction_id)
            if transaction is None:
                raise AppException(ErrorCode.NOT_FOUND, 404, "회고 대상 거래를 찾을 수 없습니다")

            transaction.satisfaction_score = answer.score
            transaction.satisfaction_text = answer.text
            transaction.labeled_at = completed_at
            await self.transaction_repo.save(transaction)

            transactions_by_id[transaction.id] = transaction
            entries.append(
                RetrospectiveEntry(
                    retrospective_id="",
                    transaction_id=transaction.id,
                    score=answer.score,
                    text=answer.text,
                    created_at=completed_at,
                )
            )

        scores = [answer.score for answer in request.answers]
        avg_score = sum(scores) / len(scores)
        previous_week_transactions = await self.transaction_repo.list_labeled_between(
            user_id=user.id,
            from_date=self.start_of_day(request.week_start - timedelta(days=7)),
            to_date=self.end_of_day(request.week_start - timedelta(days=1)),
        )
        weekly_insight = self.create_weekly_insight(
            avg_score=avg_score,
            transactions=list(transactions_by_id.values()),
            previous_week_transactions=previous_week_transactions,
        )
        retrospective = Retrospective(
            user_id=user.id,
            week_start=request.week_start,
            week_end=week_end,
            completed_at=completed_at,
            avg_score=round(avg_score, 1),
            entry_count=len(entries),
            weekly_insight=weekly_insight.model_dump(mode="json"),
        )
        saved_retrospective = await self.retrospective_repo.create(retrospective, entries)

        return SubmitRetrospectiveResponse(
            retrospective_id=saved_retrospective.id,
            week_start=saved_retrospective.week_start,
            completed_at=saved_retrospective.completed_at,
            submitted_count=saved_retrospective.entry_count,
            weekly_insight=weekly_insight,
        )

    async def get_weekly_summary(self, user: User, retrospective_id: str) -> WeeklySummaryResponse:
        retrospective = await self.retrospective_repo.find_by_id(user.id, retrospective_id)
        if retrospective is None:
            raise AppException(ErrorCode.NOT_FOUND, 404, "회고를 찾을 수 없습니다")

        week_start = retrospective.week_start
        week_end = retrospective.week_end

        spending_comparison = await self.build_weekly_spending_comparison(user.id, week_start, week_end)
        saved_amount_comparison = await self.build_weekly_saved_amount_comparison(user.id, week_start, week_end)

        transactions = await self.transaction_repo.list_labeled_between(
            user_id=user.id,
            from_date=self.start_of_day(week_start),
            to_date=self.end_of_day(week_end),
        )

        return WeeklySummaryResponse(
            retrospective_id=retrospective.id,
            week_start=week_start,
            week_end=week_end,
            spending_comparison=spending_comparison,
            saved_amount_comparison=saved_amount_comparison,
            top_happy_consumption=build_top_happy_consumption(transactions, nickname=user.nickname),
            happy_purchase_archive=build_happy_archive(transactions),
        )

    async def list_retrospectives(
        self,
        user_id: str,
        from_week: date | None = None,
        to_week: date | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> RetrospectiveHistoryResponse:
        normalized_limit = min(max(limit, 1), 100)
        retrospectives = await self.retrospective_repo.list_by_user(
            user_id=user_id,
            from_week=from_week,
            to_week=to_week,
            cursor=cursor,
            limit=normalized_limit + 1,
        )
        has_next = len(retrospectives) > normalized_limit
        page_items = retrospectives[:normalized_limit]
        return RetrospectiveHistoryResponse(
            retrospectives=[self.to_history_item(retrospective) for retrospective in page_items],
            next_cursor=page_items[-1].id if has_next and page_items else None,
        )

    async def find_linked_sessions(
        self,
        user_id: str,
        transactions: list[Transaction],
    ) -> dict[str, ChatbotSession]:
        transaction_ids = [transaction.id for transaction in transactions]
        linked_session_ids = [
            transaction.linked_chatbot_session_id
            for transaction in transactions
            if transaction.linked_chatbot_session_id is not None
        ]
        sessions = await self.chatbot_repo.find_sessions_by_ids(user_id, linked_session_ids)
        sessions.extend(await self.chatbot_repo.find_sessions_by_linked_transaction_ids(user_id, transaction_ids))

        sessions_by_transaction_id = {
            session.linked_transaction_id: session for session in sessions if session.linked_transaction_id is not None
        }
        for session in sessions:
            sessions_by_transaction_id.setdefault(session.id, session)
        return sessions_by_transaction_id

    async def ensure_answers_match_current_questions(
        self,
        user_id: str,
        week_start: date,
        week_end: date,
        answers: list,
    ) -> None:
        transactions = await self.transaction_repo.list_for_retrospective_week(
            user_id=user_id,
            week_start=self.start_of_day(week_start),
            week_end=self.end_of_day(week_end),
            limit=MAX_RETROSPECTIVE_QUESTION_COUNT,
        )
        required_question_ids = {f"rq_{transaction.id}" for transaction in transactions}
        submitted_question_ids = {answer.question_id for answer in answers}
        if required_question_ids and submitted_question_ids != required_question_ids:
            raise AppException(ErrorCode.INVALID_INPUT, 400, "이번 주 회고 질문 전체에 답변해야 합니다")

    async def build_weekly_spending_comparison(self, user_id: str, week_start: date, week_end: date):
        previous_week_start = week_start - timedelta(days=7)
        previous_week_end = week_start - timedelta(days=1)
        current_amount = await self.transaction_repo.sum_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(week_start),
            to_date=self.end_of_day(week_end),
        )
        previous_amount = await self.transaction_repo.sum_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(previous_week_start),
            to_date=self.end_of_day(previous_week_end),
        )
        return build_spending_comparison(current_amount, previous_amount)

    async def build_weekly_saved_amount_comparison(self, user_id: str, week_start: date, week_end: date):
        previous_week_start = week_start - timedelta(days=7)
        previous_week_end = week_start - timedelta(days=1)
        current_amount = await self.sum_saved_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(week_start),
            to_date=self.end_of_day(week_end),
        )
        previous_amount = await self.sum_saved_amount_between(
            user_id=user_id,
            from_date=self.start_of_day(previous_week_start),
            to_date=self.end_of_day(previous_week_end),
        )
        return build_spending_comparison(current_amount, previous_amount)

    async def sum_saved_amount_between(self, user_id: str, from_date: datetime, to_date: datetime) -> int:
        sessions = await self.chatbot_repo.list_decided_sessions(
            user_id=user_id,
            decisions=[ChatbotDecision.SKIP],
            from_date=from_date,
            to_date=to_date,
            limit=1000,
        )
        return sum(self.summary_amount(session) for session in sessions)

    def to_current_week_item(
        self,
        transaction: Transaction,
        linked_sessions: dict[str, ChatbotSession],
        generated_question,
        merchant_count: int,
    ) -> RetrospectiveQuestionItem:
        linked_session = self.resolve_linked_session(transaction, linked_sessions)
        return RetrospectiveQuestionItem(
            question_id=generated_question.question_id,
            transaction=FeedbackTransactionSnapshot(
                transaction_id=transaction.id,
                amount=transaction.amount,
                merchant=transaction.merchant,
                category=Category(transaction.category),
                occurred_at=transaction.occurred_at,
            ),
            selection_reason=self.resolve_selection_reason(transaction, linked_session, merchant_count),
            pattern_summary=generated_question.pattern_summary,
            question=FeedbackQuestionContent(
                title=generated_question.title,
                body=generated_question.body,
                score_scale=ScoreScale(
                    min_label=generated_question.min_label,
                    max_label=generated_question.max_label,
                ),
            ),
            linked_chatbot_summary=self.to_linked_chatbot_summary(linked_session),
        )

    @staticmethod
    def resolve_linked_session(
        transaction: Transaction,
        linked_sessions: dict[str, ChatbotSession],
    ) -> ChatbotSession | None:
        if transaction.linked_chatbot_session_id is not None:
            return linked_sessions.get(transaction.linked_chatbot_session_id)
        return linked_sessions.get(transaction.id)

    @staticmethod
    def resolve_selection_reason(
        transaction: Transaction,
        linked_session: ChatbotSession | None,
        merchant_count: int = 1,
    ) -> RetrospectiveSelectionReason:
        if linked_session is not None:
            return RetrospectiveSelectionReason.CHATBOT_FOLLOW_UP
        if merchant_count >= 2:
            return RetrospectiveSelectionReason.REPEATED_MERCHANT
        if transaction.occurred_at.hour >= 21:
            return RetrospectiveSelectionReason.TIME_PATTERN
        if transaction.satisfaction_score is not None and transaction.satisfaction_score >= 4:
            return RetrospectiveSelectionReason.HIGH_SATISFACTION_REINFORCE
        if transaction.category_confidence < 0.7:
            return RetrospectiveSelectionReason.HIGH_UNCERTAINTY
        if transaction.amount >= 50000:
            return RetrospectiveSelectionReason.LARGE_AMOUNT_GAP
        return RetrospectiveSelectionReason.DIVERSITY

    @staticmethod
    def to_linked_chatbot_summary(session: ChatbotSession | None) -> LinkedChatbotSummary | None:
        if session is None or session.summary is None or session.decision is None:
            return None
        return LinkedChatbotSummary(
            session_id=session.id,
            user_reasoning=session.summary.get("user_reasoning"),
            decision=ChatbotDecision(session.decision),
        )

    @staticmethod
    def to_question_candidate(
        transaction: Transaction,
        reason: RetrospectiveSelectionReason,
        merchant_count: int,
        linked_session: ChatbotSession | None,
        category_avg_score: float | None,
    ) -> QuestionCandidate:
        linked_user_reasoning = None
        if linked_session is not None and linked_session.summary is not None:
            linked_user_reasoning = linked_session.summary.get("user_reasoning")
        return QuestionCandidate(
            question_id=f"rq_{transaction.id}",
            amount=transaction.amount,
            merchant=transaction.merchant,
            category=transaction.category,
            occurred_at=transaction.occurred_at.isoformat(),
            selection_reason=reason.value,
            merchant_count=merchant_count,
            linked_user_reasoning=linked_user_reasoning,
            category_avg_score=category_avg_score,
        )

    @staticmethod
    def average_scores_by_category(transactions: list[Transaction]) -> dict[Category, float]:
        scores_by_category: dict[Category, list[int]] = defaultdict(list)
        for transaction in transactions:
            if transaction.satisfaction_score is None:
                continue
            scores_by_category[Category(transaction.category)].append(transaction.satisfaction_score)
        return {category: sum(scores) / len(scores) for category, scores in scores_by_category.items() if scores}

    @staticmethod
    def create_weekly_insight(
        avg_score: float,
        transactions: list[Transaction],
        previous_week_transactions: list[Transaction],
    ) -> WeeklyInsight:
        previous_scores = [
            transaction.satisfaction_score
            for transaction in previous_week_transactions
            if transaction.satisfaction_score is not None
        ]
        if previous_scores:
            previous_avg = sum(previous_scores) / len(previous_scores)
            diff = avg_score - previous_avg
            headline = f"이번 주 만족도 평균 {avg_score:.1f}점, 지난주보다 {diff:+.1f}"
        else:
            headline = f"이번 주 만족도 평균 {avg_score:.1f}점"

        highlight = RetrospectiveService.create_highlight(transactions)
        return WeeklyInsight(headline=headline, highlight=highlight)

    @staticmethod
    def create_highlight(transactions: list[Transaction]) -> str:
        scores_by_category: dict[Category, list[int]] = defaultdict(list)
        for transaction in transactions:
            if transaction.satisfaction_score is None:
                continue
            scores_by_category[Category(transaction.category)].append(transaction.satisfaction_score)

        if not scores_by_category:
            return "이번 주 회고 데이터가 차곡차곡 쌓였어요"

        best_category = max(
            scores_by_category,
            key=lambda category: (
                sum(scores_by_category[category]) / len(scores_by_category[category]),
                len(scores_by_category[category]),
            ),
        )
        return f"{CATEGORY_LABELS[best_category]} 카테고리에서 가장 높은 만족"

    @staticmethod
    def resolve_week_range(value: date) -> tuple[date, date]:
        week_start = value - timedelta(days=value.weekday())
        return week_start, week_start + timedelta(days=6)

    @staticmethod
    def to_history_item(retrospective: Retrospective) -> RetrospectiveHistoryItem:
        return RetrospectiveHistoryItem(
            retrospective_id=retrospective.id,
            week_start=retrospective.week_start,
            week_end=retrospective.week_end,
            completed_at=retrospective.completed_at,
            avg_score=retrospective.avg_score,
            entry_count=retrospective.entry_count,
        )

    @staticmethod
    def start_of_day(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=UTC)

    @staticmethod
    def end_of_day(value: date) -> datetime:
        return datetime.combine(value, time.max, tzinfo=UTC)

    @staticmethod
    def summary_amount(session: ChatbotSession) -> int:
        if session.summary and isinstance(session.summary.get("amount"), int):
            return session.summary["amount"]
        return session.amount_hint or 0

    @staticmethod
    def subtract_months(value: date, months: int) -> date:
        month_index = value.month - months
        year = value.year
        while month_index <= 0:
            month_index += 12
            year -= 1

        last_day = RetrospectiveService.last_day_of_month(year, month_index)
        return value.replace(year=year, month=month_index, day=min(value.day, last_day))

    @staticmethod
    def last_day_of_month(year: int, month: int) -> int:
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return next_month.toordinal() - date(year, month, 1).toordinal()
