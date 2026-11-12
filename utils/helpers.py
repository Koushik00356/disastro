"""Small helpers shared by every stage of the pipeline."""

import hashlib
import html
import json
import logging
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

import config


def get_logger(name):

    logger = logging.getLogger(name)

    if not logging.getLogger().handlers:
        # Windows consoles default to cp1252 and choke on scraped unicode.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    return logger


def load_json(path, default=None):

    path = Path(path)

    if not path.exists():
        return [] if default is None else default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data, indent=4):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def http_get(url, **kwargs):

    headers = {"User-Agent": config.USER_AGENT, **kwargs.pop("headers", {})}

    response = requests.get(
        url,
        headers=headers,
        timeout=kwargs.pop("timeout", config.REQUEST_TIMEOUT),
        **kwargs,
    )
    response.raise_for_status()

    return response


def make_id(*parts):
    """Stable id for a record, so re-scraping the same item never duplicates it."""

    key = "|".join(str(p).strip().lower() for p in parts if p)

    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def now_iso():

    return to_iso(datetime.now(timezone.utc))


def to_iso(dt):

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(value):
    """Parse RSS (RFC 822), ISO 8601 or epoch-millisecond dates into a datetime (UTC)."""

    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

    value = str(value).strip()

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def normalize_date(value):

    dt = parse_date(value)

    return to_iso(dt) if dt else None


def strip_html(text):

    if not text:
        return ""

    text = re.sub(r"<br\s*/?>|</p>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    return re.sub(r"\s+", " ", text).strip()
