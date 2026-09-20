"""Carga la configuración desde variables de entorno (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Postgres
    POSTGRES_USER = os.getenv("POSTGRES_USER", "btcmonitor")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "btcmonitor")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

    # Notion
    NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    NOTION_DB_EVENTOS = os.getenv("NOTION_DB_EVENTOS", "")
    NOTION_DB_SNAPSHOTS = os.getenv("NOTION_DB_SNAPSHOTS", "")
    NOTION_DB_ALERTAS = os.getenv("NOTION_DB_ALERTAS", "")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Binance
    BINANCE_SYMBOL = os.getenv("BINANCE_SYMBOL", "BTCUSDT")

    # Umbrales
    FUNDING_RATE_ALERTA = float(os.getenv("FUNDING_RATE_ALERTA", "0.0005"))
    RSI_SOBRECOMPRA = float(os.getenv("RSI_SOBRECOMPRA", "70"))
    RSI_SOBREVENTA = float(os.getenv("RSI_SOBREVENTA", "30"))

    # Frecuencias
    INTERVALO_MERCADO_MIN = int(os.getenv("INTERVALO_MERCADO_MIN", "15"))
    INTERVALO_NOTICIAS_MIN = int(os.getenv("INTERVALO_NOTICIAS_MIN", "20"))
    INTERVALO_WHALES_MIN = int(os.getenv("INTERVALO_WHALES_MIN", "5"))

    # Whale trades: monto mínimo en USD para considerarse "grande"
    WHALE_TRADE_USD_MIN = float(os.getenv("WHALE_TRADE_USD_MIN", "500000"))

    # Dashboard
    DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))

    # Asistente (Claude) — opcional. Si se deja vacío, el botón de "Pregúntale
    # al asistente" del dashboard muestra un mensaje explicando que falta
    # configurar la clave, y el resto del proyecto sigue funcionando gratis
    # como siempre (esto es lo único del proyecto que consume créditos de API).
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.POSTGRES_HOST} port={self.POSTGRES_PORT} "
            f"dbname={self.POSTGRES_DB} user={self.POSTGRES_USER} "
            f"password={self.POSTGRES_PASSWORD}"
        )


config = Config()
