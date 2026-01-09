from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: UUID | None = None


class AuthSummary(BaseModel):
    message: str
    joined_at: datetime | None = None
