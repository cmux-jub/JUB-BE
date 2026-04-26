from enum import StrEnum


class OnboardingStatus(StrEnum):
    NEEDS_BANK_LINK = "NEEDS_BANK_LINK"
    NEEDS_LABELING = "NEEDS_LABELING"
    READY = "READY"


class SubscriptionTier(StrEnum):
    FREE_FULL = "FREE_FULL"
    FREE_LIMITED = "FREE_LIMITED"
    PAID = "PAID"


class Category(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    LASTING = "LASTING"
    ESSENTIAL = "ESSENTIAL"


class OnboardingSelectionReason(StrEnum):
    LARGE_AMOUNT = "LARGE_AMOUNT"
    REPEATED_PURCHASE = "REPEATED_PURCHASE"
    UNUSUAL_PATTERN = "UNUSUAL_PATTERN"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"


class OnboardingNextStep(StrEnum):
    LINK_BANK = "LINK_BANK"
    LABEL_MORE = "LABEL_MORE"
    CREATE_FIRST_INSIGHT = "CREATE_FIRST_INSIGHT"
    READY = "READY"


class ChatbotDecision(StrEnum):
    BUY = "BUY"
    RECONSIDER = "RECONSIDER"
    SKIP = "SKIP"


class ChatbotModelTier(StrEnum):
    FULL = "FULL"
    LITE = "LITE"


class ChatbotMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class RetrospectiveSelectionReason(StrEnum):
    HIGH_SATISFACTION_REINFORCE = "HIGH_SATISFACTION_REINFORCE"
    LARGE_AMOUNT_GAP = "LARGE_AMOUNT_GAP"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    DIVERSITY = "DIVERSITY"
    CHATBOT_FOLLOW_UP = "CHATBOT_FOLLOW_UP"


class SavedAmountPeriod(StrEnum):
    ALL = "all"
    MONTH = "month"
    YEAR = "year"


class CategorySatisfactionPeriod(StrEnum):
    DAYS_30 = "30d"
    DAYS_90 = "90d"
    ALL = "all"


class ScoreTrendPeriod(StrEnum):
    WEEKS_8 = "8w"
    WEEKS_12 = "12w"
    MONTHS_6 = "6m"


class SubscriptionPlan(StrEnum):
    MONTHLY = "MONTHLY"
