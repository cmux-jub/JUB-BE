from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.banking import router as banking_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.health import router as health_router
from app.api.v1.insights import router as insights_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.retrospectives import router as retrospectives_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(banking_router)
api_router.include_router(chatbot_router)
api_router.include_router(insights_router)
api_router.include_router(onboarding_router)
api_router.include_router(retrospectives_router)
api_router.include_router(subscription_router)
api_router.include_router(transactions_router)
api_router.include_router(users_router)
