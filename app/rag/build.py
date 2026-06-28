from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Filing
from app.rag.diff import _norm_item, diff_section
from app.rag.retrieve import hybrid

# Standing analyst query when the caller passes none. Broad on purpose: it drives hybrid()'s
# relevance ranking, so it must surface valuation-relevant passages across the whole filing.
DEFAULT_QUERY = (
    "material year-over-year changes to risk factors, MD&A outlook, guidance, "
    "litigation, and liquidity that affect the equity's value"
)


def _latest_two_same_form(session: Session, ticker: str) -> tuple[Filing | None, Filing | None]:
    """Current filing + the prior filing of the SAME form (10-K<->10-K, 10-Q<->10-Q).

    diff_section aligns same-quarter sections, so prior MUST match current's form. Returns
    (current, prior); prior is None when there's no comparable earlier filing yet.
    """
    rows = (
        session.execute(
            select(Filing).where(Filing.ticker == ticker.upper()).order_by(Filing.filed_at.desc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return None, None
    current = rows[0]
    prior = next((f for f in rows[1:] if f.form_type == current.form_type), None)
    return current, prior


def build_diff_bundle(
    session: Session, ticker: str, query: str | None = None, k: int = 8
) -> dict:
    """Option A evidence bundle: relevance includes, diff annotates.

    1. corpus = ALL of the ticker's stored chunks (every section, changed or not).
    2. hybrid() ranks that corpus by `query` -> top-k relevant chunks (the INCLUSION step).
    3. diff EVERY aligned section of current vs prior-year same-form filing into a
       section -> delta map (NO [:top_k] truncation -- truncation was the query-blind gap).
    4. attach each section's delta onto the retrieved chunks from that section.
    Returns the bundle; passages carry top-level (accession, section) for citation checks.
    """
    ticker = ticker.upper()
    query = query or DEFAULT_QUERY

    # 1 — corpus: all chunks for the ticker; keep section + accession for annotation/citations.
    # Join Filing for ticker + accession (real columns) rather than poking into the generic-JSON
    # `Chunk.meta` — `.astext` is a Postgres-JSONB-only operator and isn't available here.
    rows = session.execute(
        select(Chunk.id, Chunk.text, Chunk.section, Filing.accession)
        .join(Filing, Chunk.filing_id == Filing.id)
        .where(Filing.ticker == ticker)
    ).all()
    if not rows:
        return {
            "ticker": ticker,
            "query": query,
            "accession": None,
            "passages": [],
            "changed_sections": [],
        }
    corpus_ids = [r.id for r in rows]
    corpus_texts = [r.text for r in rows]
    id_to_text = dict(zip(corpus_ids, corpus_texts))
    meta_by_id = {
        r.id: {"section": r.section, "accession": r.accession} for r in rows
    }

    # 2 — query-relevant retrieval over the WHOLE corpus (this gates inclusion)
    hits = hybrid(session, query, corpus_texts, corpus_ids, k=k, ticker=ticker)

    # 3 — diff map for ALL materially-changed aligned sections (query-blind change signal)
    current, prior = _latest_two_same_form(session, ticker)
    diff_by_section: dict[str, dict] = {}
    if current is not None and prior is not None:
        cur_secs = {_norm_item(kk): vv for kk, vv in current.sections.items()}
        pri_secs = {_norm_item(kk): vv for kk, vv in prior.sections.items()}
        for key in cur_secs.keys() & pri_secs.keys():
            d = diff_section(cur_secs[key], pri_secs[key])
            if not d["added"] and d["semantic_drift"] < 0.01:
                continue  # nothing materially changed -> no annotation
            diff_by_section[key] = d

    # 4 — assemble: relevance included these; diff annotates the ones that moved
    passages = []
    for cid, score in hits:
        m = meta_by_id.get(cid, {})
        section = m.get("section")
        delta = diff_by_section.get(_norm_item(section or ""))
        passages.append(
            {
                "chunk_id": cid,
                "accession": m.get("accession"),  # TOP-LEVEL: critic/guardrail read these
                "section": section,
                "text": id_to_text.get(cid, ""),
                "rerank_score": score,
                "diff": (
                    {
                        k2: delta[k2]
                        for k2 in ("semantic_drift", "lexical_change", "added", "removed")
                    }
                    if delta
                    else None  # retrieved for relevance but didn't change YoY
                ),
            }
        )

    return {
        "ticker": ticker,
        "query": query,
        "accession": current.accession if current else None,
        "passages": passages,  # citation source for hypothesis/critic/guardrail
        "changed_sections": sorted(diff_by_section),  # audit: everything that moved this year
    }
