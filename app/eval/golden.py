"""Build, inspect, and validate the hand-labeled golden retrieval set.

Provenance: golden.json was labeled on 2026-06-22 against a frozen snapshot of
the latest-10-K chunks for AAPL, META, MSFT, NVDA and TSLA (Item 1A + Item 7),
ingested via scripts/ingest_golden.py. Each case's corpus_ids/corpus_texts are
that snapshot's real Chunk.id values; relevance was judged by reading every
passage. If the corpus is re-ingested the ids change and this file goes stale —
re-label rather than trusting it silently.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Chunk

GOLDEN_PATH = Path(__file__).parent / "golden.json"


def candidate_pool(ticker: str, limit: int = 12) -> list[dict]:
    """Pull a candidate pool of chunks for one ticker, to hand-label into a golden case.

    Print these, read them, and copy the ids that answer your query into relevant_chunk_ids.
    """
    with SessionLocal() as db:
        rows = db.execute(
            select(Chunk.id, Chunk.section, Chunk.text)
            .where(Chunk.meta["ticker"].as_string() == ticker)
            .limit(limit)
        ).all()
    return [{"id": r.id, "section": r.section, "text": r.text[:240]} for r in rows]


def load() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text()) if GOLDEN_PATH.exists() else []


def validate(gold: list[dict]) -> list[str]:
    """Honesty checks: relevant ids must be a subset of the corpus; nothing empty."""
    problems: list[str] = []
    for i, case in enumerate(gold):
        corpus = set(case.get("corpus_ids", []))
        for key in ("query", "relevant_chunk_ids", "corpus_texts", "corpus_ids"):
            if not case.get(key):
                problems.append(f"case {i}: missing/empty '{key}'")
        if len(case.get("corpus_texts", [])) != len(case.get("corpus_ids", [])):
            problems.append(f"case {i}: corpus_texts/corpus_ids length mismatch")
        stray = set(case.get("relevant_chunk_ids", [])) - corpus
        if stray:
            problems.append(f"case {i}: relevant ids {stray} not in corpus_ids")
    return problems


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:  # inspect a candidate pool: python -m app.eval.golden AAPL
        for c in candidate_pool(sys.argv[1]):
            print(f"[{c['id']}] ({c['section']}) {c['text']}")
    else:  # validate the labeled file
        issues = validate(load())
        print("golden.json OK" if not issues else "\n".join(issues))
