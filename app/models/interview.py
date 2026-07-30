import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.question import Question


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        CheckConstraint(
            "language IN ('python','java','cpp','javascript')", name="ck_interviews_language"
        ),
        CheckConstraint(
            "difficulty IN ('junior','middle','senior')", name="ck_interviews_difficulty"
        ),
        CheckConstraint(
            "status IN ('in_progress','completed','abandoned')", name="ck_interviews_status"
        ),
        # A user can have at most one active interview - enforced in InterviewService too,
        # but a DB-level constraint closes the race-condition window between two
        # concurrent start() calls that both pass the application-level check.
        Index(
            "ix_interviews_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", order_by="Question.order_index"
    )
