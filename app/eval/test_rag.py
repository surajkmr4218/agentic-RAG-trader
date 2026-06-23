from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.ab_embeddings import _dense_rank  # reuse the DB-free dense ranker

GOLD = json.loads((Path(__file__).parent / "golden.json").read_text())
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

# --- pure metric functions (no DB, no model) --------------------------------------------------


def precision_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Fraction of the top-k retrieved ids that are relevant."""
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for cid in top if cid in relevant) / len(top)


def recall(retrieved: list[int], relevant: set[int]) -> float:
    """Fraction of relevant ids that were retrieved (anywhere in the list)."""
    if not relevant:
        return 1.0
    return sum(1 for cid in relevant if cid in retrieved) / len(relevant)


def _rank_case(case: dict) -> list[int]:
    return _dense_rank(DEFAULT_MODEL, case["query"], case["corpus_texts"], case["corpus_ids"])


# --- retrieval quality ------------------------------------------------------------------------

PRECISION_AT_5_FLOOR = 0.4  # RATCHET: raise this as retrieval improves.


@pytest.mark.parametrize("case", GOLD, ids=[c["query"][:40] for c in GOLD])
def test_precision_at_5(case: dict) -> None:
    retrieved = _rank_case(case)
    p = precision_at_k(retrieved, set(case["relevant_chunk_ids"]), k=5)
    assert p >= PRECISION_AT_5_FLOOR, (
        f"precision@5 {p:.3f} < {PRECISION_AT_5_FLOOR} for: {case['query']}"
    )


def test_mean_recall() -> None:
    recalls = [recall(_rank_case(c), set(c["relevant_chunk_ids"])) for c in GOLD]
    mean_recall = sum(recalls) / len(recalls)
    assert mean_recall >= 0.5, f"mean recall {mean_recall:.3f} < 0.5"


# --- citation accuracy: every cited span must resolve to a real corpus chunk ------------------


def test_citations() -> None:
    """A citation is valid only if its chunk id exists in that case's corpus.

    Stand-in for the agent's behavior (Week 4): hypotheses cite chunk ids, and a cited span that
    doesn't resolve is a broken citation. Here we assert the labeled relevant ids themselves all
    resolve — the invariant the agent must also satisfy.
    """
    unresolved = 0
    total = 0
    for case in GOLD:
        corpus = set(case["corpus_ids"])
        for cid in case["relevant_chunk_ids"]:
            total += 1
            if cid not in corpus:
                unresolved += 1
    accuracy = 1.0 - (unresolved / total if total else 0.0)
    assert accuracy == 1.0, f"citation accuracy {accuracy:.3f}: {unresolved}/{total} unresolved"


# --- hallucination: extracted facts must appear in the cited source text ----------------------


def _extract_facts(case: dict) -> list[tuple[str, int]]:
    """Stub fact extractor for testing the *invariant*, not the LLM.

    Returns (fact_text, source_chunk_id). In Week 4 the agent produces these; the test below is the
    contract it must satisfy: every extracted fact's text is grounded in its cited chunk.
    """
    facts = []
    id_to_text = dict(zip(case["corpus_ids"], case["corpus_texts"]))
    for cid in case["relevant_chunk_ids"]:
        txt = id_to_text.get(cid, "")
        # first 5 words form a real substring of the source => grounded by construction
        snippet = " ".join(txt.split()[:5])
        if snippet:
            facts.append((snippet, cid))
    return facts


def _norm(text: str) -> str:
    """Collapse runs of whitespace to single spaces.

    SEC filings flatten to single-`\n` lines (see app/rag/chunk.py), so a chunk's text contains
    embedded newlines. `_extract_facts` builds snippets with `text.split()` (whitespace-collapsed),
    so grounding must be checked whitespace-insensitively: a fact is grounded iff its tokens appear
    contiguously in the source, regardless of newline formatting.
    """
    return " ".join(text.split())


def test_hallucination() -> None:
    """Hallucination rate = fraction of extracted facts NOT found in their cited source text."""
    grounded = 0
    total = 0
    id_to_text = {
        cid: t for case in GOLD for cid, t in zip(case["corpus_ids"], case["corpus_texts"])
    }
    for case in GOLD:
        for fact_text, source_id in _extract_facts(case):
            total += 1
            if _norm(fact_text).lower() in _norm(id_to_text.get(source_id, "")).lower():
                grounded += 1
    hallucination_rate = 1.0 - (grounded / total if total else 0.0)
    assert hallucination_rate <= 0.0, f"hallucination rate {hallucination_rate:.3f} > 0"
