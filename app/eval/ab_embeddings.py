from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

GOLD = json.loads((Path(__file__).parent / "golden.json").read_text())

CANDIDATES = {
    "bge-small": "BAAI/bge-small-en-v1.5",            # current default (Week 2)
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",  # the alternative (also 384-dim)
}


@lru_cache(maxsize=4)
def _model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


def _precision_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for cid in top if cid in relevant) / len(top)


def _dense_rank(model_name: str, query: str, texts: list[str], ids: list[int]) -> list[int]:
    m = _model(model_name)
    doc_vecs = m.encode(texts, normalize_embeddings=True)
    qv = m.encode([query], normalize_embeddings=True)[0]
    sims = doc_vecs @ qv  # cosine, vectors normalized
    order = np.argsort(-sims)
    return [ids[i] for i in order]


def run_ab(k: int = 5) -> dict[str, float]:
    results: dict[str, float] = {}
    for label, model_name in CANDIDATES.items():
        precisions = []
        for case in GOLD:
            ranked = _dense_rank(model_name, case["query"], case["corpus_texts"], case["corpus_ids"])
            precisions.append(_precision_at_k(ranked, set(case["relevant_chunk_ids"]), k))
        results[label] = round(float(np.mean(precisions)), 4)
    return results


if __name__ == "__main__":
    scores = run_ab()
    winner = max(scores, key=scores.get)
    for label, p in sorted(scores.items(), key=lambda kv: -kv[1]):
        print(f"{label:12s} precision@5 = {p}")
    print(f"WINNER: {winner}")