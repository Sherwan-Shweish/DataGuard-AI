"""Readiness-Bericht als PowerPoint und PDF – ein gemeinsames Seitenmodell, nur freigegebene Kommentare.

IBCS-Notation: Ist-Werte (AC) dunkelgrau, günstige Veränderungen grün, ungünstige rot, größter Wert oben, deutsches
Zahlenformat. Alle Zahlen stammen aus dem deterministischen Lauf; KI-Texte erscheinen nur, wenn sie für den aktuellen
Fingerabdruck (Daten + Entscheidungen) namentlich freigegeben sind – die Freigabe wird hier erneut geprüft.
"""

from __future__ import annotations

import io
import textwrap
from collections.abc import Iterable
from pathlib import Path

from src import format as fmt
from src.config import UNTERNEHMEN
from src.regeln import REGEL

FARBEN = {"AC": "#404040", "günstig": "#2E6B30", "ungünstig": "#F06A4F", "leise": "#A6A6A6", "text": "#30353C"}
OBJEKTNAME = {"DEBI": "Debitoren", "KRED": "Kreditoren"}
ARCHIV_SATZ = ("Debitorenquote folgt aus der Suite-Vorgabe: Umsatz nur bei den 12 Kunden aus VarianceAI; die "
               "Kreditorenquote ist der realistischere Wert.")


def _matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    return plt


