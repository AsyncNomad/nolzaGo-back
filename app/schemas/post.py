from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DBModelMixin
from app.schemas.user import UserOut


class PostBase(BaseModel):
    title: str = Field(max_length=255)
    game_type: str = Field(max_length=100)
    description: str | None = None
    location_name: str = Field(max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_participants: int = Field(default=4, ge=2, le=50)
    start_time: datetime | None = None
    like_count: int = 0


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location_name: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_participants: int | None = Field(default=None, ge=2, le=50)
    start_time: datetime | None = None
    like_count: int | None = None


class PostOut(DBModelMixin):
    title: str
    game_type: str
    description: str | None
    location_name: str
    latitude: float | None
    longitude: float | None
    max_participants: int
    start_time: datetime | None
    owner_id: UUID
    participants_count: int
    owner: UserOut | None
    like_count: int
