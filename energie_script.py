import re
import json
import requests
from datetime import datetime, date

BASE_URL = "https://www.energy-charts.info/charts/energy_pie/chart.htm"
OUTPUT_FILE = "energie.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; energy-pie-scraper/1.1)"
}

def _to_float_percent(s: str) -> float:
    # "50,7" oder "50.7" -> 50.7
    return float(s.replace(",", ".").strip())

def _fmt_percent_de(x: float) -> str:
    # 50.7 -> "50,7%"
    return f"{x:.1f}%".replace(".", ",")

def fetch_pie_values(year: int):
    """
    Liest die Prozentwerte direkt aus der Energy-Charts Pie-Seite aus:
    interval=year, source=total, country=DE, language=de, year=YYYY
    """
    params = {
        "l": "de",
        "c": "DE",
        "interval": "year",
        "source": "total",
        "year": str(year)  # Auto-Jahr
    }

    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    html = r.text

    # Stand-Datum (deutsch: "Stand: 05.03.2026")
    m_date = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", html)
    if m_date:
        stand = m_date.group(1)
    else:
        # Fallback: englisch "last update: 03/04/2026" kommt auf Energy-Charts-Seiten vor
        m2 = re.search(r"last update:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", html, re.IGNORECASE)
        if m2:
            dt = datetime.strptime(m2.group(1), "%m/%d/%Y")
            stand = dt.strftime("%d.%m.%Y")
        else:
            stand = datetime.now().strftime("%d.%m.%Y")

    # Prozentwerte: "Erneuerbar ... 50,7 %" und "Fossil ... 49,3 %"
    # Robust: Wir erlauben beliebigen Text dazwischen.
    m_ren = re.search(
        r"(Erneuerbar|Renewable)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%",
        html,
        re.IGNORECASE | re.DOTALL
    )
    m_fos = re.search(
        r"(Fossil)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%",
        html,
        re.IGNORECASE | re.DOTALL
    )

    if not m_ren or not m_fos:
        # Debug: HTML wegspeichern, falls Energy-Charts das Markup geändert hat
        with open("debug_energy_pie.html", "w", encoding="utf-8") as f:
            f.write(html)
        raise RuntimeError(
            "Konnte Erneuerbar/Fossil-Prozente nicht finden. "
            "debug_energy_pie.html wurde geschrieben – bitte darin nach den Labels suchen."
        )

    ren = _to_float_percent(m_ren.group(2))
    fos = _to_float_percent(m_fos.group(2))

    return stand, ren, fos

def build_infogram_json(stand_ddmmyyyy: str, ren: float, fos: float):
    # Format entspricht deinem bisherigen JSON-Layout
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