def _bild(fig) -> bytes:  # noqa: ANN001
    plt = _matplotlib()
    puffer = io.BytesIO()
    fig.savefig(puffer, format="png", dpi=170, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return puffer.getvalue()


def balken(beschriftungen: list[str], werte: list[float], texte: list[str], farben: list[str],
           achse: str) -> bytes:
    """Horizontale Balken, größter Wert oben (Reihenfolge wie übergeben), Werte am Balken."""
    plt = _matplotlib()
    fig, ax = plt.subplots(figsize=(11.5, max(2.2, 0.42 * len(werte) + 0.8)))
    y = list(range(len(werte)))
    ax.barh(y, werte, color=farben, height=0.6)
    ax.set_yticks(y, beschriftungen)
    ax.invert_yaxis()
    spanne = max(max(werte, default=0) - min(0, min(werte, default=0)), 1e-9)
    for i, (w, t) in enumerate(zip(werte, texte, strict=True)):
        ax.text(w + (spanne * 0.012 if w >= 0 else -spanne * 0.012), i, t, va="center",
                ha="left" if w >= 0 else "right", fontsize=10, color=FARBEN["text"])
    ax.set_xlim(min(0, min(werte, default=0)) - spanne * (0.18 if min(werte, default=0) < 0 else 0.02),
                max(0, max(werte, default=0)) + spanne * 0.2)
    ax.axvline(0, color="#AAB0B5", lw=0.7)
    ax.set_xlabel(achse, color="#6C7177")
    ax.set_xticks([])
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    return _bild(fig)


def berichtseiten(lauf, vormonat, verlauf, kommentare: Iterable, fingerabdruck: str,  # noqa: ANN001
                  pseudonyme=None) -> list[dict]:  # noqa: ANN001
    """Seitenmodell für PDF und PowerPoint; Freigabe jedes Kommentars wird gegen ``fingerabdruck`` geprüft."""
    from src.agent import berichtsfaehige

    p, r, k, kv = lauf.pruefung, lauf.readiness, lauf.kennzahlen, vormonat.kennzahlen
    jo = lauf.je_objekt
    stichtag = f"{lauf.stichtag:%d.%m.%Y}"
    kern = [
        f"DAMA-Gesamtscore {fmt.prozent(k['DAMA-Gesamtscore'])} "
        f"({fmt.pp(k['DAMA-Gesamtscore'] - kv['DAMA-Gesamtscore'])} ggü. {vormonat.stichtag:%d.%m.%Y}).",
        f"Migration-Readiness-Quote {fmt.prozent(r.quote)} = bereit {fmt.zahl(r.zaehlung['bereit'])} ÷ zu migrieren "
        f"{fmt.zahl(r.trichter['nicht archivieren'])} "
        f"({fmt.pp(k['Migration-Readiness-Quote'] - kv['Migration-Readiness-Quote'])}).",
    ]
    if len(jo) == 2:
        kern.append("Readiness je Objekt: " + " · ".join(
            f"{OBJEKTNAME[o]} {fmt.prozent(w['readiness_quote'])}" for o, w in jo.items()) + ".")
        kern.append(f"Archivierungsquote {fmt.prozent(lauf.archivquote, 1)}: " + " · ".join(
            f"{OBJEKTNAME[o]} {fmt.prozent(w['archivquote'], 1)} ({fmt.zahl(w['archivieren'])} von "
            f"{fmt.zahl(w['saetze'])})" for o, w in jo.items()) + ". " + ARCHIV_SATZ)
    kern += [f"{fmt.zahl(k['Blocker-Befunde'])} Blocker-Befunde an zu migrierenden Sätzen, "
             f"{fmt.zahl(k['Offene Dublettencluster'])} offene Dublettencluster.",
             "Synthetische Demo-Daten · AC = Ist zum Stichtag · Pp = Prozentpunkte."]
    seiten = [{"titel": "Stammdaten-Readiness-Bericht", "untertitel": f"{UNTERNEHMEN} (fiktiv) · Buchungskreis 1000 · "
                                                                       f"Stichtag {stichtag}", "zeilen": kern}]
    dama = sorted(p.dimension_score.items(), key=lambda x: -x[1])
    vm = vormonat.pruefung.dimension_score
    seiten.append({
        "titel": "DAMA-Score je Dimension",
        "untertitel": "bestandene ÷ anwendbare Prüfungen · AC · % · größter Wert oben",
        "bild": balken([d for d, _ in dama], [w for _, w in dama],
                       [f"{fmt.prozent(w)}  ({fmt.pp(w - vm[d])})" for d, w in dama], [FARBEN["AC"]] * len(dama),
                       "Score in %"),
        "zeilen": [f"Gesamtscore = ungewichteter Mittelwert der fünf Dimensionen = {fmt.prozent(p.gesamtscore)}. "
                   "Aktualität ist am niedrigsten: Altbestand ohne Buchung und ohne Löschvormerkung (A01/A02)."]})
    t = r.trichter
    stufen = [("alle Sätze", t["alle Sätze"]), ("nicht archivieren", t["nicht archivieren"]),
              ("ohne Blocker", t["ohne Blocker"]), ("bereit", t["bereit"])]
    seiten.append({
        "titel": "Migration Readiness (CVI)", "untertitel": "Trichter · Anzahl Sätze · AC",
        "bild": balken([s for s, _ in stufen], [w for _, w in stufen], [fmt.zahl(w) for _, w in stufen],
                       [FARBEN["leise"], FARBEN["AC"], FARBEN["AC"], FARBEN["günstig"]], "Sätze"),
        "zeilen": [f"Readiness-Quote = bereit ÷ (alle − archivieren) = {fmt.zahl(t['bereit'])} ÷ "
                   f"{fmt.zahl(t['nicht archivieren'])} = {fmt.prozent(r.quote)}; inkl. „bereit nach Bereinigung“ "
                   f"{fmt.prozent(r.quote_inkl_bereinigung)}."]
                  + ([" · ".join(f"{OBJEKTNAME[o]}: Readiness {fmt.prozent(w['readiness_quote'])}, Archivierung "
                                 f"{fmt.prozent(w['archivquote'], 1)}" for o, w in jo.items()) + ". " + ARCHIV_SATZ]
                     if len(jo) == 2 else [])})
    bl = r.blocker.regel.value_counts()
    if len(bl):
        oben = list(bl.items())[:10]
        seiten.append({
            "titel": "Blocker nach Regel", "untertitel": "zu migrierende Sätze · Anzahl · größter Wert oben",
            "bild": balken([f"{rid} · {REGEL[rid].beschreibung}" for rid, _ in oben], [int(n) for _, n in oben],
                           [fmt.zahl(int(n)) for _, n in oben], [FARBEN["ungünstig"]] * len(oben), "Blocker"),
            "zeilen": ["Blocker verhindern die Übernahme als Geschäftspartner; Dubletten (E01) werden vor der CVI per "
                       "Golden-Record-Entscheidung zusammengeführt."]})
    z = verlauf.zerlegung
    if len(z):
        summe = z.groupby("ursache").beitrag_pp.sum().sort_values(ascending=False)
        nb = z[z.ursache == "neue Blocker durch Neuanlagen"].groupby("benutzer").beitrag_pp.sum().sort_values()
        vk = verlauf.kennzahlen["Migration-Readiness-Quote"]
        seiten.append({
            "titel": "Readiness-Veränderung über zwölf Monate",
            "untertitel": f"Zerlegung aus dem Änderungsprotokoll · Pp · {fmt.prozent(vk.iloc[0])} → "
                          f"{fmt.prozent(vk.iloc[-1])}",
            "bild": balken(list(summe.index), [float(w) for w in summe], [fmt.pp(w) for w in summe],
                           [FARBEN["günstig"] if w >= 0 else FARBEN["ungünstig"] for w in summe], "Beitrag in Pp"),
            "zeilen": [
                "Data Firewall: Pflichtfeld- und Dublettenprüfung bereits bei der Anlage – dieselbe Regel- und "
                "Dubletten-Engine vor dem Speichern, Bankdaten nur mit Vier-Augen-Prüfung.",
                "Größte Verursacher neuer Blocker (Anlagebenutzer): "
                + ", ".join(f"{b} {fmt.pp(w)}" for b, w in nb.head(3).items()) + "."]})
    frei = berichtsfaehige(list(kommentare), fingerabdruck)
    if not frei:
        seiten.append({"titel": "Freigegebene Kommentare",
                       "untertitel": "namentliche Freigabe zum aktuellen Datenstand",
                       "zeilen": ["Für diesen Daten- und Entscheidungsstand liegen keine freigegebenen Kommentare "
                                  "vor."]})
    for i, kmt in enumerate(frei, start=1):
        text = pseudonyme.aufloesen(kmt.text) if pseudonyme is not None else kmt.text
        seiten.append({"titel": f"{kmt.aufgabe.value} (freigegeben)",
                       "untertitel": f"Freigabe: {kmt.freigegeben_von} · {kmt.freigegeben_am:%d.%m.%Y %H:%M} · "
                                     f"Kommentar {i} von {len(frei)} · Faktenprüfung bestanden",
                       "zeilen": text.splitlines()})
    return seiten


def erstelle_pptx(seiten: list[dict]) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i, s in enumerate(seiten, start=1):
        folie = prs.slides.add_slide(prs.slide_layouts[6])

        def text(x, y, b, h, inhalt, groesse, farbe="30353C", fett=False, folie=folie):  # noqa: ANN001
            tf = folie.shapes.add_textbox(Inches(x), Inches(y), Inches(b), Inches(h)).text_frame
            tf.word_wrap = True
            for n, zeile in enumerate(inhalt.split("\n")):
                absatz = tf.paragraphs[0] if n == 0 else tf.add_paragraph()
                absatz.text = zeile
                absatz.font.name, absatz.font.size, absatz.font.bold = "Arial", Pt(groesse), fett
                absatz.font.color.rgb = RGBColor.from_string(farbe)
                absatz.space_after = Pt(8)

        text(0.55, 0.3, 12.2, 0.6, s["titel"], 26, fett=True)
        text(0.55, 0.95, 12.2, 0.5, s["untertitel"], 13, "6C7177")
        if "bild" in s:
            folie.shapes.add_picture(io.BytesIO(s["bild"]), Inches(0.65), Inches(1.5), width=Inches(12),
                                     height=Inches(4.65))
            text(0.55, 6.2, 12.2, 0.85, "\n".join(s["zeilen"]), 11)
        else:
            text(0.65, 1.65, 12, 5.2, "\n".join(s["zeilen"]), 16)
        text(0.55, 7.1, 12, 0.25, f"DataGuard-AI · synthetische Demo-Daten · {i} / {len(seiten)}", 9, "6C7177")
    puffer = io.BytesIO()
    prs.save(puffer)
    return puffer.getvalue()


def _schrift_pdf() -> tuple[str, str]:
    """DejaVu Sans aus matplotlib (Unicode: →, −, ≥, ÷, •) – auf jedem Rechner vorhanden, der matplotlib hat."""
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    ordner = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, datei in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(ordner / datei)))
    return "DejaVu", "DejaVu-Bold"


