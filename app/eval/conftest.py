from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.ab_embeddings import _dense_rank
from app.eval.test_rag import precision_at_k, recall

GOLD = json.loads((Path(__file__).parent / "golden.json").read_text())


@pytest.fixture(scope="session", autouse=True)
def _print_eval_metrics():
    yield  # run after the suite
    ranked = [
        (_dense_rank("BAAI/bge-small-en-v1.5", c["query"], c["corpus_texts"], c["corpus_ids"]), c)
        for c in GOLD
    ]
    p_at_5 = sum(
        precision_at_k(r, set(c["relevant_chunk_ids"]), 5) for r, c in ranked
    ) / len(ranked)
    rec = sum(recall(r, set(c["relevant_chunk_ids"])) for r, c in ranked) / len(ranked)
    # citation accuracy and hallucination rate are asserted exactly in test_rag.py:
    print("\n================ RAG EVAL METRICS ================")
    print(f"  precision@5         : {p_at_5:.3f}")
    print(f"  mean recall         : {rec:.3f}")
    #print("  citation accuracy   : 1.000  (every cited span resolves — test_citations)")
    #print("  hallucination rate  : 0.000  (extracted facts grounded — test_hallucination)")
    print(f"  golden set size     : {len(GOLD)} queries")
    print("==================================================")
