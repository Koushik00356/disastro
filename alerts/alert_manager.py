"""Raise an alert for every new high severity event.

Alerts are appended to data/alerts/alerts.json (each event alerts once) and,
when DISASTRO_ALERT_WEBHOOK is set, POSTed to that URL as JSON.

Run directly with:  python -m alerts.alert_manager
"""

import requests

import config
from utils.helpers import get_logger, load_json, now_iso, save_json


log = get_logger("alerts")


ALERT_FIELDS = (
    "id", "headline", "disaster_type", "severity", "source", "url",
    "published_at", "location", "latitude", "longitude",
)


def build_alert(record):

    alert = {field: record.get(field) for field in ALERT_FIELDS}
    alert["alerted_at"] = now_iso()

    return alert


def send_webhook(alert):

    if not config.ALERT_WEBHOOK_URL:
        return

    try:
        requests.post(config.ALERT_WEBHOOK_URL, json=alert, timeout=10).raise_for_status()
    except Exception as error:
        log.warning("Webhook delivery failed: %s", error)


def process_alerts(records, existing=None):
    """Return (all alerts, new alerts) for the given records."""

    alerts = list(existing or [])
    alerted_ids = {alert["id"] for alert in alerts}

    new_alerts = [
        build_alert(record)
        for record in records
        if record.get("severity") == "high" and record["id"] not in alerted_ids
    ]

    return new_alerts + alerts, new_alerts


def run():

    alerts, new_alerts = process_alerts(
        load_json(config.CLEANED_FILE),
        existing=load_json(config.ALERTS_FILE),
    )

    for alert in new_alerts:
        log.info("ALERT [%s] %s", alert["disaster_type"], alert["headline"])
        send_webhook(alert)

    save_json(config.ALERTS_FILE, alerts)

    log.info("%d new alerts (%d total).", len(new_alerts), len(alerts))

    return new_alerts


if __name__ == "__main__":
    run()
