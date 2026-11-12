"""Merge every raw source, keep only disaster-related items and clean the text.

Reads all JSON files in data/raw/, tags each record with a disaster type,
drops non-disaster and expired records, and merges the result into
data/cleaned/cleaned_news.json.

Run directly with:  python -m preprocessing.clean_text
"""

import re
from datetime import datetime, timedelta, timezone

import config
from utils.helpers import (
    get_logger,
    load_json,
    make_id,
    normalize_date,
    now_iso,
    parse_date,
    save_json,
)


log = get_logger("clean_text")


DISASTER_PATTERNS = {
    disaster_type: re.compile(r"\b(?:" + "|".join(keywords) + r")\b", re.IGNORECASE)
    for disaster_type, keywords in config.DISASTER_KEYWORDS.items()
}

NON_DISASTER_PATTERN = re.compile(
    r"\b(?:" + "|".join(config.NON_DISASTER_PATTERNS) + r")", re.IGNORECASE
)
SOCIAL_SIGNAL_PATTERN = re.compile(
    r"\b(?:" + "|".join(config.SOCIAL_SIGNAL_PATTERNS) + r")\b", re.IGNORECASE
)

# Fields computed by later stages that must survive a re-scrape of the same item.
PRESERVED_FIELDS = ("severity", "severity_score", "severity_method")


def clean_headline(headline):

    headline = headline.lower()

    headline = re.sub(r"[^a-zA-Z0-9\s]", "", headline)

    headline = re.sub(r"\s+", " ", headline).strip()

    return headline


def detect_disaster_type(text):
    """Return the first disaster type whose keywords appear in the text, else None."""

    if NON_DISASTER_PATTERN.search(text):
        return None

    for disaster_type, pattern in DISASTER_PATTERNS.items():

        if pattern.search(text):
            return disaster_type

    return None


def normalize_record(record):
    """Bring a raw record (including ones from the old Scrapy spider) to the common shape."""

    headline = re.sub(r"\s+", " ", str(record.get("headline") or "")).strip()

    if not headline:
        return None

    source = record.get("source") or "unknown"
    summary = re.sub(r"\s+", " ", str(record.get("summary") or "")).strip()

    article = dict(record)

    # Old records carry a per-run counter as id; replace it with a stable hash.
    if not isinstance(article.get("id"), str):
        article["id"] = make_id(source, record.get("url") or headline)

    article["headline"] = headline
    article["summary"] = summary
    article["source"] = source
    article["source_type"] = record.get("source_type") or "news"
    article["url"] = record.get("url") or ""
    article["scraped_at"] = normalize_date(record.get("scraped_at")) or now_iso()
    article["published_at"] = normalize_date(record.get("published_at")) or article["scraped_at"]

    # Text that gets embedded: headline plus summary when it adds something.
    if not summary or summary == headline:
        article["text"] = headline
    elif summary.startswith(headline.rstrip(".")):
        article["text"] = summary
    else:
        article["text"] = f"{headline}. {summary}"

    # Agency events arrive with a type; everything else is tagged by keyword.
    if article["source_type"] != "api":
        article["disaster_type"] = detect_disaster_type(article["text"])

    if not article.get("disaster_type"):
        return None

    if article["source_type"] == "social" and not SOCIAL_SIGNAL_PATTERN.search(article["text"]):
        return None

    article["cleaned_headline"] = clean_headline(headline)

    return article


def load_raw_records():

    records = []

    for path in sorted(config.RAW_DIR.glob("*.json")):

        try:
            records.extend(load_json(path))
        except ValueError as error:
            log.warning("Skipping unreadable file %s: %s", path.name, error)

    return records


def clean_records(raw_records, existing=None, now=None):

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=config.RETENTION_DAYS)

    merged = {}

    # Existing records go through the same normalisation, which also weeds out
    # anything written by older versions of this script.
    for record in list(existing or []) + list(raw_records):

        article = normalize_record(record)

        if article is None:
            continue

        previous = merged.get(article["id"])

        if previous and previous.get("text") == article["text"]:
            for field in PRESERVED_FIELDS:
                if field in previous:
                    article[field] = previous[field]

        merged[article["id"]] = article

    cleaned = []
    seen_headlines = set()

    for article in sorted(merged.values(), key=lambda a: a["published_at"], reverse=True):

        if parse_date(article["published_at"]) < cutoff:
            continue

        # The same story syndicated by several outlets is kept once.
        if article["cleaned_headline"] in seen_headlines:
            continue

        seen_headlines.add(article["cleaned_headline"])
        cleaned.append(article)

    return cleaned


def run():

    raw_records = load_raw_records()

    cleaned = clean_records(raw_records, existing=load_json(config.CLEANED_FILE))

    save_json(config.CLEANED_FILE, cleaned)

    log.info(
        "Cleaned news saved: %d disaster records kept (from %d raw records).",
        len(cleaned),
        len(raw_records),
    )

    return cleaned


if __name__ == "__main__":
    run()
