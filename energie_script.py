import os
import re
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "energie.json"
TMP_FILE = "energie.json.tmp"

URL = "https://www.energy-charts.info/charts/energy_pie/chart.htm?l=de&c=DE&interval=year&source=total"

def fmt_percent_de(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")

def to_float_percent(s: str) -> float:
    return float(s.replace(",", ".").strip())

def extract_stand(text: str) -> str:
    # "Stand: 06.03.2026"
    m = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
    if m:
        return m.group(1)

    # "letztes Update: 02/24/2026, ..." oder "last update: 02/24/2026, ..."
    m = re.search(r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
    if m:
        dt = datetime.strptime(m.group(2), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    return datetime.now().strftime("%d.%m.%Y")

def safe_write_json(data: list):
    # Erst tmp schreiben, dann atomar ersetzen -> letzter Stand bleibt bei Fehlern erhalten
    with open(TMP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(TMP_FILE, OUTPUT_FILE)

def build_infogram_json(stand: str, renewable: float, fossil: float) -> list:
    return [[
        ["", f"Stand: {stand}"],
        ["Erneuerbar", fmt_percent_de(renewable)],
        ["Fossil", fmt_percent_de(fossil)]
    ]]

def pick_plausible(values, lo=20.0, hi=80.0):
    """Wähle einen plausiblen Anteil (typisch Summenwert)"""
    vals = [v for v in values if lo <= v <= hi]
    if not vals:
        return None
    # Nimm den Wert, der am nächsten bei 50 liegt
    return min(vals, key=lambda x: abs(x - 50.0))

def extract_percent_candidates(text: str):
    """
    Kandidaten aus gerendertem Text extrahieren.
    Achtung: 'Fossil oil' etc. enthält auch 'Fossil' — daher später Plausibilitätsfilter.
    """
    # alles auf eine Zeile normalisieren, damit DOTALL nicht nötig ist
    t = " ".join(text.split())

    fossil_candidates = [
        to_float_percent(x)
        for x in re.findall(r"\bFossil\b[^%]{0,120}?([0-9]{1,3}[,\.][0-9])\s*%", t, flags=re.IGNORECASE)
    ]

    # \bErneuerbar\b verhindert Match in "Erneuerbarer Müll"
    renewable_candidates = [
        to_float_percent(x)
        for x in re.findall(r"\bErneuerbar\b[^%]{0,120}?([0-9]{1,3}[,\.][0-9])\s*%", t, flags=re.IGNORECASE)
    ]

    return renewable_candidates, fossil_candidates

def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(locale="de-DE")
            page.goto(URL, wait_until="networkidle", timeout=90000)

            rendered_text = page.inner_text("body")
            browser.close()

        # In CI kann ohne JS nur eine Shell kommen, daher Debug bei Bedarf [1](https://www.energy-charts.info/charts/energy_pie/chart.htm?l=fr&c=DE&source=total&interval=month&legendItems=0wf&month=11)[2](https://energy-charts.info/charts/energy_pie/chart.htm?l=de&c=DE&interval=year)
        if "enable Javascript" in rendered_text or "enable JavaScript" in rendered_text:
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(rendered_text)
            raise RuntimeError("Nur JS-Shell erhalten. debug_rendered_text.txt wurde geschrieben.")

        stand = extract_stand(rendered_text)

        ren_candidates, fos_candidates = extract_percent_candidates(rendered_text)

        # 1) Fossil: plausiblen Summenwert wählen (zwischen 20 und 80)
        fossil = pick_plausible(fos_candidates)
        if fossil is None:
            # Debug schreiben
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(rendered_text)
            raise RuntimeError("Konnte keinen plausiblen Fossil-Summenwert finden.")

        # 2) Erneuerbar: plausiblen Summenwert wählen
        renewable = pick_plausible(ren_candidates)

        # 3) Wenn Erneuerbar fehlt oder offensichtlich ein Slice (<10), aus Fossil berechnen
        if renewable is None or renewable < 10.0:
            renewable = round(100.0 - fossil, 1)

        # Finale Plausibilitätskorrektur: Summe exakt auf 100 (1 Nachkommastelle)
        # (damit es genauso sauber ist wie auf der Seite)
        fossil = round(fossil, 1)
        renewable = round(100.0 - fossil, 1)

        data = build_infogram_json(stand, renewable, fossil)
        safe_write_json(data)

        print("OK: energie.json aktualisiert")
        print("Stand:", stand, "| Erneuerbar:", renewable, "| Fossil:", fossil)

    except Exception as e:
        # letzten Stand behalten
        if os.path.exists(TMP_FILE):
            try:
                os.remove(TMP_FILE)
            except:
                pass
        print("WARNUNG: Update fehlgeschlagen – energie.json bleibt unverändert.")
        print("Fehler:", e)
        return  # Exit 0

if __name__ == "__main__":
    main()
