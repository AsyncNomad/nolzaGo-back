from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DBModelMixin
from app.schemas.user import UserOut


class MemoryBase(BaseModel):
    title: str = Field(max_length=255)
    content: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    location_name: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    origin_post_id: UUID | None = None


class MemoryCreate(MemoryBase):
    pass


class MemoryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    image_url: str | None = None
    location_name: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    origin_post_id: UUID | None = None


class MemoryOut(DBModelMixin):
    title: str
    content: str | None
    image_url: str | None
    location_name: str | None
    latitude: float | None
    longitude: float | None
    like_count: int
    owner_id: UUID
    owner: UserOut | None
    created_at: datetime | None = None
    origin_post_id: UUID | None = None
    origin_post_title: str | None = None
    origin_post_status: str | None = None

    model_config = {"from_attributes": True}
