import requests
import json
import os
from datetime import datetime, date, timedelta

TOTAL_POWER_URL = "https://api.energy-charts.info/total_power"
OUTPUT_FILE = "energie.json"
START_DATE = date(2026, 1, 1)

# Grobe Klassifikation anhand der production_type Namen
RENEWABLE_KEYS = [
    "wind", "solar", "photovolta", "pv", "hydro", "water", "biomass", "bio", "geothermal",
    "erneuer", "wass", "biomasse"
]
FOSSIL_KEYS = [
    "lignite", "braunkohle", "hard coal", "steinkohle", "coal", "gas", "oil", "fossil",
    "erdgas", "öl"
]
EXCLUDE_KEYS = [
    "pumped", "pumpspeicher", "storage", "battery", "import", "export", "load", "consumption"
]

def norm(s: str) -> str:
    return (s or "").strip().lower()

def classify(name: str) -> str:
    n = norm(name)
    if any(k in n for k in EXCLUDE_KEYS):
        return "exclude"
    if any(k in n for k in RENEWABLE_KEYS):
        return "renewable"
    if any(k in n for k in FOSSIL_KEYS):
        return "fossil"
    return "unknown"

def fetch_ytd_share_total(start_date: date, end_date: date):
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
    fossil_sum = 0.0
    unknown = []

    for pt in production_types:
        name = pt.get("name", "")
        data = pt.get("data", []) or []
        if not data:
            continue

        bucket = classify(name)
        s = sum(float(x) for x in data if x is not None)

        if bucket == "renewable":
            renew_sum += s
        elif bucket == "fossil":
            fossil_sum += s
        elif bucket == "unknown":
            unknown.append(name)
        # exclude ignorieren

    denom = renew_sum + fossil_sum
    if denom <= 0:
        raise RuntimeError("Summe (Erneuerbar+Fossil) ist 0 – Klassifikation prüfen.")

    share_renew = 100.0 * renew_sum / denom

    # Letzter Zeitstempel => Stand
    last_ts = int(unix_seconds[-1])
    last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d")

    return last_date, share_renew, unknown

def generate_json_content(date_str, renewable_share):
    fossil_share = round(100.0 - renewable_share, 1)
    datum_string = f"Stand: {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}"

    anteil_erneuerbar = f"{round(renewable_share, 1):.1f}%".replace(".", ",")
    anteil_fossil = f"{fossil_share:.1f}%".replace(".", ",")

    return [[
        ["", datum_string],
        ["Erneuerbar", anteil_erneuerbar],
        ["Fossil", anteil_fossil]
    ]]

def write_to_json(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    # Wenn du exakt “bis letzter kompletter Tag” willst:
    # end = date.today() - timedelta(days=1)
    end = date.today()

    date_str, share_renew, unknown = fetch_ytd_share_total(START_DATE, end)

    if unknown:
        print("Hinweis: Unbekannte Produktionstypen (nicht zugeordnet):", unknown)

    json_data = generate_json_content(date_str, share_renew)
    write_to_json(json_data)
    print("OK:", OUTPUT_FILE, "| Erneuerbar:", round(share_renew, 1), "%")

if __name__ == "__main__":
    main()
