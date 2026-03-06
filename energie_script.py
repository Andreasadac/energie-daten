import os
import json
import re
from datetime import date, datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "energie.json"
TMP_FILE = "energie.json.tmp"

def fmt_percent_de(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")

def to_float_percent(s: str) -> float:
    return float(s.replace(",", ".").strip())

def safe_write_json(data, path_tmp=TMP_FILE, path_final=OUTPUT_FILE):
    with open(path_tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(path_tmp, path_final)  # atomar

def build_infogram_json(stand_ddmmyyyy: str, ren: float, fos: float):
    return [[
        ["", f"Stand: {stand_ddmmyyyy}"],
        ["Erneuerbar", fmt_percent_de(ren)],
        ["Fossil", fmt_percent_de(fos)]
    ]]

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

        # Extraktion (ggf. Regex anpassen, wenn du schon eine funktionierende Version hast)
        m_stand = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
        if m_stand:
            stand = m_stand.group(1)
        else:
            m_upd = re.search(r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
            stand = datetime.strptime(m_upd.group(2), "%m/%d/%Y").strftime("%d.%m.%Y") if m_upd else datetime.now().strftime("%d.%m.%Y")

        m_ren = re.search(r"(Erneuerbar|Renewable)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE | re.DOTALL)
        m_fos = re.search(r"(Fossil)\s*.*?([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE | re.DOTALL)
        if not m_ren or not m_fos:
            raise RuntimeError("Konnte Prozentwerte nicht aus dem gerenderten Text extrahieren.")

        ren = to_float_percent(m_ren.group(2))
        fos = to_float_percent(m_fos.group(2))

        data = build_infogram_json(stand, ren, fos)
        safe_write_json(data)

        print("OK: energie.json aktualisiert:", ren, fos, "Stand:", stand)

    except Exception as e:
        # WICHTIG: letzten Stand behalten -> kein Overwrite, kein Crash
        if os.path.exists(TMP_FILE):
            try:
                os.remove(TMP_FILE)
            except:
                pass
        print("WARNUNG: Update fehlgeschlagen, letzter Stand bleibt erhalten.")
        print("Fehler:", e)

        # Exit 0: Workflow bleibt grün, und Commit-Step findet keine Änderungen
        return

if __name__ == "__main__":
    main()
