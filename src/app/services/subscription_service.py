from datetime import UTC, datetime, timedelta

from app.core.enums import SubscriptionTier
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.subscription import SubscriptionStatusResponse, UpgradeSubscriptionRequest

FREE_FULL_CHATBOT_LIMIT = 5


class SubscriptionService:
    def __init__(self, subscription_repo: SubscriptionRepository, user_repo: UserRepository) -> None:
        self.subscription_repo = subscription_repo
        self.user_repo = user_repo

    async def get_status(self, user: User) -> SubscriptionStatusResponse:
        subscription = await self.subscription_repo.find_by_user_id(user.id)
        return self.to_status_response(user, subscription)

    async def upgrade(self, user: User, request: UpgradeSubscriptionRequest) -> SubscriptionStatusResponse:
        user.subscription_tier = SubscriptionTier.PAID.value
        await self.user_repo.save(user)

        subscription = await self.subscription_repo.find_by_user_id(user.id)
        next_billing_date = datetime.now(UTC) + timedelta(days=30)
        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                tier=SubscriptionTier.PAID.value,
                plan=request.plan.value,
                next_billing_date=next_billing_date,
            )
        else:
            subscription.tier = SubscriptionTier.PAID.value
            subscription.plan = request.plan.value
            subscription.next_billing_date = next_billing_date

        saved_subscription = await self.subscription_repo.save(subscription)
        return self.to_status_response(user, saved_subscription)

    @staticmethod
    def to_status_response(user: User, subscription: Subscription | None) -> SubscriptionStatusResponse:
        remaining = max(FREE_FULL_CHATBOT_LIMIT - user.chatbot_usage_count, 0)
        if user.subscription_tier != SubscriptionTier.FREE_FULL.value:
            remaining = 0

        return SubscriptionStatusResponse(
            tier=SubscriptionTier(user.subscription_tier),
            chatbot_usage_count=user.chatbot_usage_count,
            chatbot_full_remaining=remaining,
            downgrades_at=subscription.downgrades_at if subscription else None,
            next_billing_date=subscription.next_billing_date if subscription else None,
        )
