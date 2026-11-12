"""Offline tests for the parsing, cleaning, severity and alert logic.

Run with:  python -m pytest tests
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.alert_manager import process_alerts
from preprocessing.clean_text import clean_headline, clean_records, detect_disaster_type
from scraper.api_fetcher import parse_eonet, parse_gdacs, parse_usgs
from scraper.news_scraper import parse_rss
from scraper.social_scraper import parse_mastodon
from summarizer.severity_classifier import classify_records, rule_based_severity, structured_severity
from utils.helpers import make_id, normalize_date, strip_html
from vectordb.search import build_filter


NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Floods kill 12 in northern Vietnam</title>
    <link>https://example.com/floods</link>
    <description>&lt;p&gt;Heavy rain triggered flash floods.&lt;/p&gt;</description>
    <pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Wildfire spreads near Athens - Example Times</title>
    <link>https://example.com/fire</link>
    <description>Wildfire spreads near Athens</description>
    <pubDate>Thu, 12 Nov 2026 09:00:00 GMT</pubDate>
    <source url="https://example.com">Example Times</source>
  </item>
</channel></rss>"""

GDACS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:gdacs="http://www.gdacs.org" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
<channel><item>
  <title>Red earthquake (Magnitude 7.1M) in Chile</title>
  <description>An earthquake occurred in Chile.</description>
  <link>http://www.gdacs.org/report.aspx?eventtype=EQ&amp;eventid=1</link>
  <pubDate>Thu, 12 Nov 2026 07:00:00 GMT</pubDate>
  <guid isPermaLink="false">EQ1</guid>
  <geo:Point><geo:lat>-33.4</geo:lat><geo:long>-70.6</geo:long></geo:Point>
  <gdacs:eventtype>EQ</gdacs:eventtype>
  <gdacs:alertlevel>Red</gdacs:alertlevel>
  <gdacs:severity unit="M" value="7.1">Magnitude 7.1M</gdacs:severity>
  <gdacs:country>Chile</gdacs:country>
