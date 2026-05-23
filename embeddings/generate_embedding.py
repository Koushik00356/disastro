import json
from sentence_transformers import SentenceTransformer


INPUT_FILE = "data/cleaned/cleaned_news.json"
OUTPUT_FILE = "data/embedding_data/news_embeddings.json"


model = SentenceTransformer("all-MiniLM-L6-v2")


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    articles = json.load(f)


texts = [article["cleaned_headline"] for article in articles]


embeddings = model.encode(texts)


output_data = []


for article, embedding in zip(articles, embeddings):

    article_data = {
        "headline": article["headline"],
        "cleaned_headline": article["cleaned_headline"],
        "embedding": embedding.tolist()
    }

    output_data.append(article_data)


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4)


print("Embeddings generated.")