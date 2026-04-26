from datetime import date

from pydantic import BaseModel, Field


class OAuthStartRequest(BaseModel):
    provider: str = Field(pattern="^OPEN_BANKING_KR$")


class OAuthStartResponse(BaseModel):
    auth_url: str
    state_token: str


class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state_token: str = Field(min_length=1)


class LinkedAccountResponse(BaseModel):
    account_id: str
    bank_name: str
    masked_number: str


class OAuthCallbackResponse(BaseModel):
    linked_accounts: list[LinkedAccountResponse]


class BankingSyncRequest(BaseModel):
    from_date: date
    to_date: date


class BankingSyncResponse(BaseModel):
    synced_count: int
    new_count: int
    sync_id: str
