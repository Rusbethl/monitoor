# btc-monitor

Sistema de monitoreo 24/7 para BTC/USDT (futuros perpetuos), 100% gratuito.
Corre en Docker en tu propia PC (debe quedarse encendida), guarda histórico en
Postgres/TimescaleDB, y publica un resumen ejecutivo en Notion + alertas a
Telegram. La interpretación profunda sigue haciéndose en Claude (Pro), trayendo
el resumen ya recolectado a la conversación.

## Qué hace

1. **Collector de mercado** (cada 15 min por defecto): precio, funding rate,
   open interest, long/short ratio y RSI/EMA (15m, 1h, 4h) desde la API
   pública de Binance Futures. Guarda todo en Postgres y en la base de Notion
   "Snapshots de mercado". Si algo cruza un umbral (funding extremo, RSI en
   sobrecompra/sobreventa), dispara una alerta a Telegram y a Notion.

2. **Collector de noticias** (cada 20 min por defecto): lee RSS de CoinDesk,
   CoinTelegraph, Reuters e Investing.com, filtra por keywords relevantes
   (Fed, Trump, petróleo, Irán, BTC/crypto, etc.), evita duplicados, y guarda
   cada noticia nueva en Postgres + Notion ("Eventos del día") + Telegram.

3. **Notion** funciona como bitácora/knowledge base que puedes abrir desde el
   celular o la PC para ver de un vistazo qué pasó, sin tener que pedirle a
   Claude que "ejecute los comandos" — ya está recolectado solo.

4. **Calendario económico** (cada 12h): mantiene las fechas de las próximas
   reuniones FOMC de la Fed (lista fija en `scripts/collectors/calendar_collector.py`,
   hay que actualizarla cuando la Fed publique el calendario del año siguiente).

5. **Whale trades** (cada 5 min por defecto): detecta operaciones grandes
   recientes en Binance Futures (BTC/USDT) usando el endpoint público de trades
   agregados, sin necesidad de API key. El umbral en USD se configura con
   `WHALE_TRADE_USD_MIN`.

6. **Dashboard web** (`http://localhost:8000` una vez levantado): un panel
   minimalista, oscuro y en vivo (se actualiza solo cada 20s) con precio,
   gráficas de RSI, alertas, noticias, calendario económico y whale trades —
   todo en una sola pantalla, sin depender de Notion. Es de solo lectura, no
   escribe nada ni llama a ninguna IA.

## Lo que este proyecto NO hace (por diseño, para mantenerlo gratuito)

- No hay un agente de IA corriendo 24/7 interpretando y respondiendo solo
  (eso requiere presupuesto de API tokens). La interpretación profunda de
  gráficos, mapas de liquidez y la conclusión final sigue siendo esta
  conversación de Claude Pro — pero ahora con datos ya organizados en Notion
  en vez de tener que pedir los 2 comandos manualmente.
- No incluye (todavía) las alertas técnicas de TradingView + Pipedream
  (divergencias de RSI, cruces de EMA, toques de niveles). Eso se agrega
  aparte configurando alertas en Pine Script apuntando a un webhook de
  Pipedream (gratis) que reenvíe a este mismo bot de Telegram — no requiere
  cambios de código aquí, es configuración en TradingView.

## Instalación

### 1. Requisitos
- Docker y Docker Compose instalados en tu PC.
- Una cuenta de Notion (gratis) con una integración creada en
  https://www.notion.so/my-integrations
- Un bot de Telegram creado con @BotFather, y tu chat_id (puedes obtenerlo
  hablándole a @userinfobot).

### 2. Configura Notion
Crea 3 bases de datos en Notion (pueden estar en la misma página):

- **Eventos del día**: propiedades `Título` (title), `Fuente` (text),
  `Keywords` (text), `Link` (url), `Publicado` (date).
- **Snapshots de mercado**: `Título` (title), `Precio`, `Funding Rate`,
  `Open Interest`, `Long/Short`, `RSI 15m`, `RSI 1h`, `RSI 4h`, `EMA50 1h`,
  `EMA200 1h` (todas tipo number).
- **Alertas técnicas**: `Título` (title), `Tipo` (text), `Mensaje` (text).

Comparte cada una de las 3 bases con tu integración ("..." → "Add connections").
Copia el ID de cada base (está en la URL, el bloque de 32 caracteres antes de `?v=`).

### 3. Configura el proyecto
```bash
cd btc-monitor
cp .env.example .env
# Edita .env y llena: password de Postgres, NOTION_TOKEN y los 3 NOTION_DB_*,
# TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
```

### 4. Levanta todo
```bash
docker compose up -d --build
docker compose logs -f collector
```

Deberías ver en los logs el primer snapshot de mercado y, si hay noticias
relevantes recientes, el primer lote de noticias — y recibir mensajes en tu
Telegram si algo cruza un umbral.

### 5. Verifica en Notion
Abre tus 3 bases y confirma que están llegando filas nuevas cada 15-20 min.

### 6. Abre el dashboard
Ve a `http://localhost:8000` en tu navegador (misma PC, o desde el celular si
está en la misma red WiFi usando la IP local de tu PC, ej. `http://192.168.1.x:8000`).

## Estructura del proyecto

```
btc-monitor/
├── docker-compose.yml       # DB (TimescaleDB) + collector
├── Dockerfile                # imagen del collector
├── requirements.txt
├── .env.example
├── sql/schema.sql            # se ejecuta automático al crear el contenedor de DB
└── scripts/
    ├── main.py               # orquestador con cron interno (schedule)
    ├── common/
    │   ├── config.py         # lee .env
    │   └── db.py             # helpers de Postgres
    ├── collectors/
    │   ├── binance_collector.py   # precio, funding, OI, RSI/EMA
    │   ├── news_collector.py      # RSS + filtro de keywords
    │   ├── whale_collector.py     # trades grandes (Binance aggTrades)
    │   └── calendar_collector.py  # calendario económico (FOMC)
    ├── notion/
    │   └── notion_writer.py       # escribe a las 3 bases de Notion
    ├── telegram/
    │   └── telegram_bot.py        # envía alertas y noticias
    └── dashboard/
        ├── app.py                 # API (FastAPI) que sirve el dashboard
        └── static/                # frontend (HTML/CSS/JS, sin frameworks)
```

## Ajustar umbrales y frecuencia

Todo se controla desde `.env`:
- `INTERVALO_MERCADO_MIN` / `INTERVALO_NOTICIAS_MIN`: cada cuánto recolecta.
- `FUNDING_RATE_ALERTA`: dispara alerta si `|funding_rate| >= este valor`.
- `RSI_SOBRECOMPRA` / `RSI_SOBREVENTA`: umbrales de RSI para alertar.

## Próximos pasos sugeridos

1. Agregar alertas de TradingView (Pine Script) → Pipedream (webhook gratis)
   → mismo bot de Telegram, para las divergencias de RSI y cruces de EMA que
   el collector de Binance por sí solo no detecta con la misma precisión que
   un indicador visual en TradingView.
2. Si en algún momento amplías presupuesto, reemplazar la clasificación
   manual de noticias (rumor vs. confirmado) por un paso automático con
   Claude Haiku (barato por token) antes de que llegue a Telegram/Notion.
