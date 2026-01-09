from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DBModelMixin


class ChatMessageCreate(BaseModel):
    content: str = Field(max_length=1000)


class ChatMessageOut(DBModelMixin):
    content: str
    post_id: UUID
    user_id: UUID
    created_at: datetime | None = None
