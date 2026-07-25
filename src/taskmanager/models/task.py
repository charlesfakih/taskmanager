import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from taskmanager.db.base import Base
from taskmanager.domain.enums import TaskPriority, TaskStatus


class Task(Base):
    """FK columns only, no relationship() attributes — related entities are
    resolved through GraphQL DataLoaders instead, to avoid ORM lazy-load N+1s."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), default=None)

    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.TODO.value)
    priority: Mapped[str] = mapped_column(String(20), default=TaskPriority.MEDIUM.value)

    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    due_date: Mapped[dt.date | None] = mapped_column(Date(), default=None)

    # Optimistic-concurrency token: every mutating write is a conditional
    # `UPDATE ... WHERE id = :id AND version = :expected` (see services/tasks.py).
    version: Mapped[int] = mapped_column(Integer(), default=1, server_default="1")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"status IN {tuple(s.value for s in TaskStatus)}", name="valid_status"),
        CheckConstraint(
            f"priority IN {tuple(p.value for p in TaskPriority)}", name="valid_priority"
        ),
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_assignee_id", "assignee_id"),
        Index("ix_tasks_created_by_id", "created_by_id"),
        # One composite index per supported sort field, leading with
        # project_id (every list query is project-scoped).
        Index("ix_tasks_project_created_id", "project_id", "created_at", "id"),
        Index("ix_tasks_project_status_id", "project_id", "status", "id"),
        Index("ix_tasks_project_priority_id", "project_id", "priority", "id"),
        Index("ix_tasks_project_assignee_id_id", "project_id", "assignee_id", "id"),
    )