</item></channel></rss>"""

USGS = {
    "features": [
        {
            "id": "us7000abcd",
            "properties": {
                "mag": 5.8, "place": "10 km S of Town", "time": 1794477600000,
                "url": "https://earthquake.usgs.gov/x", "alert": None, "tsunami": 0,
                "title": "M 5.8 - 10 km S of Town",
            },
            "geometry": {"coordinates": [100.5, -2.5, 30.0]},
        }
    ]
}

EONET = {
    "events": [
        {
            "id": "EONET_1", "title": "Typhoon Test", "description": None,
            "link": "https://eonet.gsfc.nasa.gov/api/v3/events/EONET_1",
            "categories": [{"id": "severeStorms", "title": "Severe Storms"}],
            "sources": [{"id": "JTWC", "url": "https://example.com/jtwc"}],
            "geometry": [
                {"date": "2026-11-10T00:00:00Z", "type": "Point", "coordinates": [130.0, 15.0]},
                {"date": "2026-11-11T00:00:00Z", "type": "Point", "coordinates": [128.0, 16.0],
                 "magnitudeValue": 90, "magnitudeUnit": "kts"},
            ],
        },
        {"id": "EONET_2", "title": "Iceberg", "categories": [{"id": "seaLakeIce", "title": "Sea Ice"}], "geometry": []},
    ]
}


def raw(headline, **fields):
    record = {"headline": headline, "source": "Test", "published_at": "2026-11-12T08:00:00Z"}
    record.update(fields)
    return record


def test_helpers():
    assert make_id("BBC", "Title") == make_id("bbc ", "title")
    assert make_id("a") != make_id("b")
    assert normalize_date("Thu, 12 Nov 2026 08:00:00 GMT") == "2026-11-12T08:00:00Z"
    assert normalize_date("2026-11-12T08:00:00.000Z") == "2026-11-12T08:00:00Z"
    assert normalize_date(1794477600000).startswith("2026-11-12")
    assert normalize_date("not a date") is None
    assert strip_html("<p>Hello &amp; <b>bye</b></p>") == "Hello & bye"


def test_parse_rss():
    articles = parse_rss(RSS, "Feed")
    assert [a["headline"] for a in articles] == ["Floods kill 12 in northern Vietnam", "Wildfire spreads near Athens"]
    assert articles[0]["summary"] == "Heavy rain triggered flash floods."
    assert articles[0]["source"] == "Feed"
    assert articles[1]["source"] == "Example Times"
    assert articles[1]["summary"] == ""
    assert articles[0]["published_at"] == "2026-11-12T08:00:00Z"


def test_parse_api_sources():
    quake = parse_usgs(USGS)[0]
    assert quake["disaster_type"] == "earthquake"
    assert (quake["latitude"], quake["longitude"], quake["magnitude"]) == (-2.5, 100.5, 5.8)

    alert = parse_gdacs(GDACS)[0]
    assert alert["alert_level"] == "red"
    assert alert["magnitude"] == 7.1
    assert alert["location"] == "Chile"
    assert alert["latitude"] == -33.4

    storms = parse_eonet(EONET)
    assert len(storms) == 1
    assert storms[0]["disaster_type"] == "cyclone"
    assert (storms[0]["latitude"], storms[0]["longitude"]) == (16.0, 128.0)
    assert "90 kts" in storms[0]["summary"]


def test_parse_mastodon():
    statuses = [
        {"id": "1", "content": "<p>Strong earthquake felt across the whole region this morning</p>",
         "language": "en", "url": "https://m.example/1", "created_at": "2026-11-12T08:00:00.000Z",
         "account": {"acct": "user"}},
        {"id": "2", "content": "<p>too short</p>", "language": "en", "account": {}},
        {"id": "3", "content": "<p>Ein starkes Erdbeben hat heute die Region getroffen</p>", "language": "de", "account": {}},
        {"id": "4", "content": "<p>Boosted earthquake post that should be skipped</p>", "language": "en",
         "reblog": {"id": "9"}, "account": {}},
    ]
    posts = parse_mastodon(statuses, "earthquake")
    assert len(posts) == 1
    assert posts[0]["source"] == "Mastodon @user"
    assert posts[0]["source_type"] == "social"


def test_detect_disaster_type():
    assert detect_disaster_type("Flash floods hit Mumbai") == "flood"
    assert detect_disaster_type("Magnitude 6 quake strikes Japan") == "earthquake"
    assert detect_disaster_type("Typhoon makes landfall") == "cyclone"
    assert detect_disaster_type("Bushfires rage in Australia") == "wildfire"
    assert detect_disaster_type("Rubio says Cuba is threat to US") is None
    assert detect_disaster_type("Minister fired over leak") is None
    assert detect_disaster_type("Republicans assess damage from 'blue tsunami'") is None
    assert detect_disaster_type("Party wins by a landslide") is None
    assert detect_disaster_type("Cyclone hoops preview: Iowa State at home") is None
    assert detect_disaster_type("Flood of the century hits Valencia") == "flood"


def test_social_posts_need_an_event_signal():
    posts = [
        raw("Love this song #hurricane #rock", source_type="social"),
        raw("Flash flood warning issued for the valley", source_type="social"),
    ]
    cleaned = clean_records(posts, now=NOW)
    assert [a["headline"] for a in cleaned] == ["Flash flood warning issued for the valley"]


def test_clean_headline():
    assert clean_headline("  Floods: 12 dead, 'many' missing!  ") == "floods 12 dead many missing"


def test_clean_records_filters_and_dedupes():
    records = [
        raw("Floods kill 12 in Vietnam", url="https://a.example/1"),
        raw("Floods kill 12 in Vietnam!", url="https://b.example/1", source="Other"),
        raw("Election results announced"),
        raw("Earthquake hits region", published_at="2026-10-01T00:00:00Z"),
        {"id": 3, "headline": "Wildfire forces evacuations", "source": "BBC News",
         "scraped_at": "2026-11-12 09:00:00.123456"},
    ]
    cleaned = clean_records(records, now=NOW)

    assert sorted(a["headline"] for a in cleaned) == ["Floods kill 12 in Vietnam", "Wildfire forces evacuations"]
    assert all(isinstance(a["id"], str) for a in cleaned)
    assert {a["disaster_type"] for a in cleaned} == {"flood", "wildfire"}


def test_clean_records_keeps_existing_severity():
    first = clean_records([raw("Floods kill 12 in Vietnam", url="https://a.example/1")], now=NOW)
    first[0]["severity"] = "high"

    second = clean_records([raw("Floods kill 12 in Vietnam", url="https://a.example/1")], existing=first, now=NOW)

    assert len(second) == 1
    assert second[0]["severity"] == "high"


def test_undated_records_keep_first_seen_time():
    first = clean_records(
        [{"headline": "Floods hit town", "source": "BBC News", "scraped_at": "2026-11-11T08:00:00Z"}], now=NOW
    )
    second = clean_records(
        [{"headline": "Floods hit town", "source": "BBC News", "scraped_at": "2026-11-12T08:00:00Z"}],
        existing=first, now=NOW,
    )
    assert second[0]["published_at"] == "2026-11-11T08:00:00Z"


def test_severity():
    assert structured_severity({"alert_level": "red"}) == "high"
    assert structured_severity({"disaster_type": "earthquake", "magnitude": 4.8}) == "low"
    assert structured_severity({"disaster_type": "earthquake", "magnitude": 6.0, "alert_level": "green"}) == "medium"
    assert structured_severity({"disaster_type": "flood"}) is None

    assert rule_based_severity("Floods kill 12 in Vietnam") == "high"
    assert rule_based_severity("Thousands evacuated as river rises") == "high"
    assert rule_based_severity("Residents evacuated as river rises") == "medium"
    assert rule_based_severity("Light rain expected") == "low"

    records = [
        {"text": "M 7.0 quake", "disaster_type": "earthquake", "magnitude": 7.0},
        {"text": "Residents evacuated as river rises", "disaster_type": "flood"},
        {"text": "Typhoon", "disaster_type": "cyclone", "wind_kts": 100},
        {"text": "Floods kill 12", "disaster_type": "flood", "severity": "low", "severity_method": "zero-shot"},
    ]
    classify_records(records, mode="rules")
    assert [r["severity"] for r in records] == ["high", "medium", "high", "high"]
    assert records[0]["severity_method"] == "structured"


def test_alerts_fire_once():
    records = [
        {"id": "a", "headline": "Big quake", "severity": "high", "disaster_type": "earthquake", "source": "USGS", "source_type": "api"},
        {"id": "b", "headline": "Small quake", "severity": "low", "disaster_type": "earthquake", "source": "USGS", "source_type": "api"},
        {"id": "c", "headline": "OMG huge quake", "severity": "high", "disaster_type": "earthquake", "source": "Mastodon", "source_type": "social"},
    ]
    alerts, new_alerts = process_alerts(records)
    assert [a["id"] for a in new_alerts] == ["a"]

    alerts, new_alerts = process_alerts(records, existing=alerts)
    assert new_alerts == []
    assert len(alerts) == 1


def test_build_filter():
    assert build_filter() is None
    assert build_filter(severity="high") == {"severity": "high"}
    assert build_filter(disaster_type="flood", severity="high") == {
        "$and": [{"disaster_type": "flood"}, {"severity": "high"}]
    }
