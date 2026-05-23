import json
import re


INPUT_FILE = "disastro_scraper/bbc_news.json"
OUTPUT_FILE = "data/cleaned/cleaned_news.json"


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    articles = json.load(f)


cleaned_articles = []


for article in articles:

    headline = article["headline"]

    headline = headline.lower()

    headline = re.sub(r"[^a-zA-Z0-9\s]", "", headline)

    headline = re.sub(r"\s+", " ", headline).strip()

    article["cleaned_headline"] = headline

    cleaned_articles.append(article)


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(cleaned_articles, f, indent=4, ensure_ascii=False)


print("Cleaned news saved.")