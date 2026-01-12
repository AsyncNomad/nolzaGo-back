from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DBModelMixin
from app.schemas.user import UserOut


class ChatMessageCreate(BaseModel):
    content: str = Field(max_length=1000)


class ChatMessageOut(DBModelMixin):
    content: str
    post_id: UUID
    user_id: UUID
    user: UserOut | None = None
    user_display_name: str | None = None
    user_profile_image_url: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
