-- Esquema inicial para btc-monitor
-- Se ejecuta automáticamente al levantar el contenedor de Postgres (docker-entrypoint-initdb.d)

CREATE TABLE IF NOT EXISTS market_snapshots (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol          TEXT NOT NULL,
    price           NUMERIC,
    funding_rate    NUMERIC,
    open_interest   NUMERIC,
    long_short_ratio NUMERIC,
    rsi_15m         NUMERIC,
    rsi_1h          NUMERIC,
    rsi_4h          NUMERIC,
    ema_50_1h       NUMERIC,
    ema_200_1h      NUMERIC,
    raw_json        JSONB
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_ts ON market_snapshots (ts DESC);

CREATE TABLE IF NOT EXISTS news_items (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          TEXT,
    title           TEXT,
    link            TEXT UNIQUE,
    matched_keywords TEXT,
    published_at    TIMESTAMPTZ,
    image_url       TEXT,
    category        TEXT,           -- 'bitcoin', 'macro', 'regulacion', 'exchange', 'general'
    sent_to_notion  BOOLEAN DEFAULT FALSE,
    sent_to_telegram BOOLEAN DEFAULT FALSE
);

-- Por si la tabla ya existía de una instalación previa sin estas columnas
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS is_rumor BOOLEAN DEFAULT FALSE;

-- Backfill: marca como rumor cualquier noticia ya guardada que coincida con
-- el mismo patrón de palabras clave que usa el collector para las nuevas.
-- Seguro de correr más de una vez.
UPDATE news_items
SET is_rumor = TRUE
WHERE is_rumor IS NOT TRUE
  AND title ~* '(rumor|rumour|reportedly|sources say|according to sources|unconfirmed|alleged|could be|may consider|in talks|speculat|said to be|considering)';

CREATE INDEX IF NOT EXISTS idx_news_items_ts ON news_items (ts DESC);

CREATE TABLE IF NOT EXISTS alerts_log (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    alert_type      TEXT,
    message         TEXT,
    payload_json    JSONB,
    sent_to_telegram BOOLEAN DEFAULT FALSE,
    sent_to_notion  BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_alerts_log_ts ON alerts_log (ts DESC);

-- Calendario económico (FOMC, CPI, NFP, etc.)
CREATE TABLE IF NOT EXISTS economic_events (
    id              SERIAL PRIMARY KEY,
    event_date      TIMESTAMPTZ NOT NULL,
    title           TEXT NOT NULL,
    category        TEXT,           -- 'fed', 'cpi', 'nfp', 'otro'
    impact          TEXT,           -- 'alto', 'medio', 'bajo'
    notes           TEXT,
    source          TEXT DEFAULT 'manual',
    UNIQUE (event_date, title)
);

CREATE INDEX IF NOT EXISTS idx_economic_events_date ON economic_events (event_date);

-- Trades grandes ("whale trades") detectados en Binance Futures
CREATE TABLE IF NOT EXISTS whale_trades (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol          TEXT NOT NULL,
    side            TEXT,           -- 'compra' o 'venta'
    price           NUMERIC,
    quantity        NUMERIC,
    quote_value_usd NUMERIC,        -- price * quantity, para filtrar/ordenar por tamaño en USD
    trade_id        BIGINT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_whale_trades_ts ON whale_trades (ts DESC);
