import chromadb

from transformers import pipeline

from sentence_transformers import SentenceTransformer


embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


generator = pipeline(
    "text-generation",
    model="google/flan-t5-small"
)


client = chromadb.PersistentClient(
    path="vectordb/chroma_storage"
)


collection = client.get_collection(
    name="disaster_news"
)


query = "major flood disaster"


query_embedding = embedding_model.encode(
    [query]
)[0].tolist()


results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)


retrieved_docs = results["documents"][0]


context = "\n".join(retrieved_docs)


prompt = f"""
Context:
{context}

Question:
{query}

Summarize disaster situation.
"""


response = generator(
    prompt,
    max_length=150
)


print("\nGenerated Response:\n")

print(response[0]["generated_text"])