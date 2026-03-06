import os
import re
import json
from datetime import date, datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "energie.json"
TMP_FILE = "energie.json.tmp"

def fmt_percent_de(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")

def to_float_percent(s: str) -> float:
    return float(s.replace(",", ".").strip())

def extract_stand(text: str) -> str:
    m = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
    if m:
        return m.group(1)

    m = re.search(r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
    if m:
        dt = datetime.strptime(m.group(2), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    return datetime.now().strftime("%d.%m.%Y")

def build_infogram_json(stand: str, ren: float, fos: float):
    return [[
        ["", f"Stand: {stand}"],
        ["Erneuerbar", fmt_percent_de(ren)],
        ["Fossil", fmt_percent_de(fos)]
    ]]

def safe_write_json(data):
    with open(TMP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(TMP_FILE, OUTPUT_FILE)

def main():
    year = date.today().year
    url = (
        "https://www.energy-charts.info/charts/energy_pie/chart.htm"
        f"?l=de&c=DE&interval=year&source=total&year={year}"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(locale="de-DE")
            page.goto(url, wait_until="networkidle", timeout=90000)
            text = page.inner_text("body")
            browser.close()

        # Werte aus gerendertem Text extrahieren
        m_ren = re.search(r"(Erneuerbar|Renewable)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE | re.DOTALL)
        m_fos = re.search(r"(Fossil)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE | re.DOTALL)

        if not m_ren or not m_fos:
            # Debug speichern
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(text)
            raise RuntimeError("Erneuerbar/Fossil nicht im gerenderten Text gefunden. debug_rendered_text.txt geschrieben.")

        ren = to_float_percent(m_ren.group(2))
        fos = to_float_percent(m_fos.group(2))
        stand = extract_stand(text)

        data = build_infogram_json(stand, ren, fos)
        safe_write_json(data)

        print("OK: energie.json aktualisiert")
        print("Stand:", stand, "| Erneuerbar:", ren, "| Fossil:", fos)

    except Exception as e:
        # Letzten Stand behalten: nichts überschreiben, Workflow grün lassen
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
