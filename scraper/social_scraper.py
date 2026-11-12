"""Collect public social media posts about disasters.

Uses Mastodon's public hashtag timelines, which need no account or API key.

Run directly with:  python -m scraper.social_scraper
"""

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


log = get_logger("social_scraper")


def parse_mastodon(statuses, hashtag):

    posts = []

    for status in statuses:

        # Skip boosts, replies and non-English posts.
        if status.get("reblog") or status.get("in_reply_to_id"):
            continue

        if status.get("language") not in (None, "en"):
            continue

        text = strip_html(status.get("content"))

        if len(text) < 30:
            continue

        account = (status.get("account") or {}).get("acct", "unknown")
        headline = text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + "..."

        posts.append(
            {
                "id": make_id("mastodon", status.get("id")),
                "headline": headline,
                "summary": text[:600],
                "source": f"Mastodon @{account}",
                "source_type": "social",
                "url": status.get("url") or "",
                "published_at": normalize_date(status.get("created_at")),
                "scraped_at": now_iso(),
                "hashtag": hashtag,
            }
        )

    return posts


def fetch_hashtag(hashtag):

    url = f"{config.MASTODON_INSTANCE}/api/v1/timelines/tag/{hashtag}"

    response = http_get(url, params={"limit": config.MASTODON_POSTS_PER_TAG})

    return parse_mastodon(response.json(), hashtag)


def scrape_social():

    posts = {}

    for hashtag in config.MASTODON_HASHTAGS:

        try:
            found = fetch_hashtag(hashtag)
            log.info("#%s: %d posts", hashtag, len(found))
            for post in found:
                posts.setdefault(post["id"], post)
        except Exception as error:
            log.warning("#%s failed: %s", hashtag, error)

    return list(posts.values())


def run():

    posts = scrape_social()

    save_json(config.RAW_SOCIAL_FILE, posts)

    log.info("Saved %d posts to %s", len(posts), config.RAW_SOCIAL_FILE)

    return posts


if __name__ == "__main__":
    run()
