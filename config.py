"""Central configuration for the Disastro pipeline.

Every path, model name and data source lives here so the individual
stages (scraper -> preprocessing -> embeddings -> vectordb -> rag) stay small.
Values marked "env" can be overridden with an environment variable.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------- paths

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

RAW_NEWS_FILE = RAW_DIR / "news.json"
RAW_API_FILE = RAW_DIR / "api_events.json"
RAW_SOCIAL_FILE = RAW_DIR / "social_posts.json"

CLEANED_FILE = DATA_DIR / "cleaned" / "cleaned_news.json"
EMBEDDINGS_FILE = DATA_DIR / "embedding_data" / "news_embeddings.json"
ALERTS_FILE = DATA_DIR / "alerts" / "alerts.json"
REPORT_FILE = DATA_DIR / "reports" / "latest_report.json"

CHROMA_DIR = BASE_DIR / "vectordb" / "chroma_storage"
COLLECTION_NAME = "disaster_news"

FRONTEND_DIR = BASE_DIR / "frontend"


# --------------------------------------------------------------- models

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SEVERITY_MODEL = "facebook/bart-large-mnli"

# "rules" uses fast keyword rules, "zero-shot" uses SEVERITY_MODEL.  (env)
# Zero-shot is slow on CPU and, on real headlines, rates almost everything
# the same level, so rules are the default.
SEVERITY_MODE = os.getenv("DISASTRO_SEVERITY_MODE", "rules")

# Text generation for the RAG step: a local Ollama server is tried first,
# then the small Hugging Face model, then a plain extractive answer.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = 300
FALLBACK_LLM = "google/flan-t5-small"


# -------------------------------------------------------------- sources

REQUEST_TIMEOUT = 30
# Keep this honest: GDACS answers browser-lookalike agents with a JavaScript
# challenge page instead of its feed.
USER_AGENT = "Mozilla/5.0 (compatible; disastro/1.0)"

BBC_NEWS_URL = "https://www.bbc.com/news"

RSS_FEEDS = [
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/world/natural-disasters/rss"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {
        "name": "Google News",
        "url": (
            "https://news.google.com/rss/search?q=flood+OR+earthquake+OR+cyclone"
            "+OR+wildfire+OR+landslide+OR+tsunami+when:2d&hl=en-US&gl=US&ceid=US:en"
        ),
    },
]

USGS_FEEDS = [
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
]
GDACS_RSS_URL = "https://www.gdacs.org/xml/rss.xml"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=7&limit=100"

MASTODON_INSTANCE = "https://mastodon.social"
MASTODON_HASHTAGS = ["earthquake", "flood", "wildfire", "hurricane", "cyclone", "tsunami"]
MASTODON_POSTS_PER_TAG = 20


# ------------------------------------------------------------- pipeline

# Events older than this are dropped from the cleaned set and the vector DB.
RETENTION_DAYS = 7

# Minutes between runs of scheduler/live_scraper.py.  (env)
SCHEDULE_INTERVAL_MINUTES = int(os.getenv("DISASTRO_INTERVAL_MINUTES", "30"))

SITUATION_REPORT_QUERY = "What are the most serious ongoing disasters right now?"

# High severity events are POSTed here as JSON when set.  (env)
ALERT_WEBHOOK_URL = os.getenv("DISASTRO_ALERT_WEBHOOK", "")

API_HOST = "127.0.0.1"
API_PORT = 8000


# ------------------------------------------------------- disaster types

# Keyword patterns (regex, matched on word boundaries) used to tag news and
# social posts with a disaster type. Anything matching none of them is
# treated as non-disaster news and filtered out.
DISASTER_KEYWORDS = {
    "earthquake": [r"earthquakes?", r"quakes?", r"aftershocks?", r"seismic", r"tremors?"],
    "tsunami": [r"tsunamis?"],
    "flood": [r"floods?", r"flooding", r"flooded", r"floodwaters?", r"flash floods?", r"inundat\w+", r"deluge"],
    "cyclone": [
        r"cyclones?", r"hurricanes?", r"typhoons?", r"tropical storms?",
        r"tropical depressions?", r"storm surges?", r"super ?storms?",
    ],
    "tornado": [r"tornado(?:es|s)?", r"twisters?"],
    "wildfire": [r"wildfires?", r"bushfires?", r"forest fires?", r"wild ?land fires?", r"brush fires?"],
    "volcano": [r"volcano(?:es|s)?", r"volcanic", r"eruptions?", r"lava flows?"],
    "landslide": [r"landslides?", r"mudslides?", r"landslips?", r"avalanches?", r"rockslides?"],
    "drought": [r"droughts?", r"famines?"],
    "heatwave": [r"heat ?waves?", r"extreme heat", r"cold ?waves?", r"blizzards?", r"snowstorms?"],
    "storm": [r"storms?", r"monsoons?", r"hailstorms?", r"cloudbursts?"],
}

# Headlines matching these use a disaster word as a metaphor or a team name.
NON_DISASTER_PATTERNS = [
    r"(?:blue|red|political|electoral|election|midterm|democrat\w*|republican) (?:tsunami|wave|landslide|earthquake|storm)",
    r"(?:tsunami|flood|storm|avalanche|deluge|eruption|earthquake) of (?!the century)\w+",
    r"landslide (?:victory|win|defeat|loss|election|vote|majority|re-?election)",
    r"(?:by|in) a landslide",
    r"cyclones? (?:football|basketball|hoops|tennis|wrestling|volleyball|soccer|softball|alert)",
    r"hurricanes? (?:football|basketball|hockey|baseball)",
    r"(?:iowa state|carolina hurricanes|miami hurricanes|big 12)",
    r"(?:spotify|youtu\.?be)",
]

# Social posts are noisier than news: besides a disaster keyword they must
# also mention something that suggests a real event.
SOCIAL_SIGNAL_PATTERNS = [
    r"magnitude", r"M[bwl]? ?\d", r"warnings?", r"watch", r"alerts?", r"advisory",
    r"evacuat\w+", r"damag\w+", r"destroy\w*", r"kill\w*", r"dead", r"deaths?",
    r"injur\w+", r"rescue\w*", r"emergency", r"displac\w+", r"missing",
    r"acres", r"hectares", r"landfall", r"epicent\w+", r"uncontrolled",
]

# Only these source types can raise alerts.
ALERT_SOURCE_TYPES = ["news", "api"]

SEVERITY_LEVELS = ["low", "medium", "high"]
