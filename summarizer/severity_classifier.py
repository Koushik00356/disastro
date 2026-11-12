"""Assign a low / medium / high severity to every cleaned record.

Signals, in this order:
    1. Structured data from the APIs (alert level, magnitude, wind speed).
    2. Keyword rules on the text (the default), or zero-shot classification
       with facebook/bart-large-mnli when DISASTRO_SEVERITY_MODE=zero-shot.

Run directly with:  python -m summarizer.severity_classifier
"""

import re

import config
from utils.helpers import get_logger, load_json, save_json


log = get_logger("severity")


LABELS = {
    "low severity disaster": "low",
    "medium severity disaster": "medium",
    "high severity disaster": "high",
}

ALERT_LEVELS = {"green": "low", "yellow": "medium", "orange": "medium", "red": "high"}

HIGH_PATTERN = re.compile(
    r"\b(?:kill(?:s|ed)?|dead|deaths?|death toll|fatalit\w+|devastat\w+|catastroph\w+"
    r"|state of emergency|destroy(?:s|ed)?|thousands|massive|deadly|deadliest)\b",
    re.IGNORECASE,
)
MEDIUM_PATTERN = re.compile(
    r"\b(?:evacuat\w+|injur\w+|damag\w+|displac\w+|missing|rescue[sd]?|stranded"
    r"|warnings?|alert|emergency|hundreds|collaps\w+|severe)\b",
    re.IGNORECASE,
)

_classifier = None


def structured_severity(record):
    """Severity from API fields, or None when the record has none."""

    levels = []

    alert = str(record.get("alert_level") or "").lower()
    if alert in ALERT_LEVELS:
        levels.append(ALERT_LEVELS[alert])

    magnitude = record.get("magnitude")
    if record.get("disaster_type") == "earthquake" and isinstance(magnitude, (int, float)):
        if magnitude >= 6.5:
            levels.append("high")
        elif magnitude >= 5.5:
            levels.append("medium")
        else:
            levels.append("low")

    # Tropical cyclone wind speed: hurricane force from 64 kt, major from 96 kt.
    wind = record.get("wind_kts")
    if isinstance(wind, (int, float)):
        levels.append("high" if wind >= 96 else "medium" if wind >= 64 else "low")

    if not levels:
        return None

    return max(levels, key=config.SEVERITY_LEVELS.index)


def rule_based_severity(text):

    if HIGH_PATTERN.search(text):
        return "high"

    if MEDIUM_PATTERN.search(text):
        return "medium"

    return "low"


def get_classifier():

    global _classifier

    if _classifier is None:
        from transformers import pipeline

        log.info("Loading %s ...", config.SEVERITY_MODEL)
        _classifier = pipeline("zero-shot-classification", model=config.SEVERITY_MODEL)

    return _classifier


def zero_shot_severity(texts):
    """Classify texts with the NLI model. Returns a list of (severity, score)."""

    classifier = get_classifier()

    results = classifier(texts, candidate_labels=list(LABELS), batch_size=8)

    if isinstance(results, dict):
        results = [results]

    return [(LABELS[r["labels"][0]], round(float(r["scores"][0]), 3)) for r in results]


def classify_records(records, mode=None):
    """Assign a severity to every record (modifies them in place).

    Zero-shot results are slow to compute, so in zero-shot mode they are kept
    from earlier runs; the cheap structured and rule results are recomputed.
    """

    mode = mode or config.SEVERITY_MODE

    pending = []

    for record in records:

        if mode == "zero-shot" and record.get("severity_method") == "zero-shot":
            continue

        severity = structured_severity(record)

        if severity:
            record.update(severity=severity, severity_score=1.0, severity_method="structured")
        else:
            pending.append(record)

    if pending and mode == "zero-shot":

        try:
            log.info("Zero-shot classifying %d records (this is slow on CPU)...", len(pending))
            predictions = zero_shot_severity([record["text"][:500] for record in pending])

            for record, (severity, score) in zip(pending, predictions):
                record.update(severity=severity, severity_score=score, severity_method="zero-shot")

            pending = []
        except Exception as error:
            log.warning("Zero-shot model unavailable (%s); using keyword rules.", error)

    for record in pending:
        record.update(
            severity=rule_based_severity(record["text"]),
            severity_score=0.5,
            severity_method="rules",
        )

    return records


def run(mode=None):

    records = classify_records(load_json(config.CLEANED_FILE), mode=mode)

    save_json(config.CLEANED_FILE, records)

    counts = {level: sum(r["severity"] == level for r in records) for level in config.SEVERITY_LEVELS}

    log.info("Severity assigned: %s", counts)

    return records


if __name__ == "__main__":
    run()
