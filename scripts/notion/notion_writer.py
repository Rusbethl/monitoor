"""
Escribe los datos recolectados a 3 bases de datos de Notion (plan gratuito):

  1. "Eventos del día"   -> noticias clasificadas
  2. "Snapshots de mercado" -> log horario de funding/OI/RSI/precio
  3. "Alertas técnicas"  -> alertas disparadas (funding extremo, RSI, etc.)

Requiere:
  - Crear una integración interna en https://www.notion.so/my-integrations
  - Compartir cada una de las 3 bases de datos con esa integración
  - Poner el token y los 3 database_id en el .env

Las bases deben tener (al menos) estas propiedades, con estos tipos exactos:

  Eventos del día:
    Título      (title)
    Fuente      (rich_text)
    Keywords    (rich_text)
    Link        (url)
    Publicado   (date)

  Snapshots de mercado:
    Título          (title)   -> se autogenera, ej "BTCUSDT 2026-09-17 14:00"
    Precio          (number)
    Funding Rate    (number)
    Open Interest   (number)
    Long/Short      (number)
    RSI 15m         (number)
    RSI 1h          (number)
    RSI 4h          (number)
    EMA50 1h        (number)
    EMA200 1h       (number)

  Alertas técnicas:
    Título      (title)   -> se autogenera con el tipo de alerta
    Tipo        (rich_text)
    Mensaje     (rich_text)
"""
import logging
from datetime import datetime, timezone

from notion_client import Client

from common.config import config

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not config.NOTION_TOKEN:
            raise RuntimeError("NOTION_TOKEN no configurado en .env")
        _client = Client(auth=config.NOTION_TOKEN)
    return _client


def push_news_item(item: dict):
    if not config.NOTION_DB_EVENTOS:
        logger.debug("NOTION_DB_EVENTOS no configurado, se omite envío a Notion.")
        return
    client = get_client()
    properties = {
        "Título": {"title": [{"text": {"content": item["title"][:2000]}}]},
        "Fuente": {"rich_text": [{"text": {"content": item.get("source", "")}}]},
        "Keywords": {"rich_text": [{"text": {"content": item.get("matched_keywords", "")}}]},
        "Link": {"url": item.get("link")},
    }
    if item.get("published_at"):
        properties["Publicado"] = {"date": {"start": item["published_at"].isoformat()}}

    client.pages.create(
        parent={"database_id": config.NOTION_DB_EVENTOS},
        properties=properties,
    )


def push_market_snapshot(snapshot: dict):
    if not config.NOTION_DB_SNAPSHOTS:
        logger.debug("NOTION_DB_SNAPSHOTS no configurado, se omite envío a Notion.")
        return
    client = get_client()
    now = datetime.now(timezone.utc)
    title = f"{snapshot.get('symbol')} {now.strftime('%Y-%m-%d %H:%M')} UTC"

    def _num(key):
        val = snapshot.get(key)
        return {"number": float(val)} if val is not None else {"number": None}

    properties = {
        "Título": {"title": [{"text": {"content": title}}]},
        "Precio": _num("price"),
        "Funding Rate": _num("funding_rate"),
        "Open Interest": _num("open_interest"),
        "Long/Short": _num("long_short_ratio"),
        "RSI 15m": _num("rsi_15m"),
        "RSI 1h": _num("rsi_1h"),
        "RSI 4h": _num("rsi_4h"),
        "EMA50 1h": _num("ema_50_1h"),
        "EMA200 1h": _num("ema_200_1h"),
    }

    client.pages.create(
        parent={"database_id": config.NOTION_DB_SNAPSHOTS},
        properties=properties,
    )


def push_alert(alert_type: str, message: str):
    if not config.NOTION_DB_ALERTAS:
        logger.debug("NOTION_DB_ALERTAS no configurado, se omite envío a Notion.")
        return
    client = get_client()
    properties = {
        "Título": {"title": [{"text": {"content": alert_type}}]},
        "Tipo": {"rich_text": [{"text": {"content": alert_type}}]},
        "Mensaje": {"rich_text": [{"text": {"content": message[:2000]}}]},
    }
    client.pages.create(
        parent={"database_id": config.NOTION_DB_ALERTAS},
        properties=properties,
    )
