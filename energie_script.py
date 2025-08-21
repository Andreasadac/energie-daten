import json
import os
import shutil
from datetime import datetime, timedelta
import requests

# Aktuelles Datum und Vortag
heute = datetime.today()
gestern = heute - timedelta(days=1)

datum_string = heute.strftime("Stand: %d.%m.%Y")
api_datum = heute.strftime("%Y-%m-%d")

# API-Endpunkt
url = f"https://api.energy-charts.info/public_power?country=de&start={api_datum}&end={api_datum}"

# API-Daten abrufen
response = requests.get(url)
data = response.json()

# Prüfen, ob 'data' vorhanden ist
if 'data' not in data or not data['data']:
    print(f"⚠️ Keine Daten verfügbar für {api_datum}. Die Datei wurde nicht aktualisiert.")
    exit(0)

# Energiequellen klassifizieren
erneuerbare_quellen = ['wind_onshore', 'wind_offshore', 'solar', 'biomass', 'hydro']
fossile_quellen = ['hard_coal', 'lignite', 'natural_gas', 'oil']

# Summen berechnen
summe_erneuerbar = 0
summe_fossil = 0
summe_gesamt = 0

for eintrag in data['data']:
    quelle = eintrag['key']
    werte = eintrag['values']
    summe = sum(werte)
    summe_gesamt += summe
    if quelle in erneuerbare_quellen:
        summe_erneuerbar += summe
    elif quelle in fossile_quellen:
        summe_fossil += summe

# Prozentuale Anteile berechnen
anteil_erneuerbar = round((summe_erneuerbar / summe_gesamt) * 100, 1) if summe_gesamt > 0 else 0
anteil_fossil = round((summe_fossil / summe_gesamt) * 100, 1) if summe_gesamt > 0 else 0

# JSON-Struktur erzeugen
struktur = [
    [
        ["", datum_string],
        ["Erneuerbar", anteil_erneuerbar],
        ["Fossil", anteil_fossil]
    ]
]

# Backup der alten Datei (falls vorhanden)
ziel_datei = "energie.json"
backup_datei = f"energie_backup_{gestern.strftime('%Y-%m-%d')}.json"

if os.path.exists(ziel_datei):
    shutil.copy(ziel_datei, backup_datei)
    print(f"📦 Backup erstellt: {backup_datei}")

# Neue JSON-Datei schreiben
with open(ziel_datei, "w", encoding="utf-8") as f:
    json.dump(struktur, f, ensure_ascii=False, indent=2)

print(f"✅ Die Datei '{ziel_datei}' wurde erfolgreich mit den Daten vom {datum_string} aktualisiert.")
