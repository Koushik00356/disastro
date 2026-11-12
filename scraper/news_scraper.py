"""Scrape news headlines from the BBC front page and a set of RSS feeds.

Run directly with:  python -m scraper.news_scraper
"""

import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from utils.helpers import (
    get_logger,
    http_get,
    make_id,
    normalize_date,
    now_iso,
    save_json,
    strip_html,
)


log = get_logger("news_scraper")


def build_article(headline, source, url="", summary="", published_at=None):

    return {
        "id": make_id(source, url or headline),
        "headline": headline,
        "summary": summary,
        "source": source,
        "source_type": "news",
        "url": url,
        "published_at": published_at,
        "scraped_at": now_iso(),
    }


def parse_bbc_homepage(page_html):

    soup = BeautifulSoup(page_html, "html.parser")

    articles = []

    for headline in soup.find_all("h2"):

        text = headline.get_text(strip=True)

        if len(text) <= 15:
            continue

        link = headline.find_parent("a")
        url = urljoin(config.BBC_NEWS_URL, link["href"]) if link and link.get("href") else ""

        articles.append(build_article(text, "BBC News", url=url))

    return articles


def parse_rss(xml_text, source_name):

    root = ET.fromstring(xml_text)

    articles = []

    for item in root.iter("item"):

        headline = strip_html(item.findtext("title"))

        if not headline:
            continue

        source = source_name
        publisher = item.findtext("source")

        # Aggregator feeds title every item "Headline - Publisher".
        if publisher:
            source = publisher.strip()
            suffix = f" - {source}"
            if headline.endswith(suffix):
                headline = headline[: -len(suffix)]

        summary = strip_html(item.findtext("description"))

        # ...and their description just repeats the headline.
        if publisher or summary == headline:
            summary = ""

        articles.append(
            build_article(
                headline,
                source,
                url=(item.findtext("link") or "").strip(),
                summary=summary[:600],
                published_at=normalize_date(item.findtext("pubDate")),
            )
        )

    return articles


def scrape_news():

    articles = []

    try:
        response = http_get(config.BBC_NEWS_URL)
        found = parse_bbc_homepage(response.text)
        log.info("BBC front page: %d headlines", len(found))
        articles.extend(found)
    except Exception as error:
        log.warning("BBC front page failed: %s", error)

    for feed in config.RSS_FEEDS:

        try:
            response = http_get(feed["url"])
            found = parse_rss(response.content, feed["name"])
            log.info("%s RSS: %d articles", feed["name"], len(found))
            articles.extend(found)
        except Exception as error:
            log.warning("%s RSS failed: %s", feed["name"], error)

    return articles


def run():

    articles = scrape_news()

    save_json(config.RAW_NEWS_FILE, articles)

    log.info("Saved %d articles to %s", len(articles), config.RAW_NEWS_FILE)

    return articles


if __name__ == "__main__":
    run()
