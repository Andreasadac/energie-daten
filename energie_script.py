import requests
import json
from datetime import datetime

# API endpoint
API_URL = "https://api.energy-charts.info/ren_share_daily_avg?country=de"

# Output file
OUTPUT_FILE = "energie.json"

def fetch_today_data():
    print("Starte API-Abruf...")
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        print("Daten erfolgreich abgerufen.")

        # Heutiges Datum im Format YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")

        # Filtere nur den heutigen Eintrag
        today_data = [entry for entry in data if entry.get("date") == today]

        if today_data:
            result = {
                "date": today,
                "renewable_share": today_data[0].get("value"),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            return result
        else:
            print("Keine Daten für das heutige Datum gefunden.")
            return None

    except Exception as e:
        print("Fehler beim Abrufen der Daten:", e)
        return None

def write_to_json(data):
    print("Schreibe Daten in energie.json...")
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Datei erfolgreich geschrieben.")
    except Exception as e:
        print("Fehler beim Schreiben der Datei:", e)

def main():
    data = fetch_today_data()
    if data:
        write_to_json(data)
    else:
        print("Keine Daten zum Schreiben vorhanden.")

if __name__ == "__main__":
    main()
