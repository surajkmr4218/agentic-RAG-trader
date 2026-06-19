from __future__ import annotations

import difflib
import re

import numpy as np
from rapidfuzz import fuzz

from app.models import Filing
from app.rag.embed import embed

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    """Naive sentence splitter on .!? boundaries. Pure."""
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def cosine(a, b) -> float:
    """Cosine similarity. Inputs are L2-normalized by embed(), so dot == cosine."""
    return float(np.dot(a, b))


def COSMETIC(s: str) -> bool:
    """True if a changed sentence is cosmetic (too short, or a bare number)."""
    return len(s) < 25 or s.replace(",", "").replace("$", "").strip().isdigit()


def diff_section(cur: str, prior: str) -> dict:
    """Sentence-level YoY diff of one aligned section.

    Returns:
      semantic_drift: 1 - cosine(embed(cur), embed(prior))  -> meaning shift, 0..~2
      lexical_change: 1 - token_set_ratio/100               -> words shift, 0..1
      added:   non-cosmetic sentences present in cur but not prior (the SIGNAL)
      removed: non-cosmetic sentences present in prior but not cur
    """
    cur_s = sentences(cur)
    pri_s = sentences(prior)

    sm = difflib.SequenceMatcher(a=pri_s, b=cur_s)  # same algorithm git diff but at sentence level
    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            added += [s for s in cur_s[j1:j2] if not COSMETIC(s)] # what was added
        if tag in ("replace", "delete"):
            removed += [s for s in pri_s[i1:i2] if not COSMETIC(s)] # what was removed

    # whole-section meaning + surface shift
    cur_v, pri_v = embed([cur]), embed([prior])
    semantic_drift = 1.0 - cosine(cur_v[0], pri_v[0])
    lexical_change = 1.0 - fuzz.token_set_ratio(cur, prior) / 100.0

    return {
        "semantic_drift": semantic_drift,
        "lexical_change": lexical_change,
        "added": added,
        "removed": removed,
    }

def _norm_item(k: str) -> str:
    """Normalize a section key for YoY alignment, e.g. 'Item 1A.' -> 'item 1a'."""
    return k.strip().lower().rstrip(".")


def evidence_for_filing(current: Filing, prior: Filing, top_k: int = 5) -> list[dict]:
    """Rank YoY-changed passages across aligned same-quarter sections.

    Aligns sections by normalized item key (item 1a <-> item 1a), diffs each,
    scores by semantic_drift + count(added) (additions emphasis), and returns the
    top_k changed passages with resolvable (accession, section) citations.
    """
    cur_secs = {_norm_item(k): (k, v) for k, v in current.sections.items()}
    pri_secs = {_norm_item(k): (k, v) for k, v in prior.sections.items()}

    scored: list[dict] = []
    for key in cur_secs.keys() & pri_secs.keys():  # only sections in BOTH
        cur_label, cur_text = cur_secs[key]
        _, pri_text = pri_secs[key]
        d = diff_section(cur_text, pri_text)
        if not d["added"] and d["semantic_drift"] < 0.01:
            continue  # nothing materially changed in this section
        # additions emphasis: drift + how many new sentences appeared
        score = d["semantic_drift"] + len(d["added"])
        scored.append(
            {
                "score": score,
                "section": cur_label,
                "semantic_drift": d["semantic_drift"],
                "lexical_change": d["lexical_change"],
                "added": d["added"],
                "removed": d["removed"],
                # self-citing: resolves to the CURRENT filing
                "citation": {
                    "accession": current.accession,
                    "section": cur_label,
                },
            }
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]