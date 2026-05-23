import json
import chromadb


INPUT_FILE = "data/embedding_data/news_embeddings.json"


client = chromadb.PersistentClient(path="vectordb/chroma_storage")

collection = client.get_or_create_collection(
    name="disaster_news"
)


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    articles = json.load(f)


for idx, article in enumerate(articles):

    collection.add(
        ids=[str(idx)],
        embeddings=[article["embedding"]],
        documents=[article["headline"]]
    )


print("Embeddings stored in ChromaDB.")