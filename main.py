"""Disastro command line entry point.

    python main.py pipeline            run every stage once
    python main.py scrape              only fetch the raw data
    python main.py search "floods"     semantic search over stored events
    python main.py ask "question"      RAG answer from stored events
    python main.py report              generate the situation report
    python main.py alerts              show recorded high severity alerts
    python main.py schedule            run the pipeline on a timer
    python main.py serve               start the API + dashboard
"""

import argparse
import sys

import config
from utils.helpers import get_logger, load_json


log = get_logger("main")


def cmd_pipeline(args):

    from pipeline import run_pipeline

    return 0 if run_pipeline(with_report=not args.no_report) else 1


def cmd_scrape(args):

    from pipeline import scrape

    scrape()


def cmd_search(args):

    from vectordb.search import search

    hits = search(args.query, n_results=args.n, disaster_type=args.type, severity=args.severity)

    if not hits:
        print("No results. Run `python main.py pipeline` first.")

    for hit in hits:
        print(f"[{hit['score']:.2f}] ({hit.get('disaster_type', '?')}, {hit.get('severity', '?')}) "
              f"{hit.get('headline', hit['text'])} - {hit.get('source', '')}")


def cmd_ask(args):

    from rag.rag_pipeline import answer_question

    result = answer_question(args.question, disaster_type=args.type, severity=args.severity)

    print(f"\n{result['answer']}\n")

    if result["sources"]:
        print(f"Sources (answered by {result['backend']}):")
        for source in result["sources"]:
            print(f"- {source.get('headline', source['text'])} ({source.get('source', '')}) {source.get('url', '')}")


def cmd_report(args):

    from rag.rag_pipeline import situation_report

    report = situation_report()

    print(f"\nSituation report ({report['backend']}):\n\n{report['answer']}\n")


def cmd_alerts(args):

    alerts = load_json(config.ALERTS_FILE)

    if not alerts:
        print("No alerts recorded.")

    for alert in alerts[:args.n]:
        print(f"{alert['alerted_at']} [{alert['disaster_type']}] {alert['headline']} ({alert['source']})")


def cmd_schedule(args):

    from scheduler.live_scraper import start

    start(interval_minutes=args.interval, with_report=not args.no_report)


def cmd_serve(args):

    import uvicorn

    uvicorn.run("backend.api:app", host=args.host, port=args.port)


def build_parser():

    parser = argparse.ArgumentParser(description="Disastro - live disaster monitoring with RAG")
    commands = parser.add_subparsers(dest="command", required=True)

    def add_filters(command):
        command.add_argument("--type", help="disaster type, e.g. flood, earthquake")
        command.add_argument("--severity", choices=config.SEVERITY_LEVELS)

    command = commands.add_parser("pipeline", help="run every stage once")
    command.add_argument("--no-report", action="store_true", help="skip the RAG situation report")
    command.set_defaults(func=cmd_pipeline)

    command = commands.add_parser("scrape", help="only fetch the raw data")
    command.set_defaults(func=cmd_scrape)

    command = commands.add_parser("search", help="semantic search over stored events")
    command.add_argument("query")
    command.add_argument("-n", type=int, default=5)
    add_filters(command)
    command.set_defaults(func=cmd_search)

    command = commands.add_parser("ask", help="RAG answer from stored events")
    command.add_argument("question")
    add_filters(command)
    command.set_defaults(func=cmd_ask)

    command = commands.add_parser("report", help="generate the situation report")
    command.set_defaults(func=cmd_report)

    command = commands.add_parser("alerts", help="show recorded high severity alerts")
    command.add_argument("-n", type=int, default=20)
    command.set_defaults(func=cmd_alerts)

    command = commands.add_parser("schedule", help="run the pipeline on a timer")
    command.add_argument("--interval", type=int, help="minutes between runs")
    command.add_argument("--no-report", action="store_true", help="skip the RAG situation report")
    command.set_defaults(func=cmd_schedule)

    command = commands.add_parser("serve", help="start the API + dashboard")
    command.add_argument("--host", default=config.API_HOST)
    command.add_argument("--port", type=int, default=config.API_PORT)
    command.set_defaults(func=cmd_serve)

    return parser


def main():

    args = build_parser().parse_args()

    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
