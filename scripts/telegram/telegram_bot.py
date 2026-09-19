"""
Envío de notificaciones a Telegram cuando se detecta un evento de alto impacto:
 - Funding rate extremo
 - RSI en sobrecompra/sobreventa en algún timeframe
 - Noticia relevante recién detectada

Requiere TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el .env.
Usa la API HTTP directa (requests) para evitar dependencias async pesadas
dentro de un script que ya corre con `schedule` de forma síncrona.
"""
import logging

import requests

from common.config import config

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_message(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.debug("Telegram no configurado, se omite envío.")
        return False

    url = f"{TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Error enviando mensaje a Telegram: %s", e)
        return False


def notify_alert(alert_type: str, message: str):
    text = f"🚨 *Alerta: {alert_type}*\n{message}"
    send_message(text)


def notify_news(item: dict):
    text = (
        f"📰 *Noticia relevante* ({item.get('source')})\n"
        f"{item.get('title')}\n"
        f"Keywords: {item.get('matched_keywords')}\n"
        f"{item.get('link')}"
    )
    send_message(text)
