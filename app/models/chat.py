from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    post_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    post: Mapped["Post"] = relationship("Post", back_populates="messages")
    user: Mapped["User"] = relationship("User")


@event.listens_for(ChatMessage, "before_insert")
def _strip_tz_on_insert(mapper, connection, target: "ChatMessage"):
    if target.created_at and target.created_at.tzinfo:
        target.created_at = target.created_at.replace(tzinfo=None)


@event.listens_for(ChatMessage, "before_update")
def _strip_tz_on_update(mapper, connection, target: "ChatMessage"):
    if target.created_at and target.created_at.tzinfo:
        target.created_at = target.created_at.replace(tzinfo=None)
