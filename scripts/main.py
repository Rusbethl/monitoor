"""
Punto de entrada del contenedor `collector`.

Orquesta, con un cron interno (`schedule`), la recolección periódica de:
 - Datos de mercado/derivados de Binance -> Postgres -> Notion (Snapshots) -> Telegram (si hay alerta)
 - Noticias relevantes por RSS -> Postgres -> Notion (Eventos) -> Telegram

Todo corre dentro de un único proceso Python de larga duración (loop infinito),
pensado para quedarse encendido 24/7 en la PC del usuario vía docker-compose.
"""
import logging
import time

import schedule

from common.config import config
from common.db import (
    get_connection,
    insert_alert,
    insert_market_snapshot,
    insert_news_item,
    insert_whale_trade,
    mark_alert_sent,
    mark_news_sent,
    upsert_economic_event,
)
from collectors import binance_collector, news_collector, whale_collector, calendar_collector
from notion import notion_writer
from telegram import telegram_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("btc-monitor")


def job_market():
    conn = get_connection()
    try:
        snapshot = binance_collector.collect()
        insert_market_snapshot(conn, snapshot)

        try:
            notion_writer.push_market_snapshot(snapshot)
        except Exception as e:
            logger.error("Error escribiendo snapshot a Notion: %s", e)

        alerts = binance_collector.evaluate_alerts(snapshot)
        for alert in alerts:
            alert_id = insert_alert(conn, alert["type"], alert["message"], snapshot)
            sent_tg = telegram_bot.notify_alert(alert["type"], alert["message"]) or False
            sent_notion = False
            try:
                notion_writer.push_alert(alert["type"], alert["message"])
                sent_notion = True
            except Exception as e:
                logger.error("Error escribiendo alerta a Notion: %s", e)
            mark_alert_sent(conn, alert_id, telegram=sent_tg, notion=sent_notion)

    except Exception:
        logger.exception("Fallo en job_market")
    finally:
        conn.close()


def job_news():
    conn = get_connection()
    try:
        items = news_collector.collect()
        for item in items:
            is_new = insert_news_item(conn, item)
            if not is_new:
                continue  # ya la teníamos, evita spam repetido

            sent_notion = False
            try:
                notion_writer.push_news_item(item)
                sent_notion = True
            except Exception as e:
                logger.error("Error escribiendo noticia a Notion: %s", e)

            sent_tg = telegram_bot.notify_news(item) or False

            # necesitamos el id recién insertado para marcarlo; lo resolvemos por link
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM news_items WHERE link = %s", (item["link"],))
                row = cur.fetchone()
            if row:
                mark_news_sent(conn, row[0], telegram=sent_tg, notion=sent_notion)

    except Exception:
        logger.exception("Fallo en job_news")
    finally:
        conn.close()


def job_whales():
    conn = get_connection()
    try:
        whales = whale_collector.collect()
        nuevos = 0
        for trade in whales:
            if insert_whale_trade(conn, trade):
                nuevos += 1
        if nuevos:
            logger.info("Whale trades nuevos guardados: %s", nuevos)
    except Exception:
        logger.exception("Fallo en job_whales")
    finally:
        conn.close()


def job_calendar():
    """Carga/actualiza el calendario económico. Es barato, se puede correr poco seguido."""
    conn = get_connection()
    try:
        events = calendar_collector.collect()
        nuevos = 0
        for event in events:
            if upsert_economic_event(conn, event):
                nuevos += 1
        if nuevos:
            logger.info("Eventos económicos nuevos guardados: %s", nuevos)
    except Exception:
        logger.exception("Fallo en job_calendar")
    finally:
        conn.close()


def main():
    logger.info("btc-monitor iniciado. Símbolo: %s", config.BINANCE_SYMBOL)
    logger.info(
        "Intervalos: mercado cada %s min, noticias cada %s min, whales cada %s min",
        config.INTERVALO_MERCADO_MIN, config.INTERVALO_NOTICIAS_MIN, config.INTERVALO_WHALES_MIN,
    )

    # Ejecuta una vez al arrancar para tener datos inmediatos
    job_market()
    job_news()
    job_whales()
    job_calendar()

    schedule.every(config.INTERVALO_MERCADO_MIN).minutes.do(job_market)
    schedule.every(config.INTERVALO_NOTICIAS_MIN).minutes.do(job_news)
    schedule.every(config.INTERVALO_WHALES_MIN).minutes.do(job_whales)
    schedule.every(12).hours.do(job_calendar)

    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    main()
