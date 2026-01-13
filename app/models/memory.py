from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MemoryPost(Base):
    __tablename__ = "memory_posts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    origin_post_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )
    origin_post_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    origin_post_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship("User")
    origin_post: Mapped["Post"] = relationship("Post", foreign_keys=[origin_post_id])
