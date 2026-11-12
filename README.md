# Disastro

Live disaster monitoring with retrieval-augmented generation (RAG).

Disastro collects disaster reports from news sites, official agencies and social
media, filters and classifies them, stores them in a vector database, and lets
you search them, ask questions about them and get alerts for severe events —
from the command line or a web dashboard. Everything runs locally and no API
keys are needed.

## How it works

```
scraper/            news (BBC, Guardian, Al Jazeera, Google News RSS)
                    agencies (USGS earthquakes, GDACS alerts, NASA EONET)
                    social (Mastodon hashtag timelines)
      |             -> data/raw/*.json
preprocessing/      keep disaster-related items, tag disaster type, clean text,
      |             de-duplicate, drop items older than 7 days
      |             -> data/cleaned/cleaned_news.json
summarizer/         low / medium / high severity (agency alert level, magnitude
      |             and wind speed; keyword rules for everything else)
embeddings/         sentence embeddings (all-MiniLM-L6-v2)
      |             -> data/embedding_data/news_embeddings.json
vectordb/           ChromaDB storage + semantic search
      |
alerts/             one alert per new high severity event (+ optional webhook)
rag/                retrieve relevant reports and generate an answer
                    (Ollama -> flan-t5-small -> extractive fallback)

backend/            FastAPI REST API
frontend/           dashboard: map, event list, alerts, question box
scheduler/          runs the pipeline every N minutes
```

`pipeline.py` runs the stages in order, `config.py` holds every path, model
name and data source, and `main.py` is the command line entry point.

## Setup

Python 3.10 or newer.

```
python -m venv ai_env
ai_env\Scripts\activate
pip install -r requirements.txt
```

The embedding model (about 90 MB) downloads from Hugging Face on first use.

For good quality answers, install [Ollama](https://ollama.com) and pull a model:

```
ollama pull llama3
```

Without Ollama, answers fall back to the much weaker `flan-t5-small`.

## Usage

Run all commands from the project root.

```
python main.py pipeline              # run every stage once
python main.py pipeline --no-report  # ...without the LLM situation report
python main.py search "flood damage in asia" --severity high
python main.py ask "Where were the strongest earthquakes this week?"
python main.py report                # situation report on the most severe events
python main.py alerts                # list recorded alerts
python main.py schedule --interval 30
python main.py serve                 # dashboard at http://127.0.0.1:8000
```

Each stage can also be run on its own, for example
`python -m scraper.api_fetcher` or `python -m preprocessing.clean_text`.

A pipeline run takes about a minute plus the situation report, which depends on
how fast your machine runs the language model. Only new records are embedded.

### API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/events` | Events; filter with `disaster_type`, `severity`, `source_type`, `limit` |
| GET | `/api/stats` | Counts by severity, type and source, plus pipeline status |
| GET | `/api/search?q=` | Semantic search |
| POST | `/api/ask` | RAG answer: `{"question": "..."}` |
| GET | `/api/report` | Latest situation report |
| GET | `/api/alerts` | High severity alerts |
| POST | `/api/refresh` | Start a pipeline run in the background |

Interactive API docs are at `/docs`.

## Configuration

Edit `config.py`, or set these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISASTRO_SEVERITY_MODE` | `rules` | `zero-shot` classifies text with `bart-large-mnli` instead (slow on CPU, and in testing it rated nearly every headline the same level) |
| `DISASTRO_INTERVAL_MINUTES` | `30` | Scheduler interval |
| `DISASTRO_ALERT_WEBHOOK` | *(unset)* | URL that receives each new alert as a JSON POST |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `llama3` | Model used for answers |

## Scrapy spider (optional)

The original Scrapy spider still works as an extra source. Write its output
into `data/raw/` and the next pipeline run picks it up:

```
cd disastro_scraper
scrapy crawl bbc_news -O ../data/raw/bbc_scrapy.json
```

## Tests

```
python -m pytest tests
```

The tests run offline against sample payloads.

## Limitations

- News and social items are tagged by keyword, so an occasional off-topic
  headline ("a storm of criticism") can slip through.
- Only agency events carry coordinates; news items are not geocoded and do not
  appear on the map.
- Severity for news and social posts comes from keyword rules ("killed",
  "evacuated", ...) and is a rough guide, not an official assessment. Alerts
  are raised only from news and agency sources.
