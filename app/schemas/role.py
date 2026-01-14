from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class RoleAssignRequest(BaseModel):
    police: int
    thief: int


class RoleAssignmentOut(BaseModel):
    id: UUID
    user_id: UUID
    post_id: UUID
    role: str
    is_captured: bool = False
    created_at: datetime
    user_display_name: str | None = None
    user_profile_image_url: str | None = None

    class Config:
        from_attributes = True


class RoleChatMessageOut(BaseModel):
    id: UUID
    user_id: UUID
    post_id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
