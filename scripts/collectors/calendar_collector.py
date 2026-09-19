"""
Calendario económico (fechas de la Fed / FOMC).

No existe una API pública y gratuita confiable para esto, así que se mantiene
como una lista fija en este archivo. Fuente: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

IMPORTANTE: la Fed publica el calendario del año siguiente normalmente a
mediados de año. Cuando cambie el año, actualiza la lista FOMC_2026 (o agrega
FOMC_2027) con las fechas oficiales del sitio de la Fed.

Cada reunión FOMC dura 2 días; la decisión de tasa se anuncia a las 2:00pm ET
del último día, seguida de la conferencia de prensa a las 2:30pm ET. Se guarda
la fecha del último día con hora aproximada en UTC (puede variar 1h según
horario de verano en EE.UU.).
"""
import logging

logger = logging.getLogger(__name__)

# (fecha ISO del último día de la reunión, hora aprox. del anuncio en UTC)
FOMC_2026 = [
    ("2026-01-28", "19:00"),
    ("2026-03-18", "18:00"),
    ("2026-04-29", "18:00"),
    ("2026-06-17", "18:00"),
    ("2026-07-29", "18:00"),
    ("2026-09-16", "18:00"),
    ("2026-10-28", "18:00"),
    ("2026-12-09", "19:00"),
]


def collect() -> list[dict]:
    """Devuelve la lista de eventos económicos conocidos (por ahora, solo FOMC)."""
    events = []
    for date_str, time_str in FOMC_2026:
        events.append({
            "event_date": f"{date_str}T{time_str}:00Z",
            "title": f"Decisión de tasas FOMC ({date_str})",
            "category": "fed",
            "impact": "alto",
            "notes": "Anuncio de tasa de interés + conferencia de prensa del presidente de la Fed.",
            "source": "manual",
        })
    logger.info("Calendario económico: %s eventos cargados.", len(events))
    return events
