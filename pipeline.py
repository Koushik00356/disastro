"""Runs the stages of the Disastro pipeline in order.

Heavy libraries (torch, transformers, chromadb) are imported inside the
stages that need them, so scraping alone starts instantly.
"""

from datetime import datetime

from utils.helpers import get_logger


log = get_logger("pipeline")


def scrape():

    from scraper import api_fetcher, news_scraper, social_scraper

    news_scraper.run()
    api_fetcher.run()
    social_scraper.run()


def clean():

    from preprocessing import clean_text

    clean_text.run()


def classify():

    from summarizer import severity_classifier

    severity_classifier.run()


def embed():

    from embeddings import generate_embedding

    generate_embedding.run()


def store():

    from vectordb import store_embedding

    store_embedding.run()


def alert():

    from alerts import alert_manager

    alert_manager.run()


def report():

    from rag import rag_pipeline

    result = rag_pipeline.situation_report()

    log.info("Situation report (%s):\n%s", result["backend"], result["answer"])


STEPS = [
    ("SCRAPING", scrape),
    ("CLEANING", clean),
    ("SEVERITY CLASSIFICATION", classify),
    ("EMBEDDINGS", embed),
    ("VECTOR STORAGE", store),
    ("ALERTS", alert),
    ("RAG GENERATION", report),
]


def run_pipeline(with_report=True):
    """Run every stage. Returns True when all stages succeeded."""

    log.info("PIPELINE STARTED at %s", datetime.now())

    for number, (name, step) in enumerate(STEPS, start=1):

        if step is report and not with_report:
            continue

        log.info("STEP %d : %s", number, name)

        try:
            step()
        except Exception:
            log.exception("STEP %d : %s failed, stopping this run.", number, name)
            return False

    log.info("PIPELINE FINISHED at %s", datetime.now())

    return True


if __name__ == "__main__":
    run_pipeline()
