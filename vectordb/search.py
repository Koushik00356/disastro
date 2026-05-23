import chromadb
from sentence_transformers import SentenceTransformer


model = SentenceTransformer("all-MiniLM-L6-v2")


client = chromadb.PersistentClient(
    path="vectordb/chroma_storage"
)

collection = client.get_collection(
    name="disaster_news"
)


query = "major flood disaster"


query_embedding = model.encode([query])[0].tolist()


results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)


print(results["documents"])