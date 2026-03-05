import re
import json
import requests
from datetime import datetime, date

BASE_URL = "https://energy-charts.info/charts/energy_pie/chart.htm"  # ohne www
OUTPUT_FILE = "energie.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; energy-pie-scraper/1.2)"
}

def _to_float(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".").strip()) if "," in s else float(s.strip())

def _to_percent_float(s: str) -> float:
    # "50,7" oder "50.7" -> 50.7
    return float(s.replace(",", ".").strip())

def _fmt_percent_de(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")

def _extract_update_date(html: str) -> str:
    # Deutsch: "letztes Update: 02/28/2026, 11:17 AM GMT+1"
    m_de = re.search(r"letztes\s+Update:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", html, re.IGNORECASE)
    if m_de:
        dt = datetime.strptime(m_de.group(1), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    # Englisch: "last update: 03/04/2026, 3:30 AM GMT+1"
    m_en = re.search(r"last\s+update:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", html, re.IGNORECASE)
    if m_en:
        dt = datetime.strptime(m_en.group(1), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    # Manche Seiten haben "Stand: 05.03.2026"
    m_stand = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", html)
    if m_stand:
        return m_stand.group(1)

    # Fallback
    return datetime.now().strftime("%d.%m.%Y")

def fetch_pie_values(year: int):
    params = {
        "l": "de",
        "c": "DE",
        "interval": "year",
        "source": "total",
        "year": str(year),  # wichtig!
    }

    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    html = r.text

    # Wenn wir aus Versehen wieder in der JS-Shell landen, steht dieser Hinweis drin:
    if "enable Javascript" in html or "enable JavaScript" in html:
        with open("debug_energy_pie.html", "w", encoding="utf-8") as f:
            f.write(html)
        raise RuntimeError(
            "Energy-Charts liefert eine JavaScript-Shell (keine Daten im HTML). "
            "Prüfe Domain (ohne www) und Parameter. debug_energy_pie.html geschrieben."
        )

    stand = _extract_update_date(html)

    # Summary-Zeilen: "Erneuerbar <TWh> <percent> %" und "Fossil <TWh> <percent> %"
    # Beispiel aus der Seite: "Erneuerbar 278.89 TWh 58.9 %" / "Fossil 194.60 TWh 41.1 %" [2](https://www.energy-charts.info/charts/energy_pie/chart.htm?l=de&c=DE&source=total&interval=year&year=2024)
    m_ren = re.search(r"Erneuerbar\s+([0-9\.,]+)\s*TWh\s+([0-9\.,]+)\s*%", html)
    m_fos = re.search(r"Fossil\s+([0-9\.,]+)\s*TWh\s+([0-9\.,]+)\s*%", html)

    if not m_ren or not m_fos:
        with open("debug_energy_pie.html", "w", encoding="utf-8") as f:
            f.write(html)
        raise RuntimeError(
            "Konnte Summary-Prozente nicht finden. debug_energy_pie.html geschrieben."
        )

    ren_percent = _to_percent_float(m_ren.group(2))
    fos_percent = _to_percent_float(m_fos.group(2))

    return stand, ren_percent, fos_percent

def build_infogram_json(stand_ddmmyyyy: str, ren: float, fos: float):
    return [[
        ["", f"Stand: {stand_ddmmyyyy}"],
        ["Erneuerbar", _fmt_percent_de(ren)],
        ["Fossil", _fmt_percent_de(fos)]
    ]]

def main():
    year = date.today().year  # AUTO
    stand, ren, fos = fetch_pie_values(year)

    data = build_infogram_json(stand, ren, fos)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("OK:", OUTPUT_FILE)
    print("Jahr:", year, "| Stand:", stand, "| Erneuerbar:", ren, "| Fossil:", fos)

if __name__ == "__main__":
    main()
