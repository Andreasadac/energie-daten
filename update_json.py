import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Aktuelles Datum im gewünschten Format
datum = datetime.today().strftime("Stand: %d.%m.%Y")

# Energy-Charts-Webseite abrufen
url = "https://www.energy-charts.info/charts/energy/chart.htm?l=de&c=DE&source=public"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

# Beispielwerte (hier solltest du später echte Extraktion ergänzen)
erneuerbar = 58.8
fossil = 41.2

# JSON-Struktur
daten = [
    [
        ["", datum],
        ["Erneuerbar", erneuerbar],
        ["Fossil", fossil]
    ]
]

# Datei schreiben
with open("energie.json", "w", encoding="utf-8") as f:
    json.dump(daten, f, ensure_ascii=False, indent=2)
