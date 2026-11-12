"""Fetch structured disaster events from public APIs (no API keys needed).

Sources:
    USGS   - earthquakes (GeoJSON feeds)
    GDACS  - Global Disaster Alert and Coordination System (RSS)
    EONET  - NASA Earth Observatory Natural Event Tracker (JSON)

Run directly with:  python -m scraper.api_fetcher
"""

import xml.etree.ElementTree as ET

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


log = get_logger("api_fetcher")


GDACS_NS = {
    "gdacs": "http://www.gdacs.org",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
}

GDACS_EVENT_TYPES = {
    "EQ": "earthquake",
    "TS": "tsunami",
    "FL": "flood",
    "TC": "cyclone",
    "VO": "volcano",
    "DR": "drought",
    "WF": "wildfire",
}

EONET_CATEGORIES = {
    "earthquakes": "earthquake",
    "floods": "flood",
    "severeStorms": "cyclone",
    "wildfires": "wildfire",
    "volcanoes": "volcano",
    "landslides": "landslide",
    "drought": "drought",
    "tempExtremes": "heatwave",
    "snow": "storm",
    "dustHaze": "storm",
}


def build_event(source, event_id, headline, disaster_type, **fields):

    event = {
        "id": make_id(source, event_id),
        "headline": headline,
        "summary": "",
        "source": source,
        "source_type": "api",
        "url": "",
        "published_at": None,
        "scraped_at": now_iso(),
        "disaster_type": disaster_type,
    }
    event.update(fields)

    return event


def to_float(value):

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_usgs(payload):

    events = []

    for feature in payload.get("features", []):

        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None, None]

        magnitude = props.get("mag")
        place = props.get("place") or "unknown location"

        summary = f"Magnitude {magnitude} earthquake, {place}."
        if coords[2] is not None:
            summary += f" Depth {coords[2]} km."
        if props.get("tsunami"):
            summary += " Tsunami information issued."

        events.append(
            build_event(
                "USGS",
                feature.get("id"),
                props.get("title") or f"M {magnitude} - {place}",
                "earthquake",
                summary=summary,
                url=props.get("url") or "",
                published_at=normalize_date(props.get("time")),
                latitude=coords[1],
                longitude=coords[0],
                magnitude=magnitude,
                alert_level=props.get("alert"),
                location=place,
            )
        )

    return events


def parse_gdacs(xml_text):

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # The live feed regularly contains invalid characters; lxml can skip them.
        from lxml import etree

        root = etree.fromstring(xml_text, etree.XMLParser(recover=True))

    events = []

    for item in root.iter("item"):

        def field(name):
            return (item.findtext(f"gdacs:{name}", namespaces=GDACS_NS) or "").strip()

        event_type = field("eventtype")

        if event_type not in GDACS_EVENT_TYPES:
            continue

        severity = item.find("gdacs:severity", GDACS_NS)
        is_quake = event_type == "EQ" and severity is not None

        events.append(
            build_event(
                "GDACS",
                item.findtext("guid") or item.findtext("link"),
                strip_html(item.findtext("title")),
                GDACS_EVENT_TYPES[event_type],
                summary=strip_html(item.findtext("description")),
                url=(item.findtext("link") or "").strip(),
                published_at=normalize_date(item.findtext("pubDate")),
                latitude=to_float(item.findtext("geo:Point/geo:lat", namespaces=GDACS_NS)),
                longitude=to_float(item.findtext("geo:Point/geo:long", namespaces=GDACS_NS)),
                magnitude=to_float(severity.get("value")) if is_quake else None,
                alert_level=field("alertlevel").lower() or None,
                location=field("country") or None,
            )
        )

    return events


def parse_eonet(payload):

    events = []

    for item in payload.get("events", []):

        categories = [c.get("id") for c in item.get("categories", [])]
        disaster_type = next(
            (EONET_CATEGORIES[c] for c in categories if c in EONET_CATEGORIES), None
        )

        if disaster_type is None:
            continue

        # The geometry list tracks the event over time; the last entry is the latest.
        geometry = (item.get("geometry") or [{}])[-1]
        coords = geometry.get("coordinates") if geometry.get("type") == "Point" else None

        category_title = ", ".join(c.get("title", "") for c in item.get("categories", []))
        summary = item.get("description") or f"{category_title} event tracked by NASA EONET."
        if geometry.get("magnitudeValue") is not None:
            summary += f" Latest reading: {geometry['magnitudeValue']} {geometry.get('magnitudeUnit', '')}."

        sources = item.get("sources") or [{}]

        events.append(
            build_event(
                "NASA EONET",
                item.get("id"),
                item.get("title", ""),
                disaster_type,
                summary=summary.strip(),
                url=sources[0].get("url") or item.get("link", ""),
                published_at=normalize_date(geometry.get("date")),
                latitude=coords[1] if coords else None,
                longitude=coords[0] if coords else None,
            )
        )

    return events


def fetch_usgs():

    events = {}

    for url in config.USGS_FEEDS:
        for event in parse_usgs(http_get(url).json()):
            events[event["id"]] = event

    return list(events.values())


def fetch_gdacs():

    return parse_gdacs(http_get(config.GDACS_RSS_URL).content)


def fetch_eonet():

    response = http_get(config.EONET_URL, headers={"Accept": "application/json"})

    return parse_eonet(response.json())


def fetch_events():

    events = []

    for name, fetch in (("USGS", fetch_usgs), ("GDACS", fetch_gdacs), ("NASA EONET", fetch_eonet)):

        try:
            found = fetch()
            log.info("%s: %d events", name, len(found))
            events.extend(found)
        except Exception as error:
            log.warning("%s failed: %s", name, error)

    return events


def run():

    events = fetch_events()

    save_json(config.RAW_API_FILE, events)

    log.info("Saved %d events to %s", len(events), config.RAW_API_FILE)

    return events


if __name__ == "__main__":
    run()
