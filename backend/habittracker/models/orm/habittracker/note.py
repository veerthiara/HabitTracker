import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from habittracker.models.orm.base import Base

if TYPE_CHECKING:
    from habittracker.models.orm.habittracker.user import User

# Dimension must match the Ollama embedding model in use.
# nomic-embed-text → 768  |  mxbai-embed-large → 1024
# Change requires a new migration — do not edit in place.
EMBED_DIMS = 768


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual | ai
    # Nullable: populated by the embedding pipeline (scripts/embed/main.py).
    # Never returned in normal API responses — internal only.
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(EMBED_DIMS), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="notes")
