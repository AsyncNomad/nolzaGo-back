from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

# Link table for users joining posts
post_participants = Table(
    "post_participants",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("post_id", UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
)

# Link table for users liking posts
post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("post_id", UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
)
