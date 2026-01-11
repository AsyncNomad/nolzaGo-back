from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DBModelMixin
from app.schemas.user import UserOut

POST_STATUS_CHOICES = ("모집 중", "모집 마감", "놀이 진행 중", "종료")


class PostBase(BaseModel):
    title: str = Field(max_length=255)
    game_type: str = Field(max_length=100)
    description: str | None = None
    location_name: str = Field(max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_participants: int = Field(default=4, ge=2, le=100)
    start_time: datetime | None = None
    like_count: int = 0
    status: str = Field(default="모집 중", pattern="|".join(POST_STATUS_CHOICES))


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location_name: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_participants: int | None = Field(default=None, ge=2, le=100)
    start_time: datetime | None = None
    like_count: int | None = None
    status: str | None = Field(default=None, pattern="|".join(POST_STATUS_CHOICES))


class PostOut(DBModelMixin):
    title: str
    game_type: str
    description: str | None
    location_name: str
    latitude: float | None
    longitude: float | None
    max_participants: int
    status: str
    start_time: datetime | None
    owner_id: UUID
    participants_count: int
    owner: UserOut | None
    like_count: int
    is_liked: bool = False
