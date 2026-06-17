from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)   # ALWAYS upper-case
    cik: Mapped[str] = mapped_column(String(16), index=True)
    form_type: Mapped[str] = mapped_column(String(16))           # 10-K / 10-Q / 8-K
    accession: Mapped[str] = mapped_column(String(32), unique=True)
    fiscal_period: Mapped[str] = mapped_column(String(16))       # e.g. "2025-Q1"
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {item_label: section_text}, e.g. {"item 1a": "...", "item 7": "..."}
    sections: Mapped[dict] = mapped_column(JSON, default=dict)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="filing")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), index=True)
    section: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    context_blurb: Mapped[str | None] = mapped_column(Text)      # Week 2 contextual blurb
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))  # MiniLM/bge-small dim
    meta: Mapped[dict] = mapped_column(JSON, default=dict)       # {"ticker": "AAPL", ...}

    filing: Mapped["Filing"] = relationship(back_populates="chunks")


class Diff(Base):
    __tablename__ = "diffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)  # ALWAYS upper-case
    section: Mapped[str] = mapped_column(String(64))
    cur_accession: Mapped[str] = mapped_column(String(32), ForeignKey("filings.accession"))
    prior_accession: Mapped[str] = mapped_column(String(32))
    semantic_drift: Mapped[float] = mapped_column(Float)
    lexical_change: Mapped[float] = mapped_column(Float)
    added: Mapped[list] = mapped_column(JSON, default=list)      # added passages
    removed: Mapped[list] = mapped_column(JSON, default=list)    # removed passages
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)  # ALWAYS upper-case
    kind: Mapped[str] = mapped_column(String(16))                # insider/scores/news/analyst/prices
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)  # ALWAYS upper-case
    direction: Mapped[str] = mapped_column(String(16))           # long / flat (no short — cash acct)
    order_type: Mapped[str] = mapped_column(String(16))          # market / limit
    limit_price: Mapped[float | None] = mapped_column(Float)
    size_usd: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)  # [(accession, section), ...]
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency key
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey("hypotheses.id"))
    critic_verdict: Mapped[dict] = mapped_column(JSON, default=dict)
    guardrail: Mapped[dict] = mapped_column(JSON, default=dict)
    human_decision: Mapped[str] = mapped_column(String(16), default="pending")  # approved/rejected/pending
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decisions.decision_id"), unique=True
    )
    symbol: Mapped[str] = mapped_column(String(16))             # ALWAYS upper-case
    side: Mapped[str] = mapped_column(String(8))               # buy / sell
    quantity: Mapped[float] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(16))        # market / limit
    limit_price: Mapped[float | None] = mapped_column(Float)
    broker_order_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    fill_price: Mapped[float | None] = mapped_column(Float)
    forward_return: Mapped[float | None] = mapped_column(Float)
    spy_return: Mapped[float | None] = mapped_column(Float)
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clerk_user_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # set in Week 6
    role: Mapped[str] = mapped_column(String(16), default="owner")              # owner / public
    # Fernet ciphertext — populated Week 6, ENCRYPTED AT REST. Plaintext never lands here.
    robinhood_token_enc: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
