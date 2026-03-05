import re
import json
from datetime import date, datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "energie.json"

def fmt_percent_de(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")

def to_float_percent(s: str) -> float:
    return float(s.replace(",", ".").strip())

def extract_stand(text: str) -> str:
    # bevorzugt: "Stand: 05.03.2026"
    m = re.search(r"Stand:\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text)
    if m:
        return m.group(1)

    # alternativ: "letztes Update: 03/03/2026, ..." oder "last update: 03/03/2026, ..."
    m = re.search(r"(letztes\s+Update|last\s+update)\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
    if m:
        dt = datetime.strptime(m.group(2), "%m/%d/%Y")
        return dt.strftime("%d.%m.%Y")

    # fallback: heutiges Datum
    return datetime.now().strftime("%d.%m.%Y")

def extract_values(text: str):
    # Nach Rendering stehen diese Strings üblicherweise im Text (DE oder EN).
    # Wir suchen bewusst nur die Prozentwerte.
    m_ren = re.search(r"(Erneuerbar|Renewable)\s+([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE)
    m_fos = re.search(r"(Fossil)\s+([0-9]{1,3}[,\.][0-9])\s*%", text, re.IGNORECASE)

    if not m_ren or not m_fos:
        # Debug-Hilfe: kompletten Text sichern
        with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
        raise RuntimeError(
            "Konnte Erneuerbar/Fossil nach Rendering nicht finden. "
            "debug_rendered_text.txt wurde geschrieben."
        )

    ren = to_float_percent(m_ren.group(2))
    fos = to_float_percent(m_fos.group(2))
    return ren, fos

def build_infogram_json(stand_ddmmyyyy: str, ren: float, fos: float):
    return [[
        ["", f"Stand: {stand_ddmmyyyy}"],
        ["Erneuerbar", fmt_percent_de(ren)],
        ["Fossil", fmt_percent_de(fos)]
    ]]

def main():
    year = date.today().year  # AUTO

    url = (
        "https://www.energy-charts.info/charts/energy_pie/chart.htm"
        f"?l=de&c=DE&interval=year&source=total&year={year}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(
            locale="de-DE",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        page.goto(url, wait_until="networkidle", timeout=90000)

        # Sicherstellen, dass überhaupt etwas Inhalt da ist
        body_text = page.inner_text("body")

        # Falls die Seite trotz Browser nur die JS-Info zeigt (selten):
        if "enable Javascript" in body_text or "enable JavaScript" in body_text:
            page.screenshot(path="debug_page.png", full_page=True)
            with open("debug_rendered_text.txt", "w", encoding="utf-8") as f:
                f.write(body_text)
            raise RuntimeError(
                "Trotz Headless-Browser nur JS-Hinweis erhalten. "
                "debug_page.png und debug_rendered_text.txt wurden geschrieben."
            )

        stand = extract_stand(body_text)
        ren, fos = extract_values(body_text)

        browser.close()

    data = build_infogram_json(stand, ren, fos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("OK:", OUTPUT_FILE)
    print("Jahr:", year, "| Stand:", stand, "| Erneuerbar:", ren, "| Fossil:", fos)

if __name__ == "__main__":
    main()
``
