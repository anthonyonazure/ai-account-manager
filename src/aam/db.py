"""SQLAlchemy async setup. SQLite for the demo, swap URL for Postgres in prod."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DATABASE_URL = os.environ.get("AAM_DATABASE_URL", "sqlite+aiosqlite:///./aam.db")

_engine = create_async_engine(DATABASE_URL, echo=False, future=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    tier: Mapped[str] = mapped_column(String, default="silver")
    region: Mapped[str] = mapped_column(String, default="NA")
    services_purchased: Mapped[list] = mapped_column(JSON, default=list)
    contract_start: Mapped[datetime] = mapped_column(DateTime)
    contract_end: Mapped[datetime] = mapped_column(DateTime)
    arr: Mapped[float] = mapped_column(Float, default=0.0)
    industry: Mapped[str] = mapped_column(String, default="financial_services")
    am_email: Mapped[str] = mapped_column(String)

    snapshots: Mapped[list["AccountSnapshot"]] = relationship(back_populates="account")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Raw signal inputs from each source
    hubspot_emails_opened_30d: Mapped[int] = mapped_column(Integer, default=0)
    hubspot_meetings_30d: Mapped[int] = mapped_column(Integer, default=0)
    hubspot_last_activity_days_ago: Mapped[int] = mapped_column(Integer, default=999)

    zendesk_tickets_opened_30d: Mapped[int] = mapped_column(Integer, default=0)
    zendesk_tickets_closed_30d: Mapped[int] = mapped_column(Integer, default=0)
    zendesk_p1_count_30d: Mapped[int] = mapped_column(Integer, default=0)
    zendesk_avg_resolution_hours: Mapped[float] = mapped_column(Float, default=0.0)
    zendesk_csat: Mapped[float] = mapped_column(Float, default=0.0)

    portal_logins_30d: Mapped[int] = mapped_column(Integer, default=0)
    portal_modules_active: Mapped[list] = mapped_column(JSON, default=list)
    portal_modules_unused: Mapped[list] = mapped_column(JSON, default=list)
    portal_last_login_days_ago: Mapped[int] = mapped_column(Integer, default=999)

    sharepoint_doc_views_30d: Mapped[int] = mapped_column(Integer, default=0)

    account: Mapped["Account"] = relationship(back_populates="snapshots")


class Signal(Base):
    """Computed signal score per account, per snapshot."""

    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("account_id", "snapshot_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("account_snapshots.id"), index=True)
    kind: Mapped[str] = mapped_column(String, index=True)  # see signals.SIGNAL_KINDS
    score: Mapped[float] = mapped_column(Float)  # 0.0 = none, 1.0 = max
    direction: Mapped[str] = mapped_column(String)  # "risk" | "opportunity"
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    am_email: Mapped[str] = mapped_column(String, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    markdown: Mapped[str] = mapped_column(String)
    actions: Mapped[list] = mapped_column(JSON)  # list of {account_id, kind, score, reason, suggested_action}


class AmFeedback(Base):
    __tablename__ = "am_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    briefing_id: Mapped[str] = mapped_column(ForeignKey("briefings.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    am_email: Mapped[str] = mapped_column(String, index=True)
    verdict: Mapped[str] = mapped_column(String)  # "done" | "snooze" | "wrong"
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as s:
        yield s
        await s.commit()
