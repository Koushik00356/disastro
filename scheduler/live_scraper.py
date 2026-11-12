"""Run the whole pipeline on a schedule.

Run directly with:  python -m scheduler.live_scraper
"""

import time

import schedule

import config
from pipeline import run_pipeline


def start(interval_minutes=None, with_report=True):

    interval_minutes = interval_minutes or config.SCHEDULE_INTERVAL_MINUTES

    schedule.every(interval_minutes).minutes.do(run_pipeline, with_report=with_report)

    print(f"AI pipeline started... (every {interval_minutes} minutes, Ctrl+C to stop)")

    run_pipeline(with_report=with_report)

    while True:

        schedule.run_pending()

        time.sleep(1)


if __name__ == "__main__":
    start()
