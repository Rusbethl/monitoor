"""
Backend del dashboard: una API mínima (FastAPI) que en su mayoría solo LEE
de Postgres y sirve el frontend estático.

La única excepción es /api/ask: un endpoint opcional que le pasa a Claude
(vía API, si configuraste ANTHROPIC_API_KEY en .env) el contexto ya
recolectado por este mismo proyecto (noticias, snapshot de mercado, calendario,
alertas) junto con tu pregunta en lenguaje natural. Es la única parte de este
proyecto que consume créditos de API — todo lo demás sigue siendo gratis.
"""
import hashlib
import logging
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from common.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc-monitor.dashboard")

app = FastAPI(title="BTC Monitor Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_for_static(request, call_next):
    """Evita que el navegador cachee el HTML/CSS/JS del dashboard, para que
    los cambios se vean de inmediato sin necesitar modo incógnito."""
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


STATIC_DIR = Path(__file__).parent / "static"
THUMBS_DIR = STATIC_DIR / "cache" / "thumbs"
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def db():
    conn = psycopg2.connect(config.postgres_dsn)
    conn.autocommit = True
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@app.get("/api/fng")
def fear_greed():
    """
    Proxy del índice Fear & Greed de alternative.me (gratuito, sin API key).
    Se llama desde el navegador poco seguido (el índice se actualiza ~1 vez
    al día), así que no hace falta cachearlo en disco como las imágenes.
    """
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        payload = resp.json()
        item = payload["data"][0]
        return {
            "value": int(item["value"]),
            "classification": item["value_classification"],
            "timestamp": item.get("timestamp"),
        }
    except Exception:
        raise HTTPException(status_code=502, detail="No se pudo obtener el índice Fear & Greed")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "symbol": config.BINANCE_SYMBOL,
        "rsi_sobrecompra": config.RSI_SOBRECOMPRA,
        "rsi_sobreventa": config.RSI_SOBREVENTA,
        "asistente_configurado": bool(config.ANTHROPIC_API_KEY),
    }


@app.get("/api/snapshot/latest")
def snapshot_latest():
    rows = query(
        """
        SELECT ts, symbol, price, funding_rate, open_interest, long_short_ratio,
               rsi_15m, rsi_1h, rsi_4h, ema_50_1h, ema_200_1h
        FROM market_snapshots
        ORDER BY ts DESC
        LIMIT 1
        """
    )
    return rows[0] if rows else {}


@app.get("/api/snapshot/history")
def snapshot_history(hours: int = 24, limit: int = 500):
    return query(
        """
        SELECT ts, price, rsi_15m, rsi_1h, rsi_4h, funding_rate, open_interest
        FROM market_snapshots
        WHERE ts >= now() - (%s || ' hours')::interval
        ORDER BY ts ASC
        LIMIT %s
        """,
        (hours, limit),
    )


@app.get("/api/news")
def news(limit: int = 30, hours: int | None = None, is_rumor: bool | None = None):
    """
    `hours` e `is_rumor` son opcionales: sin ellos devuelve las más recientes
    en general (como antes). El panel de Rumores los usa para pedir "rumores
    de las últimas N horas", una ventana propia que no depende de cuántas
    noticias normales hayan entrado desde entonces.
    """
    clauses = []
    params: list = []
    if hours is not None:
        clauses.append("ts >= now() - (%s || ' hours')::interval")
        params.append(hours)
    if is_rumor is not None:
        clauses.append("is_rumor = %s")
        params.append(is_rumor)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    return query(
        f"""
        SELECT ts, source, title, link, matched_keywords, published_at, image_url, category, is_rumor
        FROM news_items
        {where_sql}
        ORDER BY ts DESC
        LIMIT %s
        """,
        tuple(params),
    )


