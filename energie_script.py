import requests
import json
from datetime import datetime

# API endpoint für den täglichen Durchschnitt des Erneuerbaren-Anteils in Deutschland
API_URL = "https://api.energy-charts.info/ren_share_daily_avg?country=de"

# Ziel-Datei
OUTPUT_FILE = "energie.json"

def fetch_energy_data():
    print("Starte API-Abruf...")
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()
        print("Daten erfolgreich abgerufen.")
        return data
    except Exception as e:
        print("Fehler beim Abrufen der Daten:", e)
        return None

def write_to_json(data):
    print("Schreibe Daten in energie.json...")
    try:
        # Füge aktuelles Datum hinzu, um tägliche Änderung zu erzwingen
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Datei erfolgreich geschrieben.")
    except Exception as e:
        print("Fehler beim Schreiben der Datei:", e)

def main():
    data = fetch_energy_data()
    if data:
        write_to_json(data)
    else:
        print("Keine Daten zum Schreiben vorhanden.")

if __name__ == "__main__":
    main()
