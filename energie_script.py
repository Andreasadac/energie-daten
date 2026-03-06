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
    # "50,7" oder "50.7" -> 50.7
    return float(s.replace(",", ".").strip())

def extract_stand(text: str) -> str:
    # bevorzugt: "Stand: 06.03.2026"
    m = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
    if m:
        return m.group(1)

    # alternativ: "letztes Update: 02/24/2026, ..." oder "last update: 02/24/2026, ..."
    m = re.search(
        r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
        text,
        re.IGNORECASE
    )
    if m:
        dt = datetime.strptime(m.group(2), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    # fallback
    return datetime.now().strftime("%d.%m.%Y")

def safe_write_json(data: list):
    with open(TMP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(TMP_FILE, OUTPUT_FILE)  # atomar

def build_infogram_json(stand: str, ren: float, fos: float) -> list:
    return [[
        ["", f"Stand: {stand}"],
        ["Erneuerbar", fmt_percent_de(ren)],
        ["Fossil", fmt_percent_de(fos)]
    ]]

def extract_summary_percentages(rendered_text: str) -> tuple[float, float]:
    """
    Extrahiert Summenwerte aus Zeilen wie:
      Erneuerbar 18,286.28 GWh 49.3 %
      Fossil     18,792.16 GWh 50.7 %
    (Ein Beispiel für diese Summenzeilen findet sich in der Energy-Charts-Ausgabe.) [3](https://energy-charts.info/charts/energy_pie/chart.htm)

    Wichtig: Wir suchen NUR die Summary-Zeilen mit GWh/TWh, nicht einzelne Segmente.
    Danach wählen wir die Kombination, deren Summe ~100 ergibt.
    """
    # Zeilen normalisieren
    lines = []
    for line in rendered_text.splitlines():
        line = " ".join(line.strip().split())
        if line:
            lines.append(line)

    # Regex für Summary-Zeile: Label + Menge + Einheit + Prozent
    # DE: Erneuerbar / Fossil
    # EN: Renewable / Fossil
    pattern_ren = re.compile(r"^(Erneuerbar|Renewable)\s+([0-9\.,]+)\s*(GWh|TWh)\s+([0-9]{1,3}[,\.][0-9])\s*%$", re.IGNORECASE)
    pattern_fos = re.compile(r"^(Fossil)\s+([0-9\.,]+)\s*(GWh|TWh)\s+([0-9]{1,3}[,\.][0-9])\s*%$", re.IGNORECASE)

    ren_vals = []
    fos_vals = []

    for line in lines:
        m = pattern_ren.match(line)
        if m:
            ren_vals.append(to_float_percent(m.group(4)))
            continue
        m = pattern_fos.match(line)
        if m:
            fos_vals.append(to_float_percent(m.group(4)))

    if not ren_vals or not fos_vals:
        # Debug, damit wir sehen, wie der Text in Actions aussieht
        with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
            f.write(rendered_text)
        raise RuntimeError(
            "Konnte die Summen-Zeilen (… GWh/TWh … %) nicht finden. "
            "debug_rendered_text.txt wurde geschrieben."
        )

    # Beste Kombination wählen: ren + fos ≈ 100
    best = None
    best_diff = 999.0
    for r in ren_vals:
        for f in fos_vals:
            diff = abs((r + f) - 100.0)
            if diff < best_diff:
                best_diff = diff
                best = (r, f)

    ren, fos = best

    # Sicherheitscheck: wenn nicht plausibel, abbrechen
    if best_diff > 1.0:
        raise RuntimeError(f"Unplausible Summenwerte: ren+fos != 100 (diff={best_diff:.2f}).")

    return ren, fos

def main():
    year = date.today().year  # AUTO
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

            rendered_text = page.inner_text("body")
            browser.close()

        # Wenn die Seite trotzdem nur den Hinweis liefert, hilft Debug
        if "enable Javascript" in rendered_text or "enable JavaScript" in rendered_text:
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(rendered_text)
            raise RuntimeError(
                "Energy-Charts lieferte trotz Playwright nur die JS-Shell. "
                "debug_rendered_text.txt wurde geschrieben."
            )

        stand = extract_stand(rendered_text)

        # ✅ HIER: Summenwerte korrekt extrahieren (nicht „Erneuerbarer Müll … 1,0 %“)
        ren, fos = extract_summary_percentages(rendered_text)

        data = build_infogram_json(stand, ren, fos)

        # ✅ Nur bei Erfolg überschreiben (letzten Stand behalten)
        safe_write_json(data)

        print("OK: energie.json aktualisiert")
        print("Stand:", stand, "| Erneuerbar:", ren, "| Fossil:", fos)

    except Exception as e:
        # ✅ Letzten Stand behalten: keine Überschreibung, Exit 0
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