@app.get("/api/alerts")
def alerts(limit: int = 30):
    return query(
        """
        SELECT ts, alert_type, message
        FROM alerts_log
        ORDER BY ts DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/api/calendar")
def calendar(upcoming_only: bool = True, limit: int = 20):
    if upcoming_only:
        return query(
            """
            SELECT event_date, title, category, impact, notes
            FROM economic_events
            WHERE event_date >= now() - interval '1 day'
            ORDER BY event_date ASC
            LIMIT %s
            """,
            (limit,),
        )
    return query(
        """
        SELECT event_date, title, category, impact, notes
        FROM economic_events
        ORDER BY event_date ASC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/api/whales")
def whales(limit: int = 30, min_usd: float = 0):
    return query(
        """
        SELECT ts, symbol, side, price, quantity, quote_value_usd
        FROM whale_trades
        WHERE quote_value_usd >= %s
        ORDER BY ts DESC
        LIMIT %s
        """,
        (min_usd, limit),
    )


@app.get("/api/img")
def proxy_image(u: str):
    """
    Proxy + caché en disco para miniaturas de noticias.

    Muchos sitios de noticias bloquean o limitan la carga directa de sus
    imágenes desde otro dominio (hotlinking), lo que hacía que el dashboard
    se quedara "cargando" imágenes que nunca llegan. Aquí las descargamos
    una vez desde el servidor (igual que ya hace el collector con el RSS),
    las guardamos en disco, y las servimos rápido desde caché las siguientes
    veces.
    """
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL inválida")

    digest = hashlib.sha256(u.encode()).hexdigest()[:24]

    for existing in THUMBS_DIR.glob(f"{digest}.*"):
        return FileResponse(str(existing), headers={"Cache-Control": "public, max-age=604800"})

    try:
        resp = requests.get(
            u,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; btc-monitor/1.0)"},
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo descargar la imagen")

    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    ext = ALLOWED_IMAGE_TYPES.get(content_type)
    if resp.status_code != 200 or not ext or len(resp.content) > 3_000_000:
        raise HTTPException(status_code=502, detail="Imagen no válida")

    path = THUMBS_DIR / f"{digest}.{ext}"
    path.write_bytes(resp.content)
    return Response(content=resp.content, media_type=content_type, headers={"Cache-Control": "public, max-age=604800"})


# ============================================================
# Asistente (Claude) — único endpoint que llama a una IA y consume créditos.
# ============================================================

ASK_SYSTEM_PROMPT = (
    "Eres un asistente que ayuda a un trader de futuros de BTC/USDT que opera a corto plazo "
    "con apalancamiento muy alto (entre 44x y 55x) a interpretar las noticias, datos de mercado "
    "y eventos que este dashboard ya recolectó automáticamente. Responde siempre en español, de "
    "forma clara, directa y útil para tomar decisiones de trading — nada de relleno. Cuando te "
    "pidan 'las noticias más importantes' o 'qué me ayudaría a decidir', prioriza por: qué tan "
    "reciente es cada cosa, qué tanto podría mover el precio de BTC (macro/geopolítica/petróleo "
    "suelen pesar más que noticias menores de un solo exchange), y si es un rumor sin confirmar "
    "(dilo explícitamente cuando lo sea, no lo trates como hecho). Nunca inventes datos que no "
    "estén en el contexto que se te da — si algo no está ahí, dilo abiertamente en vez de "
    "adivinar. No des garantías de dirección de precio: el mercado puede moverse en cualquier "
    "sentido y esto es solo apoyo de contexto y de gestión de riesgo, no una señal de compra o "
    "venta. Sé breve pero completo, y usa viñetas cuando eso ayude a la claridad."
)


class AskIn(BaseModel):
    question: str


def _recent_context() -> str:
    """Arma un resumen en texto plano de lo último que este proyecto ya
    recolectó, para dárselo a Claude como contexto junto con la pregunta."""
    news_rows = query(
        """
        SELECT ts, source, title, category, is_rumor
        FROM news_items
        ORDER BY ts DESC
        LIMIT 25
        """
    )
    snapshot_rows = query(
        """
        SELECT ts, price, funding_rate, open_interest, long_short_ratio,
               rsi_15m, rsi_1h, rsi_4h, ema_50_1h, ema_200_1h
        FROM market_snapshots
        ORDER BY ts DESC
        LIMIT 1
        """
    )
    calendar_rows = query(
        """
        SELECT event_date, title, category, impact
        FROM economic_events
        WHERE event_date >= now() - interval '1 day'
        ORDER BY event_date ASC
        LIMIT 6
        """
    )
    alert_rows = query(
        """
        SELECT ts, alert_type, message
        FROM alerts_log
        ORDER BY ts DESC
        LIMIT 8
        """
    )

    lines = ["=== Noticias recientes (más nueva primero) ==="]
    if news_rows:
        for r in news_rows:
            rumor_tag = " [RUMOR, sin confirmar]" if r["is_rumor"] else ""
            lines.append(f"- ({r['category']}) {r['title']} — {r['source']}{rumor_tag}")
    else:
        lines.append("(sin noticias recientes en la base de datos todavía)")

    lines.append("\n=== Snapshot de mercado más reciente ===")
    if snapshot_rows:
        s = snapshot_rows[0]
        lines.append(
            f"Precio: {s['price']} | Funding: {s['funding_rate']} | "
            f"Open Interest: {s['open_interest']} | Long/Short: {s['long_short_ratio']} | "
            f"RSI 15m/1h/4h: {s['rsi_15m']}/{s['rsi_1h']}/{s['rsi_4h']} | "
            f"EMA50/EMA200 (1h): {s['ema_50_1h']}/{s['ema_200_1h']}"
        )
    else:
        lines.append("(sin snapshot de mercado todavía)")

    lines.append("\n=== Próximos eventos económicos ===")
    if calendar_rows:
        for c in calendar_rows:
            lines.append(f"- {c['event_date']}: {c['title']} ({c['category']}, impacto {c['impact']})")
    else:
        lines.append("(sin eventos próximos cargados)")

    lines.append("\n=== Alertas técnicas recientes ===")
    if alert_rows:
        for a in alert_rows:
            lines.append(f"- {a['ts']}: [{a['alert_type']}] {a['message']}")
    else:
        lines.append("(sin alertas recientes)")

    return "\n".join(lines)


@app.post("/api/ask")
def ask(payload: AskIn):
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=400,
            detail=(
                "Falta configurar ANTHROPIC_API_KEY en el archivo .env para usar el asistente. "
                "Copia tu clave del Claude Console y agrégala ahí (mira .env.example)."
            ),
        )
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Escribe una pregunta.")

    import anthropic  # import perezoso: si falta la librería, solo afecta a este endpoint

    context_block = _recent_context()
    user_message = (
        f"Contexto recolectado por el dashboard ahora mismo:\n\n{context_block}\n\n"
        f"Pregunta del usuario: {question}"
    )

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1000,
            system=ASK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = "".join(getattr(block, "text", "") for block in response.content)
    except Exception as exc:
        logger.exception("Error llamando a Claude en /api/ask")
        raise HTTPException(status_code=502, detail=f"No se pudo obtener respuesta del asistente: {exc}")

    return {"answer": text.strip()}


# Frontend estático (debe ir al final para no tapar las rutas /api/*)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
