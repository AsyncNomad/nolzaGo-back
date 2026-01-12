from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import event

from app.db.base import Base


class ChatRead(Base):
    __tablename__ = "chat_reads"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_chat_read_post_user"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)

    post = relationship("Post")
    user = relationship("User")


@event.listens_for(ChatRead, "before_insert")
def _strip_tz_insert(mapper, connection, target: "ChatRead"):
    if target.last_read_at and target.last_read_at.tzinfo:
        target.last_read_at = target.last_read_at.replace(tzinfo=None)


@event.listens_for(ChatRead, "before_update")
def _strip_tz_update(mapper, connection, target: "ChatRead"):
    if target.last_read_at and target.last_read_at.tzinfo:
        target.last_read_at = target.last_read_at.replace(tzinfo=None)
