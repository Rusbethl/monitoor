"""
Detector de "whale trades": operaciones grandes recientes en Binance Futures
(BTC/USDT), usando el endpoint público de trades agregados (aggTrades).
No requiere API key.
"""
import logging

from common.config import config
from .binance_collector import _get, FUTURES_BASE  # reutiliza sesión/helper HTTP

logger = logging.getLogger(__name__)


def get_recent_agg_trades(symbol: str, limit: int = 1000) -> list[dict]:
    """Últimos N trades agregados. Cada uno ya viene con precio/cantidad combinados
    por Binance para operaciones ejecutadas al mismo precio/tiempo (más realista
    para detectar una orden grande que llegar dato por dato)."""
    return _get("/fapi/v1/aggTrades", {"symbol": symbol, "limit": limit}, base=FUTURES_BASE)


def collect(symbol: str | None = None) -> list[dict]:
    """Revisa los trades agregados recientes y devuelve solo los que superan
    el umbral configurado en USD (WHALE_TRADE_USD_MIN)."""
    symbol = symbol or config.BINANCE_SYMBOL
    trades = get_recent_agg_trades(symbol, limit=1000)

    whales = []
    for t in trades:
        price = float(t["p"])
        qty = float(t["q"])
        usd_value = price * qty
        if usd_value < config.WHALE_TRADE_USD_MIN:
            continue
        # "m" = True significa que el comprador fue el "maker" (orden pasiva);
        # si el comprador es maker, quien agredió el mercado fue el vendedor -> venta agresiva.
        side = "venta" if t.get("m") else "compra"
        whales.append({
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": qty,
            "quote_value_usd": usd_value,
            "trade_id": int(t["a"]),
        })

    if whales:
        logger.info("Whale trades detectados: %s (umbral $%s)", len(whales), config.WHALE_TRADE_USD_MIN)
    return whales
