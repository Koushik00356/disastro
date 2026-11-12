"""Store the embeddings and record metadata in ChromaDB.

The collection is kept in sync with the cleaned file: new records are
upserted and records that expired (or predate this pipeline) are removed.

Run directly with:  python -m vectordb.store_embedding
"""

import chromadb

import config
from utils.helpers import get_logger, load_json


log = get_logger("vectordb")


METADATA_FIELDS = (
    "headline", "source", "source_type", "url", "published_at", "disaster_type",
    "severity", "severity_score", "latitude", "longitude", "magnitude", "location",
)

BATCH_SIZE = 200


def get_collection():

    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))

    return client.get_or_create_collection(name=config.COLLECTION_NAME)


def build_metadata(article):
    """ChromaDB metadata cannot hold None, so missing fields are left out."""

    return {
        field: article[field]
        for field in METADATA_FIELDS
        if article.get(field) not in (None, "")
    }


def store_embeddings(articles, embedded):

    collection = get_collection()

    articles_by_id = {article["id"]: article for article in articles}
    embedded = [item for item in embedded if item["id"] in articles_by_id]

    for start in range(0, len(embedded), BATCH_SIZE):

        batch = embedded[start:start + BATCH_SIZE]

        collection.upsert(
            ids=[item["id"] for item in batch],
            embeddings=[item["embedding"] for item in batch],
            documents=[item["text"] for item in batch],
            metadatas=[build_metadata(articles_by_id[item["id"]]) for item in batch],
        )

    current_ids = {item["id"] for item in embedded}
    stale_ids = [doc_id for doc_id in collection.get(include=[])["ids"] if doc_id not in current_ids]

    if stale_ids:
        collection.delete(ids=stale_ids)

    return len(embedded), len(stale_ids)


def run():

    stored, removed = store_embeddings(
        load_json(config.CLEANED_FILE),
        load_json(config.EMBEDDINGS_FILE),
    )

    log.info("Embeddings stored in ChromaDB: %d records (%d stale removed).", stored, removed)


if __name__ == "__main__":
    run()
