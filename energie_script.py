import requests
import json
import os
from datetime import datetime, date

# API endpoint
API_URL = "https://api.energy-charts.info/ren_share_daily_avg"

# Output file
OUTPUT_FILE = "energie.json"

# Zeitraum: Jahresanfang fix auf 01.01.2026
START_DATE = date(2026, 1, 1)

def fetch_ytd_average(start_date: date):
    """
    Holt alle Tageswerte ab start_date bis heute und berechnet den YTD-Durchschnitt.
    Gibt (last_date_str, avg_renewable_share) zurück.
    """
    try:
        today_str = date.today().strftime("%Y-%m-%d")
        start_str = start_date.strftime("%Y-%m-%d")

        # API unterstützt start/end im Daily-Format YYYY-MM-DD
        # (laut Doku: Daily Format ist gültig und interpretiert in lokaler Zeitzone) 
        params = {
            "country": "de",
            "start": start_str,
            "end": today_str
        }

        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not data:
            print("Keine Daten verfügbar (leere Antwort).")
            return None

        # Defensive: nur gültige Einträge ab START_DATE
        filtered = []
        for item in data:
            d = item.get("date")
            v = item.get("value")
            if d is None or v is None:
                continue
            try:
                d_obj = datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                continue
            if d_obj >= start_date:
                filtered.append((d_obj, float(v)))

        if not filtered:
            print("Keine Daten im gewünschten Zeitraum gefunden.")
            return None

        # Sortieren nach Datum (falls API nicht garantiert sortiert)
        filtered.sort(key=lambda x: x[0])

        # Letztes verfügbares Datum
        last_date = filtered[-1][0].strftime("%Y-%m-%d")

        # YTD Durchschnitt
        avg_renewable = sum(v for _, v in filtered) / len(filtered)

        return last_date, avg_renewable

    except Exception as e:
        print("Fehler beim Abrufen/Berechnen der Daten:", e)
        return None

def generate_json_content(date_str, renewable_share):
    fossil_share = round(100.0 - renewable_share, 1)

    datum_string = f"Stand: {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}"
    anteil_erneuerbar = f"{round(renewable_share, 1):.1f}%".replace(".", ",")
    anteil_fossil = f"{fossil_share:.1f}%".replace(".", ",")

    result = [
        [
            ["", datum_string],
            ["Erneuerbar", anteil_erneuerbar],
            ["Fossil", anteil_fossil]
        ]
    ]
    return result

def write_to_json(data):
    try:
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Datei erfolgreich geschrieben:", OUTPUT_FILE)
    except Exception as e:
        print("Fehler beim Schreiben der Datei:", e)

def main():
    entry = fetch_ytd_average(START_DATE)

    if entry:
        date_str, renewable_share = entry
    else:
        # Fallback: heutiges Datum und feste Werte (dein aktueller Stand)
        date_str = date.today().strftime("%Y-%m-%d")
        renewable_share = 48.7  # Fallback (heute laut dir)
        print("Fallback aktiv: verwende feste Werte.")

    json_data = generate_json_content(date_str, renewable_share)
    write_to_json(json_data)

if __name__ == "__main__":
    main()
