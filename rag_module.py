"""
GreenGuard AI - RAG (Retrieval-Augmented Generation) Module

Builds a local FAISS index over the `medicines` table descriptions so the
AI assistant can retrieve grounded context before answering - instead of
hallucinating facts about medicines.

Runs FULLY OFFLINE (sentence-transformers + FAISS are both local),
regardless of whether the final answer generation uses Granite (online)
or a local model (offline). This is what makes RAG itself
connectivity-independent.

Requires:
    pip install sentence-transformers faiss-cpu numpy
"""

import os
import pickle
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    _RAG_LIBS_AVAILABLE = True
except ImportError:
    _RAG_LIBS_AVAILABLE = False

from config import EMBEDDING_MODEL_NAME, FAISS_INDEX_PATH
from database import db_session

_embedder = None
_index = None
_doc_lookup = []  # list of dicts, index i corresponds to FAISS vector i

_META_PATH = FAISS_INDEX_PATH + ".meta.pkl"


def _get_embedder():
    global _embedder
    if _embedder is None:
        if not _RAG_LIBS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers / faiss not installed. Run: "
                "pip install sentence-transformers faiss-cpu --break-system-packages"
            )
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def build_index():
    """
    Pull every medicine description from SQLite, embed it, and build a
    FAISS index. Call this once after seeding/updating the medicines table.
    """
    embedder = _get_embedder()

    with db_session() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT id, name, manufacturer, category, license_number,
                              certifying_body, batch_format_regex, description
                       FROM medicines""")
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        raise RuntimeError("No medicines in database - run seed_data.py first.")

    texts = [r["description"] for r in rows]
    embeddings = embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized vectors = cosine sim
    index.add(embeddings.astype(np.float32))

    os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(_META_PATH, "wb") as f:
        pickle.dump(rows, f)

    print(f"Built FAISS index with {len(rows)} medicine records -> {FAISS_INDEX_PATH}")
    return index, rows


def _load_index():
    global _index, _doc_lookup
    if _index is None:
        if not os.path.exists(FAISS_INDEX_PATH):
            _index, _doc_lookup = build_index()
        else:
            _index = faiss.read_index(FAISS_INDEX_PATH)
            with open(_META_PATH, "rb") as f:
                _doc_lookup = pickle.load(f)
    return _index, _doc_lookup


def retrieve(query: str, top_k: int = 3) -> list:
    """
    Return the top_k most relevant medicine records for a natural-language
    query (e.g. "is this Ashwagandha capsule genuine?").
    """
    embedder = _get_embedder()
    index, doc_lookup = _load_index()

    query_vec = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    scores, indices = index.search(query_vec.astype(np.float32), top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        doc = dict(doc_lookup[idx])
        doc["similarity_score"] = float(score)
        results.append(doc)
    return results


def build_context_string(retrieved_docs: list) -> str:
    """Format retrieved medicine records into a context block for the LLM prompt."""
    if not retrieved_docs:
        return "No matching verified medicine found in the database."

    lines = []
    for doc in retrieved_docs:
        lines.append(
            f"- {doc['name']} ({doc['manufacturer']}, {doc['category']}): "
            f"{doc['description']} [License: {doc['license_number']} / "
            f"{doc['certifying_body']}]"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    build_index()
    demo = retrieve("Is this ashwagandha capsule genuine?")
    for d in demo:
        print(d["name"], d["similarity_score"])
