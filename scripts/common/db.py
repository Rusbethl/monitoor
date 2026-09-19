"""Helpers de conexión y escritura a PostgreSQL/TimescaleDB."""
import json
import logging
import time

import psycopg2
import psycopg2.extras

from common.config import config

logger = logging.getLogger(__name__)


def get_connection(retries: int = 10, delay: int = 3):
    """Se conecta a Postgres reintentando (útil al arrancar con docker-compose)."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(config.postgres_dsn)
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError as e:
            last_err = e
            logger.warning(
                "No se pudo conectar a Postgres (intento %s/%s): %s",
                attempt, retries, e,
            )
            time.sleep(delay)
    raise last_err


def insert_market_snapshot(conn, data: dict):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_snapshots
                (symbol, price, funding_rate, open_interest, long_short_ratio,
                 rsi_15m, rsi_1h, rsi_4h, ema_50_1h, ema_200_1h, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data.get("symbol"),
                data.get("price"),
                data.get("funding_rate"),
                data.get("open_interest"),
                data.get("long_short_ratio"),
                data.get("rsi_15m"),
                data.get("rsi_1h"),
                data.get("rsi_4h"),
                data.get("ema_50_1h"),
                data.get("ema_200_1h"),
                json.dumps(data),
            ),
        )


def insert_news_item(conn, item: dict) -> bool:
    """Inserta una noticia si no existe ya (por link único). Devuelve True si fue nueva."""
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO news_items (source, title, link, matched_keywords, published_at, image_url, category, is_rumor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO NOTHING
                RETURNING id
                """,
                (
                    item.get("source"),
                    item.get("title"),
                    item.get("link"),
                    item.get("matched_keywords"),
                    item.get("published_at"),
                    item.get("image_url"),
                    item.get("category"),
                    item.get("is_rumor", False),
                ),
            )
            return cur.fetchone() is not None
        except psycopg2.errors.UniqueViolation:
            return False


def insert_alert(conn, alert_type: str, message: str, payload: dict):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO alerts_log (alert_type, message, payload_json)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (alert_type, message, json.dumps(payload)),
        )
        return cur.fetchone()[0]


def mark_news_sent(conn, news_id: int, telegram: bool = False, notion: bool = False):
    with conn.cursor() as cur:
        if telegram:
            cur.execute("UPDATE news_items SET sent_to_telegram = TRUE WHERE id = %s", (news_id,))
        if notion:
            cur.execute("UPDATE news_items SET sent_to_notion = TRUE WHERE id = %s", (news_id,))


def mark_alert_sent(conn, alert_id: int, telegram: bool = False, notion: bool = False):
    with conn.cursor() as cur:
        if telegram:
            cur.execute("UPDATE alerts_log SET sent_to_telegram = TRUE WHERE id = %s", (alert_id,))
        if notion:
            cur.execute("UPDATE alerts_log SET sent_to_notion = TRUE WHERE id = %s", (alert_id,))


def upsert_economic_event(conn, event: dict) -> bool:
    """Inserta un evento económico si no existe ya (por fecha+título). Devuelve True si fue nuevo."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO economic_events (event_date, title, category, impact, notes, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_date, title) DO NOTHING
            RETURNING id
            """,
            (
                event.get("event_date"),
                event.get("title"),
                event.get("category"),
                event.get("impact"),
                event.get("notes"),
                event.get("source", "manual"),
            ),
        )
        return cur.fetchone() is not None


def insert_whale_trade(conn, trade: dict) -> bool:
    """Inserta un whale trade si no existe ya (por trade_id). Devuelve True si fue nuevo."""
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO whale_trades (symbol, side, price, quantity, quote_value_usd, trade_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_id) DO NOTHING
                RETURNING id
                """,
                (
                    trade.get("symbol"),
                    trade.get("side"),
                    trade.get("price"),
                    trade.get("quantity"),
                    trade.get("quote_value_usd"),
                    trade.get("trade_id"),
                ),
            )
            return cur.fetchone() is not None
        except psycopg2.errors.UniqueViolation:
            return False
