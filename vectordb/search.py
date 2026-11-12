"""Semantic search over the stored disaster records.

Run directly with:  python -m vectordb.search "major flood disaster"
"""

import sys

from embeddings.generate_embedding import embed_texts
from vectordb.store_embedding import get_collection


def build_filter(disaster_type=None, severity=None, source_type=None):

    conditions = [
        {field: value}
        for field, value in (
            ("disaster_type", disaster_type),
            ("severity", severity),
            ("source_type", source_type),
        )
        if value
    ]

    if not conditions:
        return None

    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def search(query, n_results=5, **filters):
    """Return the records most similar to the query, best match first."""

    collection = get_collection()

    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=embed_texts([query]),
        n_results=n_results,
        where=build_filter(**filters),
    )

    hits = []

    for doc_id, document, metadata, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append(
            {
                "id": doc_id,
                "text": document,
                # Squared L2 distance between unit vectors -> cosine similarity.
                "score": round(1 - distance / 2, 3),
                **(metadata or {}),
            }
        )

    return hits


if __name__ == "__main__":

    query = " ".join(sys.argv[1:]) or "major flood disaster"

    for hit in search(query):
        print(f"[{hit['score']:.2f}] ({hit.get('severity', '?')}) {hit.get('headline', hit['text'])}")
