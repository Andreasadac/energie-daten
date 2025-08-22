import requests
import json
from datetime import datetime

# API endpoint
API_URL = "https://api.energy-charts.info/ren_share_daily_avg?country=de"

# Output file
OUTPUT_FILE = "energie.json"

def fetch_latest_entry():
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()

        if not data:
            print("Keine Daten verfügbar.")
            return None

        # Verwende den letzten verfügbaren Eintrag
        latest_entry = data[-1]
        date = latest_entry.get("date")
        renewable_share = latest_entry.get("value")

        if date is None or renewable_share is None:
            print("Ungültiger Eintrag im API-Ergebnis.")
            return None

        # Berechne fossil_share als Differenz zu 100%
        fossil_share = round(100.0 - renewable_share, 2)

        return {
            "date": date,
            "renewable_share": round(renewable_share, 2),
            "fossil_share": fossil_share
        }

    except Exception as e:
        print("Fehler beim Abrufen der Daten:", e)
        return None

def write_to_json(data):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Datei erfolgreich geschrieben.")
    except Exception as e:
        print("Fehler beim Schreiben der Datei:", e)

def main():
    data = fetch_latest_entry()
    if data:
        write_to_json(data)
    else:
        print("Keine Daten zum Schreiben vorhanden.")

if __name__ == "__main__":
    main()
