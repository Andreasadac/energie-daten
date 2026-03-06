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
    # "Stand: 06.03.2026"
    m = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
    if m:
        return m.group(1)

    # "letztes Update: 02/24/2026, ..." oder "last update: 02/24/2026, ..."
    m = re.search(r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
                  text, re.IGNORECASE)
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

def extract_summary_percentages(rendered_text: str) -> tuple[float, float]:
    """
    Extrahiert NUR die Summenwerte aus Zeilen wie:
      Erneuerbar 18,286.28 GWh 49.3 %
      Fossil     18,792.16 GWh 50.7 %
    (Beispiel solcher Summenzeilen in Energy-Charts-Pie-Ausgaben.) [3](https://energy-charts.info/charts/energy_pie/chart.htm)

    Wichtig:
    - Wortgrenzen \bErneuerbar\b verhindern Match in "Erneuerbarer Müll"
    - Wir akzeptieren GWh/TWh (Summary), nicht die Segment-Prozente
    - Wir wählen das Paar, dessen Summe am nächsten bei 100 liegt
    """

    # Zeilenweise analysieren (robuster als "alles in einer Zeile")
    lines = [" ".join(l.strip().split()) for l in rendered_text.splitlines() if l.strip()]

    # Summary-Zeilen (DE/EN tolerant)
    ren_re = re.compile(r"^\b(Erneuerbar|Renewable)\b\s+[0-9\.,]+\s*(GWh|TWh)\s+([0-9]{1,3}[,\.][0-9])\s*%$",
                        re.IGNORECASE)
    fos_re = re.compile(r"^\bFossil\b\s+[0-9\.,]+\s*(GWh|TWh)\s+([0-9]{1,3}[,\.][0-9])\s*%$",
                        re.IGNORECASE)

    ren_vals = []
    fos_vals = []

    for line in lines:
        m = ren_re.match(line)
        if m:
            ren_vals.append(to_float_percent(m.group(3)))
            continue
        m = fos_re.match(line)
        if m:
            fos_vals.append(to_float_percent(m.group(2)))

    if not ren_vals or not fos_vals:
        # Debug: genau den gerenderten Text sichern
        with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
            f.write(rendered_text)
        raise RuntimeError(
            "Summen-Zeilen nicht gefunden (Erneuerbar/Fossil mit GWh/TWh). "
            "debug_rendered_text.txt wurde geschrieben."
        )

    # Bestes Paar wählen: ren + fos ≈ 100
    best = None
    best_diff = 999.0
    for r in ren_vals:
        for f in fos_vals:
            diff = abs((r + f) - 100.0)
            if diff < best_diff:
                best_diff = diff
                best = (r, f)

    if best is None or best_diff > 1.0:
        raise RuntimeError(f"Unplausible Summenwerte: ren+fos nicht nahe 100 (diff={best_diff:.2f}).")

    return best

def main():
    # Du hast diese URL angegeben – ohne year Parameter.
    # Wir lassen das so, damit es exakt dem Browser entspricht.
    url = "https://www.energy-charts.info/charts/energy_pie/chart.htm?l=de&c=DE&interval=year&source=total"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(locale="de-DE")
            page.goto(url, wait_until="networkidle", timeout=90000)
            rendered_text = page.inner_text("body")
            browser.close()

        # Falls trotz Playwright nur die JS-Shell kommt (CI-typisch) [1](https://www.energy-charts.info/charts/energy_pie/chart.htm?l=fr&c=DE&source=total&interval=month&legendItems=0wf&month=11)[2](https://energy-charts.info/charts/energy_pie/chart.htm?l=de&c=DE&interval=year)
        if "enable Javascript" in rendered_text or "enable JavaScript" in rendered_text:
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(rendered_text)
            raise RuntimeError("Nur JS-Shell erhalten. debug_rendered_text.txt wurde geschrieben.")

        stand = extract_stand(rendered_text)

        renewable, fossil = extract_summary_percentages(rendered_text)

        data = build_infogram_json(stand, renewable, fossil)

        # Nur bei Erfolg überschreiben -> letzter Stand bleibt bei Fehlern
        safe_write_json(data)

        print("OK: energie.json aktualisiert")
        print("Stand:", stand, "| Erneuerbar:", renewable, "| Fossil:", fossil)

    except Exception as e:
        # Letzten Stand behalten: tmp löschen, nicht crashen
        if os.path.exists(TMP_FILE):
            try:
                os.remove(TMP_FILE)
            except:
                pass
        print("WARNUNG: Update fehlgeschlagen – energie.json bleibt unverändert.")
        print("Fehler:", e)
        return

if __name__ == "__main__":
    main()
