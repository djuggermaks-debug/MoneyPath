import feedparser
import requests
import os
from datetime import datetime, timezone, timedelta


REUTERS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/reuters/energy",
    "https://rss.app/feeds/tXWNOmyBuVRdQprj.xml",
    "https://www.investing.com/rss/news_301.rss",
    "https://www.investing.com/rss/news_25.rss",
]

DIGEST_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.reuters.com/reuters/energy",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.feedburner.com/TechCrunch",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.eurogamer.net/feed",
    "https://oilprice.com/rss/main",
]

NEWSAPI_URL = "https://newsapi.org/v2/everything"

DIGEST_KEYWORDS = [
    "merger", "acquisition", "geopolitics", "sanctions", "summit",
    "artificial intelligence", "semiconductor", "IPO", "Federal Reserve",
    "trade war", "NATO", "tariff", "central bank", "election", "conflict",
    "G7", "G20", "BRICS", "tech deal", "big tech", "regulation",
]


def _is_recent(published, hours=4):
    try:
        pub = datetime(*published[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - pub < timedelta(hours=hours)
    except Exception:
        return True


def fetch_rss(keywords):
    articles = []
    for url in REUTERS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
            if any(kw.lower() in text for kw in keywords):
                if _is_recent(entry.get("published_parsed", ())):
                    articles.append({
                        "source": "Reuters",
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "link": entry.get("link", ""),
                    })
    return articles


def fetch_newsapi(keywords):
    api_key = os.environ.get("NEWSAPI_KEY", "")
    if not api_key:
        return []

    query = " OR ".join(keywords[:5])
    params = {
        "q": query,
        "apiKey": api_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "from": (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        resp = requests.get(NEWSAPI_URL, params=params, timeout=10)
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "source": a.get("source", {}).get("name", "NewsAPI"),
                "title": a.get("title", ""),
                "summary": a.get("description", ""),
                "published": a.get("publishedAt", ""),
                "link": a.get("url", ""),
            })
        return articles
    except Exception:
        return []


def fetch_all(keywords):
    rss = fetch_rss(keywords)
    api = fetch_newsapi(keywords)
    seen = set()
    result = []
    for article in rss + api:
        key = article["title"][:60]
        if key not in seen:
            seen.add(key)
            result.append(article)
    return result


def fetch_digest():
    api_key = os.environ.get("NEWSAPI_KEY", "")
    articles = []

    for url in DIGEST_FEEDS:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get("title", url.split("/")[2])
            for entry in feed.entries:
                if _is_recent(entry.get("published_parsed", ()), hours=24):
                    articles.append({
                        "source": source_name,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "published": entry.get("published", ""),
                        "link": entry.get("link", ""),
                    })
        except Exception:
            pass

    if api_key:
        query = "summit OR geopolitics OR sanctions OR \"artificial intelligence\" OR energy OR gaming OR merger OR acquisition"
        params = {
            "q": query,
            "apiKey": api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "from": (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        try:
            resp = requests.get(NEWSAPI_URL, params=params, timeout=10)
            data = resp.json()
            for a in data.get("articles", []):
                articles.append({
                    "source": a.get("source", {}).get("name", "NewsAPI"),
                    "title": a.get("title", ""),
                    "summary": a.get("description", ""),
                    "published": a.get("publishedAt", ""),
                    "link": a.get("url", ""),
                })
        except Exception:
            pass

    seen = set()
    result = []
    for article in articles:
        key = article["title"][:60]
        if key not in seen:
            seen.add(key)
            result.append(article)
    return result
