"""
Recolector de datos de mercado y derivados desde la API pública de Binance
(Futuros USDT-M). No requiere API key para estos endpoints.

Recolecta:
 - Precio actual
 - Funding Rate (más reciente)
 - Open Interest
 - Long/Short Ratio (cuentas globales)
 - RSI y EMA en 15m, 1h y 4h (calculados con pandas puro, sin librerías externas)
"""
import logging

import pandas as pd
import requests

from common.config import config

logger = logging.getLogger(__name__)

FUTURES_BASE = "https://fapi.binance.com"

session = requests.Session()
session.headers.update({"User-Agent": "btc-monitor/1.0"})


def _get(path: str, params: dict | None = None, base: str = FUTURES_BASE):
    url = f"{base}{path}"
    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_price(symbol: str) -> float:
    data = _get("/fapi/v1/ticker/price", {"symbol": symbol})
    return float(data["price"])


def get_funding_rate(symbol: str) -> float:
    data = _get("/fapi/v1/premiumIndex", {"symbol": symbol})
    return float(data["lastFundingRate"])


def get_open_interest(symbol: str) -> float:
    data = _get("/fapi/v1/openInterest", {"symbol": symbol})
    return float(data["openInterest"])


def get_long_short_ratio(symbol: str) -> float | None:
    """Ratio global de cuentas long/short (últimos 5 min)."""
    data = _get(
        "/futures/data/globalLongShortAccountRatio",
        {"symbol": symbol, "period": "5m", "limit": 1},
    )
    if not data:
        return None
    return float(data[-1]["longShortRatio"])


def get_klines(symbol: str, interval: str, limit: int = 250) -> pd.DataFrame:
    data = _get(
        "/fapi/v1/klines",
        {"symbol": symbol, "interval": interval, "limit": limit},
    )
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(data, columns=cols)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    return df


def compute_rsi(df: pd.DataFrame, length: int = 14) -> float | None:
    """RSI estilo Wilder, calculado con pandas puro (sin pandas-ta)."""
    if df is None or len(df) < length + 1:
        return None
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.dropna()
    if rsi.empty:
        return None
    return float(rsi.iloc[-1])


def compute_ema(df: pd.DataFrame, length: int) -> float | None:
    if df is None or len(df) < length:
        return None
    ema = df["close"].ewm(span=length, adjust=False).mean().dropna()
    if ema.empty:
        return None
    return float(ema.iloc[-1])


def collect(symbol: str | None = None) -> dict:
    symbol = symbol or config.BINANCE_SYMBOL
    logger.info("Recolectando datos de mercado para %s...", symbol)

    price = get_price(symbol)
    funding_rate = get_funding_rate(symbol)
    open_interest = get_open_interest(symbol)
    long_short_ratio = get_long_short_ratio(symbol)

    df_15m = get_klines(symbol, "15m", limit=250)
    df_1h = get_klines(symbol, "1h", limit=250)
    df_4h = get_klines(symbol, "4h", limit=250)

    rsi_15m = compute_rsi(df_15m)
    rsi_1h = compute_rsi(df_1h)
    rsi_4h = compute_rsi(df_4h)
    ema_50_1h = compute_ema(df_1h, 50)
    ema_200_1h = compute_ema(df_1h, 200)

    result = {
        "symbol": symbol,
        "price": price,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "long_short_ratio": long_short_ratio,
        "rsi_15m": rsi_15m,
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "ema_50_1h": ema_50_1h,
        "ema_200_1h": ema_200_1h,
    }
    logger.info("Snapshot de mercado: %s", result)
    return result


def evaluate_alerts(snapshot: dict) -> list[dict]:
    """Revisa el snapshot contra los umbrales configurados y devuelve alertas a disparar."""
    alerts = []

    fr = snapshot.get("funding_rate")
    if fr is not None and abs(fr) >= config.FUNDING_RATE_ALERTA:
        direction = "positivo (longs pagan)" if fr > 0 else "negativo (shorts pagan)"
        alerts.append({
            "type": "funding_rate_extremo",
            "message": (
                f"Funding rate extremo en {snapshot['symbol']}: {fr:.5f} ({direction}). "
                f"Umbral configurado: {config.FUNDING_RATE_ALERTA}"
            ),
        })

    for tf in ("rsi_15m", "rsi_1h", "rsi_4h"):
        val = snapshot.get(tf)
        if val is None:
            continue
        if val >= config.RSI_SOBRECOMPRA:
            alerts.append({
                "type": f"rsi_sobrecompra_{tf}",
                "message": f"RSI {tf} en sobrecompra: {val:.1f} (>= {config.RSI_SOBRECOMPRA})",
            })
        elif val <= config.RSI_SOBREVENTA:
            alerts.append({
                "type": f"rsi_sobreventa_{tf}",
                "message": f"RSI {tf} en sobreventa: {val:.1f} (<= {config.RSI_SOBREVENTA})",
            })

    return alerts
