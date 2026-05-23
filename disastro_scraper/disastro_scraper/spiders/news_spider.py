import scrapy
from datetime import datetime


class NewsSpider(scrapy.Spider):

    name = "bbc_news"

    start_urls = [
        "https://www.bbc.com/news"
    ]

    def parse(self, response):

        headlines = response.xpath("//h2/text()").getall()

        for idx, headline in enumerate(headlines):

            text = headline.strip()

            if len(text) > 15:

                yield {
                    "id": idx + 1,
                    "headline": text,
                    "source": "BBC News",
                    "scraped_at": str(datetime.now())
                }