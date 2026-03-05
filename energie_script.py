import requests
import json
from datetime import datetime, date, timedelta

TOTAL_POWER_URL = "https://api.energy-charts.info/total_power"
OUTPUT_FILE = "energie.json"
START_DATE = date(2026, 1, 1)

# Schlüsselwörter für Erneuerbare (EN/DE, robust gegen Varianten)
RENEWABLE_KEYS = [
    "wind", "wind on", "wind off",
    "solar", "pv", "photovolta",
    "hydro", "water", "run-of-river", "reservoir",
    "biomass", "bio", "biogas",
    "geothermal",
    "erneuer", "wind", "solar", "wasser", "biomass", "biogas", "geotherm"
]

# Dinge, die NICHT zur Nettostromerzeugung im Mix zählen sollen
# (je nach API-Land/Setup tauchen diese manchmal auf)
EXCLUDE_KEYS = [
    "import", "export",
    "pumped", "pumpspeicher",
    "storage", "battery",
    "load", "consumption"
]

def norm(s: str) -> str:
    return (s or "").strip().lower()

def is_excluded(name: str) -> bool:
    n = norm(name)
    return any(k in n for k in EXCLUDE_KEYS)

def is_renewable(name: str) -> bool:
    n = norm(name)
    return any(k in n for k in RENEWABLE_KEYS)

def fetch_ytd_renew_share_total(start_date: date, end_date: date):
    params = {
        "country": "de",
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }

    r = requests.get(TOTAL_POWER_URL, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()

    unix_seconds = payload.get("unix_seconds", [])
    production_types = payload.get("production_types", [])

    if not unix_seconds or not production_types:
        raise RuntimeError("Keine Daten von /total_power erhalten.")

    renew_sum = 0.0
    total_sum = 0.0

    # optionales Debugging: Welche Typen wurden gezählt?
    counted_total = []
    counted_renew = []

    for pt in production_types:
        name = pt.get("name", "")
        data = pt.get("data", []) or []
        if not data:
            continue

        if is_excluded(name):
            continue

        s = sum(float(x) for x in data if x is not None)
        total_sum += s
        counted_total.append(name)

        if is_renewable(name):
            renew_sum += s
            counted_renew.append(name)

    if total_sum <= 0:
        raise RuntimeError("total_sum ist 0 – Klassifikation/Response prüfen.")

    share_renew = 100.0 * renew_sum / total_sum

    # "Stand" = letzter Zeitstempel der Serie (lokal interpretiert)
    last_ts = int(unix_seconds[-1])
    last_date_str = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d")

