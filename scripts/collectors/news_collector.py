"""
Recolector de noticias vía RSS, filtrado por keywords relevantes para BTC:
Fed/tasas, Trump/dólar, petróleo, geopolítica (Irán, etc.), y BTC/crypto directo.

No determina automáticamente "rumor" vs "confirmado" (eso requiere lectura humana
o un LLM), pero sí clasifica la fuente como tipo "medio_formal" o "agregador_veloz"
para dar una pista, y guarda el link para que el comando de análisis lo revise.
"""
import logging
import re
from datetime import datetime, timezone

import feedparser

logger = logging.getLogger(__name__)

# Fuentes RSS gratuitas. Se puede ampliar libremente.
FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Investing.com Crypto": "https://www.investing.com/rss/news_301.rss",
}

KEYWORDS = [
    # Macro / Fed
    "fed", "federal reserve", "powell", "interest rate", "rate cut", "rate hike",
    "fomc", "cpi", "ppi", "inflation", "jobs report", "nonfarm payrolls",
    # Trump / dólar / geopolítica
    "trump", "dollar", "tariff", "iran", "war", "sanctions", "oil price", "opec",
    # BTC / crypto directo
    "bitcoin", "btc", "crypto", "etf", "blackrock", "microstrategy", "saylor",
    "sec", "binance", "liquidation", "whale",
]

# Categorías para clasificar cada noticia (se usa para el ícono/color de la
# tarjeta cuando el feed no trae imagen, y para el tag visible).
CATEGORY_KEYWORDS = {
    "bitcoin": ["bitcoin", "btc", "microstrategy", "saylor", "etf", "halving"],
    "regulacion": ["sec", "regulat", "law", "legal", "tax", "ban", "government"],
    "exchange": ["binance", "coinbase", "exchange", "liquidation", "whale", "hack"],
    "macro": [
        "fed", "federal reserve", "powell", "interest rate", "rate cut", "rate hike",
        "fomc", "cpi", "ppi", "inflation", "jobs report", "nonfarm payrolls",
        "trump", "dollar", "tariff", "iran", "war", "sanctions", "oil price", "opec",
    ],
}


def _matches_keywords(title: str, summary: str) -> list[str]:
    text = f"{title} {summary}".lower()
    return [kw for kw in KEYWORDS if kw in text]


RUMOR_KEYWORDS = [
    "rumor", "rumour", "reportedly", "sources say", "according to sources",
    "unconfirmed", "alleged", "allegedly", "could be", "may consider",
    "in talks", "speculat", "said to be", "considering",
]


def _is_rumor(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in RUMOR_KEYWORDS)


def _category_for(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "general"


def _extract_image(entry) -> str | None:
    """Busca una imagen en los campos habituales de RSS/Media RSS."""
    media = getattr(entry, "media_content", None) or []
    for m in media:
        url = m.get("url") if isinstance(m, dict) else None
        if url:
            return url

    thumbs = getattr(entry, "media_thumbnail", None) or []
    for t in thumbs:
        url = t.get("url") if isinstance(t, dict) else None
        if url:
            return url

    for link in getattr(entry, "links", []) or []:
        if isinstance(link, dict) and str(link.get("type", "")).startswith("image/"):
            if link.get("href"):
                return link["href"]

    summary_html = getattr(entry, "summary", "") or ""
    match = re.search(r'<img[^>]+src="([^"]+)"', summary_html)
    if match:
        return match.group(1)

    return None


def _parse_published(entry) -> datetime | None:
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return None


def collect() -> list[dict]:
    """Devuelve una lista de items de noticias nuevos que matchean keywords."""
    results = []
    for source_name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning("Error leyendo feed %s (%s): %s", source_name, url, e)
            continue

        if feed.bozo and not feed.entries:
            logger.warning("Feed %s no devolvió entradas válidas.", source_name)
            continue

        for entry in feed.entries[:30]:
            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "") if hasattr(entry, "summary") else ""
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            matched = _matches_keywords(title, summary)
            if not matched:
                continue

            results.append({
                "source": source_name,
                "title": title,
                "link": link,
                "matched_keywords": ", ".join(matched),
                "published_at": _parse_published(entry),
                "image_url": _extract_image(entry),
                "category": _category_for(title, summary),
                "is_rumor": _is_rumor(title, summary),
            })

    logger.info("Noticias relevantes encontradas: %s", len(results))
    return results
