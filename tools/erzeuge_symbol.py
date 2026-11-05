"""Erzeugt das App-Symbol von DataGuard-AI im Stil der Suite (Kupferfläche, dunkle Glyphen, ein heller Akzent).

Motiv: Identität „≡“ – drei Stammsätze desselben Partners (umrandet, dunkel, dunkel) werden über das
Identitätszeichen zu einem hellen Golden Record mit Prüfhaken zusammengeführt.
Ausgabe: desktop/ressourcen/icon.png (1024 px), desktop/ressourcen/AppIcon.icns, static/favicon.png (128 px).

Aufruf (einmalig, nicht Teil der App):  uv run --with playwright python tools/erzeuge_symbol.py
"""

from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

PROJEKT = Path(__file__).resolve().parents[1]
D, L = "#1E120C", "#FCF4EC"
X0, X1, H, Y = 168, 452, 128, (262, 438, 614)


def zeile(y: int, art: str) -> str:
    if art == "umriss":
        k = f'<rect x="{X0 + 9}" y="{y + 9}" width="{X1 - X0 - 18}" height="{H - 18}" rx="22" fill="none" ' \
            f'stroke="{D}" stroke-width="18"/>'
        linie = D
    else:
        k = f'<rect x="{X0}" y="{y}" width="{X1 - X0}" height="{H}" rx="26" fill="{D}"/>'
        linie = "#B07658"
    k += f'<line x1="{X0 + 44}" y1="{y + 50}" x2="{X0 + 200}" y2="{y + 50}" stroke="{linie}" stroke-width="16" ' \
         f'stroke-linecap="round"/>'
    k += f'<line x1="{X0 + 44}" y1="{y + 84}" x2="{X0 + 150}" y2="{y + 84}" stroke="{linie}" stroke-width="16" ' \
         f'stroke-linecap="round"/>'
    return k


teile = [zeile(Y[0], "umriss"), zeile(Y[1], "dunkel"), zeile(Y[2], "dunkel")]
# Identitätszeichen ≡ zwischen den Sätzen und dem Golden Record
for dy in (-34, 0, 34):
    teile.append(f'<line x1="490" y1="{502 + dy}" x2="556" y2="{502 + dy}" stroke="{D}" stroke-width="16" '
                 'stroke-linecap="round"/>')
# Golden Record (hell) mit drei Zeilen und Prüfhaken
gx0, gx1, gy0, gy1 = 594, 856, 262, 742
teile.append(f'<rect x="{gx0}" y="{gy0}" width="{gx1 - gx0}" height="{gy1 - gy0}" rx="26" fill="{L}"/>')
for i, breite in enumerate((170, 128, 150)):
    y = gy0 + 70 + i * 46
    teile.append(f'<line x1="{gx0 + 40}" y1="{y}" x2="{gx0 + 40 + breite}" y2="{y}" stroke="#D7B7A3" '
                 'stroke-width="16" stroke-linecap="round"/>')
cx = (gx0 + gx1) / 2
teile.append(f'<path d="M{cx - 62},{606} L{cx - 18},{652} L{cx + 64},{556}" fill="none" stroke="{D}" '
             'stroke-width="30" stroke-linecap="round" stroke-linejoin="round"/>')
teile.append(f'<line x1="176" y1="768" x2="848" y2="768" stroke="{D}" stroke-width="14" stroke-linecap="round"/>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#EEAA82"/><stop offset="1"
stop-color="#C2663E"/></linearGradient>
<filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="16" stdDeviation="20"
flood-color="#000" flood-opacity="0.32"/></filter></defs>
<rect x="100" y="100" width="824" height="824" rx="186" fill="url(#g)" filter="url(#s)"/>
{"".join(teile)}
</svg>'''
ziel = PROJEKT / "desktop" / "ressourcen"
(ziel / "icon.svg").write_text(svg, encoding="utf-8")
with sync_playwright() as p:
    browser = p.chromium.launch()
    seite = browser.new_page(viewport={"width": 1024, "height": 1024})
    seite.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
    seite.screenshot(path=str(ziel / "icon.png"), omit_background=True,
                     clip={"x": 0, "y": 0, "width": 1024, "height": 1024})
    browser.close()
bild = Image.open(ziel / "icon.png").convert("RGBA")
bild.save(ziel / "AppIcon.icns", format="ICNS")
bild.resize((128, 128), Image.LANCZOS).save(PROJEKT / "static" / "favicon.png", optimize=True)
print("Symbol erzeugt:", ziel)
