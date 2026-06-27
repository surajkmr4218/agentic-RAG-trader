"""
Handles data ingestion from FMP (Financial Modeling Prep) API. 
Caches results in the database to avoid excessive API calls. 
Each type of data has a defined time-to-live (TTL) to determine freshness.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Signal

BASE = "https://financialmodelingprep.com/stable"

# How long a saved signal stays "fresh". Prices move intraday-ish; scores, consensus,
# and price targets barely move. Tune per-type if you blow the budget.
DEFAULT_TTL = dt.timedelta(hours=12)
TTL_BY_KIND: dict[str, dt.timedelta] = {
    "eod_prices": dt.timedelta(hours=12),
    "financial_scores": dt.timedelta(days=3),
    "analyst_consensus": dt.timedelta(days=3),
    "analyst_grades": dt.timedelta(days=3),
    "price_target_consensus": dt.timedelta(days=3),
}


def _get(path: str, **params: Any) -> Any:
    """Raw FMP GET. Adds the apikey. No caching here — callers go through _cached()."""
    params["apikey"] = settings.fmp_api_key
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BASE}/{path}", params=params)
        r.raise_for_status()
        return r.json()

def _fresh(row: Signal, kind: str) -> bool:
    ttl = TTL_BY_KIND.get(kind, DEFAULT_TTL)
    age = dt.datetime.now(dt.UTC) - row.fetched_at
    return age < ttl

def _cached(session: Session, ticker: str, kind: str, path: str, **params: Any) -> Any:
    """Return cached payload if fresh; else fetch from FMP, persist to Signal, return."""
    stmt = (
        select(Signal)
        .where(Signal.ticker == ticker, Signal.kind == kind)
        .order_by(Signal.fetched_at.desc())
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if row is not None and _fresh(row, kind):
        return row.payload  # cache hit — zero FMP calls

    payload = _get(path, **params)  # cache miss / stale — one FMP call
    session.add(Signal(ticker=ticker, kind=kind, payload=payload))
    session.commit()
    return payload

def financial_scores(session: Session, ticker: str) -> Any:
    """Altman Z-score, Piotroski F-score. Bullish tail = high Piotroski + safe Z."""
    return _cached(session, ticker, "financial_scores", "financial-scores", symbol=ticker)


def eod_prices(session: Session, ticker: str) -> list[dict]:
    """Light EOD history — used for price sanity + Week-5 backtest forward returns."""
    return _cached(
        session, ticker, "eod_prices", "historical-price-eod/light", symbol=ticker,
    )


def analyst_consensus(session: Session, ticker: str) -> Any:
    """grades-consensus: counts of strongBuy/buy/hold/sell/strongSell."""
    return _cached(session, ticker, "analyst_consensus", "grades-consensus", symbol=ticker)


def analyst_grades(session: Session, ticker: str, limit: int = 20) -> list[dict]:
    """Recent rating changes (upgrade/downgrade) by firm — bullish tail = upgrades."""
    return _cached(
        session, ticker, "analyst_grades", "grades", symbol=ticker, limit=limit,
    )


def price_target_consensus(session: Session, ticker: str) -> Any:
    """Analyst price targets (high/low/median/consensus). Bullish tail = consensus >> price."""
    return _cached(
        session, ticker, "price_target_consensus", "price-target-consensus", symbol=ticker,
    )