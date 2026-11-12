"""Generate sentence embeddings for the cleaned records.

Embeddings already computed for an unchanged text are reused, so each run
only encodes new records.

Run directly with:  python -m embeddings.generate_embedding
"""

import config
from utils.helpers import get_logger, load_json, save_json


log = get_logger("embeddings")


_model = None


def get_model():

    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBEDDING_MODEL)

    return _model


def embed_texts(texts):

    embeddings = get_model().encode(texts, normalize_embeddings=True)

    return [embedding.tolist() for embedding in embeddings]


def generate_embeddings(articles, existing=None):

    cached = {
        item["id"]: item["embedding"]
        for item in (existing or [])
        if "id" in item and item.get("text")
    }
    cached_text = {item["id"]: item["text"] for item in (existing or []) if "id" in item and item.get("text")}

    new_articles = [
        article for article in articles if cached_text.get(article["id"]) != article["text"]
    ]

    if new_articles:
        new_embeddings = embed_texts([article["text"] for article in new_articles])

        for article, embedding in zip(new_articles, new_embeddings):
            cached[article["id"]] = embedding

    output_data = []

    for article in articles:

        article_data = {
            "id": article["id"],
            "headline": article["headline"],
            "cleaned_headline": article["cleaned_headline"],
            "text": article["text"],
            "embedding": cached[article["id"]],
        }

        output_data.append(article_data)

    return output_data, len(new_articles)


def run():

    articles = load_json(config.CLEANED_FILE)

    output_data, new_count = generate_embeddings(articles, existing=load_json(config.EMBEDDINGS_FILE))

    save_json(config.EMBEDDINGS_FILE, output_data, indent=None)

    log.info("Embeddings generated: %d total, %d new.", len(output_data), new_count)

    return output_data


if __name__ == "__main__":
    run()