def erstelle_pdf(seiten: list[dict]) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    normal, fett = _schrift_pdf()
    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pagesize=(960, 540))
    c.setTitle("DataGuard-AI Stammdaten-Readiness-Bericht")
    c.setAuthor("DataGuard-AI (synthetische Demo-Daten)")
    for i, s in enumerate(seiten, start=1):
        c.setFillColorRGB(0.19, 0.21, 0.24)
        c.setFont(fett, 22)
        c.drawString(40, 498, s["titel"])
        c.setFont(normal, 11)
        c.setFillColorRGB(0.42, 0.44, 0.47)
        c.drawString(40, 474, s["untertitel"])
        c.setFillColorRGB(0.19, 0.21, 0.24)
        if "bild" in s:
            c.drawImage(ImageReader(io.BytesIO(s["bild"])), 45, 95, 865, 360, preserveAspectRatio=True, anchor="c")
            y, groesse, breite = 75, 9, 175
        else:
            y, groesse, breite = 430, 13, 125
        c.setFont(normal, groesse)
        for zeile in s["zeilen"]:
            for stueck in textwrap.wrap(zeile, breite) or [""]:
                c.drawString(45, y, stueck)
                y -= groesse * 1.45
            y -= 6
        c.setFont(normal, 8)
        c.setFillColorRGB(0.42, 0.44, 0.47)
        c.drawString(40, 20, f"DataGuard-AI · synthetische Demo-Daten · {i} / {len(seiten)}")
        c.showPage()
    c.save()
    return puffer.getvalue()
