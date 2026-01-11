from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import post_likes, post_participants

POST_STATUS_CHOICES = ("모집 중", "모집 마감", "놀이 진행 중", "종료")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    game_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_participants: Mapped[int] = mapped_column(Integer, default=4)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="모집 중")
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owner_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="posts")
    participants: Mapped[List["User"]] = relationship(
        "User",
        secondary=post_participants,
        back_populates="joined_posts",
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="post", cascade="all, delete-orphan"
    )
    liked_users: Mapped[List["User"]] = relationship(
        "User",
        secondary=post_likes,
        back_populates="liked_posts",
    )
