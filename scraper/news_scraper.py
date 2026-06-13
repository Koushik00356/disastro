import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

url = "https://www.bbc.com/news"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

headlines = soup.find_all("h2")

articles = []

for idx, headline in enumerate(headlines[:15]):

    text = headline.get_text(strip=True)

    if text:

        article_data = {
            "id": idx + 1,
            "headline": text,
            "source": "BBC News",
            "category": "general",
            "scraped_at": str(datetime.now())
        }

        articles.append(article_data)

        print(f"{idx+1}. {text}")

# Save JSON
with open("data/raw/bbc_news.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, indent=4, ensure_ascii=False)


print(f"\nScraped {len(articles)} articles from BBC News.")
print("\nSaved data to disastro_model/data/raw/bbc_news.json")
