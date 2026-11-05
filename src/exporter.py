"""Exporte im Stil der Suite: Excel (Bereinigungsliste mit Gegenprüfung, Golden-Record-Entscheidungen),
Power-BI-Paket (Sternschema, DAX) und Übergabe-CSV als Beispiel für das SAP S/4HANA Migration Cockpit.

Grundsätze:
  • IBAN nie unmaskiert – Befundwerte kommen bereits maskiert aus der Engine (``regeln.anzeige_wert``); Kontonummer,
    BLZ und BIC werden nicht exportiert. Tests prüfen jede Datei auf IBAN des Bestands.
  • Stammdatentexte sind unvertrauenswürdig: Werte, die eine Tabellenkalkulation als Formel lesen würde (``=``, ``@``
    bzw. ``+``/``-`` mit Buchstaben), werden mit einem Apostroph entschärft (CSV-/Formel-Injection).
  • Deutsches Format: CSV mit Semikolon, Dezimalkomma, Datum TT.MM.JJJJ, UTF-8 mit BOM.
  • Excel enthält Formeln; ``neu_berechnen`` speichert mit LibreOffice zusätzlich die Ergebniswerte (falls vorhanden),
    ``pruefe_excel`` liest die Gegenprüfung aus.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src import pruefziffern as pz
from src.config import STICHTAG, UNTERNEHMEN
from src.customizing import KONTENGRUPPE
from src.golden_record import zuordnungsliste
from src.regeln import DIMENSIONEN, REGEL
from src.seed_data import QUELLE_LAUFEND
from src.suite import aktive_schluessel

SCHRIFT = "Arial"
PROZENT = '0.00 "%"'
ZAHL = "#,##0"
_KOPF = Font(name=SCHRIFT, size=10, bold=True, color="FFFFFF")
_KOPF_FUELLUNG = PatternFill("solid", fgColor="2F3A45")
_TITEL = Font(name=SCHRIFT, size=14, bold=True)
_LEISE = Font(name=SCHRIFT, size=9, color="595959")
_EINGABE = Font(name=SCHRIFT, size=10, color="0000FF")  # Werte aus Python (blau), Formeln schwarz
_LINIE = Border(bottom=Side(style="thin", color="333333"))
_OK = PatternFill("solid", fgColor="DCEBDD")
_FEHLER = PatternFill("solid", fgColor="F9D3CC")
OBJEKTNAME = {"DEBI": "Debitor", "KRED": "Kreditor"}
KENNZEICHEN_LAUFEND = "aktiv laut Kreditorenbuchung, nicht Teil der FlowAudit-Stichprobe"
_FORMELBEGINN = re.compile(r"^[=@]|^[+\-].*[A-Za-z(]")


def entschaerfen(wert: Any) -> Any:
    """Text, den Excel/LibreOffice als Formel deuten würde, mit Apostroph versehen (OWASP CSV Injection)."""
    if isinstance(wert, str) and _FORMELBEGINN.search(wert.lstrip("\t\r")):
        return "'" + wert
    return wert


def kennzeichen(schluessel: str, quelle: str | None) -> str:
    if schluessel in aktive_schluessel():
        return "aktiver Partner der Suite"
    return KENNZEICHEN_LAUFEND if quelle == QUELLE_LAUFEND else ""


# =============================================================================
# Excel – Hilfen
# =============================================================================


def _kopfzeile(ws: Worksheet, zeile: int, titel: Sequence[str], breiten: Sequence[int]) -> None:
    for i, (t, b) in enumerate(zip(titel, breiten, strict=True), start=1):
        c = ws.cell(zeile, i, t)
        c.font, c.fill, c.border = _KOPF, _KOPF_FUELLUNG, _LINIE
        ws.column_dimensions[get_column_letter(i)].width = b
    ws.freeze_panes = ws.cell(zeile + 1, 1)


def _titel(ws: Worksheet, titel: str, unter: str) -> None:
    ws["A1"], ws["A1"].font = titel, _TITEL
    ws["A2"], ws["A2"].font = unter, _LEISE


def _setze(ws: Worksheet, zeile: int, spalte: int, wert: Any, format_: str | None = None,
           eingabe: bool = False) -> None:
    c = ws.cell(zeile, spalte, entschaerfen(wert))
    if format_:
        c.number_format = format_
    if eingabe:
        c.font = _EINGABE


def _formel(ws: Worksheet, zeile: int, spalte: int, formel: str, format_: str | None = None) -> None:
    c = ws.cell(zeile, spalte, formel)
    if format_:
        c.number_format = format_


def _status_formatierung(ws: Worksheet, bereich: str) -> None:
    ws.conditional_formatting.add(bereich, CellIsRule(operator="equal", formula=['"OK"'], fill=_OK))
    ws.conditional_formatting.add(bereich, CellIsRule(operator="equal", formula=['"FEHLER"'], fill=_FEHLER))


def _tabelle(ws: Worksheet, start: int, df: pd.DataFrame, breiten: Sequence[int],
             formate: dict[str, str] | None = None) -> int:
    """DataFrame ab Zeile ``start`` (Kopf) schreiben; Texte entschärft. Gibt die letzte Datenzeile zurück."""
    _kopfzeile(ws, start, list(df.columns), breiten)
    formate = formate or {}
    for r, zeile in enumerate(df.itertuples(index=False), start=start + 1):
        for c, (spalte, wert) in enumerate(zip(df.columns, zeile, strict=True), start=1):
            if isinstance(wert, float) and pd.isna(wert):
                wert = None
            ws.cell(r, c, entschaerfen(wert)).number_format = formate.get(spalte, "General")
    ws.auto_filter.ref = f"A{start}:{get_column_letter(len(df.columns))}{start + max(len(df), 1)}"
    return start + len(df)


def _neue_mappe() -> Workbook:
    """Mappe mit Arial als Standardschrift (Formatvorlage „Normal“) – keine Schrift je Zelle nötig."""
    from openpyxl.utils.indexed_list import IndexedList

    wb = Workbook()
    wb._fonts = IndexedList([Font(name=SCHRIFT, size=10), *list(wb._fonts)[1:]])  # Standardschrift (Index 0)
    next(st for st in wb._named_styles if st.name == "Normal").font = Font(name=SCHRIFT, size=10)
    return wb


def _hinweise(wb: Workbook, titel: str, zeilen: Iterable[str]) -> None:
    ws = wb.active
    ws.title = "Hinweise"
    _titel(ws, titel, f"{UNTERNEHMEN} (fiktiv) · Buchungskreis 1000 · Stichtag {STICHTAG:%d.%m.%Y} · "
                      "synthetische Daten")
    for i, t in enumerate(zeilen, start=4):
        ws.cell(i, 1, t)
    ws.column_dimensions["A"].width = 120


def _speichern(wb: Workbook) -> bytes:
    wb.calculation.fullCalcOnLoad = True  # Excel berechnet beim Öffnen; LibreOffice-Lauf cacht zusätzlich Werte
    puffer = io.BytesIO()
    wb.save(puffer)
    return puffer.getvalue()


# =============================================================================
# Excel – Bereinigungsliste mit Gegenprüfung
# =============================================================================


def bereinigungsliste_tabelle(lauf) -> pd.DataFrame:  # noqa: ANN001
    """Je Befund: Satz, Objekt, SAP-Feld, Regel, Schweregrad, Vorschlag, Status (IBAN maskiert)."""
    b = lauf.pruefung.befunde
    status = dict(zip(lauf.readiness.status.schluessel, lauf.readiness.status.status, strict=True))
    quelle = dict(zip(lauf.saetze.schluessel, lauf.saetze.quelle, strict=True))
    return pd.DataFrame({
        "Satz": b.nr, "Objekt": b.objekt.map(OBJEKTNAME), "Name": b.name, "SAP-Feld": b.sap_feld, "Regel": b.regel,
        "Beschreibung": b.regel.map(lambda r: REGEL[r].beschreibung), "Dimension": b.dimension,
        "Schweregrad": b.schweregrad, "CVI-Blocker": b.regel.map(lambda r: "ja" if REGEL[r].cvi_blocker else ""),
        "Wert (maskiert)": b.wert, "Partner": b.partner.map(lambda p: ", ".join(p)), "Vorschlag": b.korrektur,
        "Status": b.schluessel.map(status), "Kennzeichen": b.schluessel.map(lambda s: kennzeichen(s, quelle.get(s))),
    })


def bereinigungsliste_excel(lauf) -> bytes:  # noqa: ANN001
    """Excel „Bereinigungsliste“ mit Blättern Gegenprüfung, Bereinigungsliste, Regeln, Status."""
    p, r = lauf.pruefung, lauf.readiness
    wb = _neue_mappe()
    _hinweise(wb, "DataGuard-AI · Bereinigungsliste", [
        "Blatt „Bereinigungsliste“: je Befund Satz, Objekt, SAP-Feld, Regel, Schweregrad, Vorschlag und "
        "Readiness-Status.",
        "Blatt „Regeln“: je Regel anwendbare und verletzte Prüfungen aus Python (blau) und Excel-Formeln (schwarz).",
        "Blatt „Status“: Readiness-Status je Satz (bereit / bereit nach Bereinigung / blockiert / archivieren).",
        "Blatt „Gegenprüfung“: DAMA-Scores, Readiness- und Archivierungsquoten mit Excel-Formeln nachgerechnet; "
        "Status grün = Python und Excel stimmen überein.",
        "IBAN nur maskiert (z. B. „DE59 •••• 3344“); Kontonummer, BLZ und BIC werden nicht exportiert.",
        "Keine Änderung der Quelldaten: Die Liste ist ein Vorschlag; Korrekturen erfolgen im Quellsystem durch das "
        "Stammdatenteam.",
        "Archivierungsquote Debitoren folgt aus der Suite-Vorgabe (Umsatz nur bei den 12 Kunden aus VarianceAI); die "
        "Kreditorenquote ist der realistischere Wert.",
    ])
    # Bereinigungsliste
    ws_b = wb.create_sheet("Bereinigungsliste")
    _titel(ws_b, "Bereinigungsliste", f"{len(p.befunde)} Befunde · Objekt {lauf.objekt} · sortiert nach Satz und Regel")
    liste = bereinigungsliste_tabelle(lauf)
    letzte_b = _tabelle(ws_b, 3, liste, [10, 10, 34, 22, 7, 40, 14, 11, 10, 22, 22, 50, 22, 30])
    # Regeln
    ws_r = wb.create_sheet("Regeln")
    _titel(ws_r, "Regeln: anwendbare und verletzte Prüfungen", "blau = Wert aus Python · schwarz = Excel-Formel")
    kopf = ["Regel", "Beschreibung", "Dimension", "Schweregrad", "SAP-Feld", "CVI-Blocker", "anwendbar", "verletzt",
            "bestanden", "Quote bestanden", "verletzt laut Liste", "Status"]
    _kopfzeile(ws_r, 3, kopf, [8, 44, 14, 12, 22, 11, 11, 10, 11, 15, 17, 10])
    z = p.zaehler.reset_index(drop=True)
    for i, x in enumerate(z.itertuples(index=False), start=4):
        for c, wert in enumerate([x.regel, x.beschreibung, x.dimension, x.schweregrad, REGEL[x.regel].sap_feld,
                                  "ja" if REGEL[x.regel].cvi_blocker else ""], start=1):
            ws_r.cell(i, c, wert)
        _setze(ws_r, i, 7, int(x.anwendbar), ZAHL, eingabe=True)
        _setze(ws_r, i, 8, int(x.verletzt), ZAHL, eingabe=True)
        _formel(ws_r, i, 9, f"=G{i}-H{i}", ZAHL)
        _formel(ws_r, i, 10, f'=IF(G{i}>0,I{i}/G{i}*100,"")', PROZENT)
        _formel(ws_r, i, 11, f"=COUNTIF(Bereinigungsliste!$E$4:$E${max(letzte_b, 4)},A{i})", ZAHL)
        _formel(ws_r, i, 12, f'=IF(K{i}=H{i},"OK","FEHLER")')
    letzte_r = 3 + len(z)
    _status_formatierung(ws_r, f"L4:L{letzte_r}")
    # Status je Satz
    ws_s = wb.create_sheet("Status")
    _titel(ws_s, "Readiness-Status je Satz", "Quote = bereit ÷ (alle − archivieren)")
    st = r.status
    quelle = dict(zip(lauf.saetze.schluessel, lauf.saetze.quelle, strict=True))
    status_df = pd.DataFrame({"Objekt": st.objekt, "Nummer": st.nr, "Name": st.name, "Status": st.status,
                              "Blocker": st.blocker, "Fehler": st.fehler, "BP-Gruppierung": st.bp_gruppierung,
                              "Archivgrund": st.gruende_archiv,
                              "Kennzeichen": st.schluessel.map(lambda s: kennzeichen(s, quelle.get(s)))})
    letzte_s = _tabelle(ws_s, 3, status_df, [8, 10, 34, 22, 18, 14, 14, 40, 30])
    # Gegenprüfung
    ws = wb.create_sheet("Gegenprüfung", 1)
    _titel(ws, "Formel-Gegenprüfung: Python-Ergebnis vs. Excel-Formel",
           "Status grün = Abweichung innerhalb der Rundung (Python rundet Quoten auf 2 Nachkommastellen)")
    _kopfzeile(ws, 3, ["Prüfung", "Python", "Excel", "Differenz", "Status"], [70, 14, 14, 12, 10])
    rg, sb, sd = f"Regeln!$C$4:$C${letzte_r}", f"Status!$A$4:$A${letzte_s}", f"Status!$D$4:$D${letzte_s}"
    zeilen: list[tuple[str, float, str, float]] = []
    for d in DIMENSIONEN:
        zeilen.append((f"DAMA-Score {d} = bestanden ÷ anwendbar × 100", p.dimension_score[d],
                       f'=SUMIFS(Regeln!$I$4:$I${letzte_r},{rg},"{d}")/SUMIFS(Regeln!$G$4:$G${letzte_r},{rg},"{d}")*100',
                       0.006))
    zeilen.append(("DAMA-Gesamtscore = Mittelwert der fünf Dimensionen", p.gesamtscore, "=AVERAGE(C4:C8)", 0.011))
    basis = f'(COUNTA({sd})-COUNTIF({sd},"archivieren"))'
    zeilen.append(("Readiness-Quote = bereit ÷ (alle − archivieren) × 100", r.quote,
                   f'=COUNTIF({sd},"bereit")/{basis}*100', 0.006))
    zeilen.append(("Archivierungsquote = archivieren ÷ alle Sätze × 100", lauf.archivquote,
                   f'=COUNTIF({sd},"archivieren")/COUNTA({sd})*100', 0.051))
    for o, w in lauf.je_objekt.items():
        n = OBJEKTNAME[o]
        b_o = f'(COUNTIF({sb},"{o}")-COUNTIFS({sb},"{o}",{sd},"archivieren"))'
        zeilen.append((f"Readiness-Quote {n}en", w["readiness_quote"], f'=COUNTIFS({sb},"{o}",{sd},"bereit")/{b_o}*100',
                       0.006))
        zeilen.append((f"Archivierungsquote {n}en", w["archivquote"],
                       f'=COUNTIFS({sb},"{o}",{sd},"archivieren")/COUNTIF({sb},"{o}")*100', 0.051))
    zeilen.append(("Befunde je Regel: Liste = Zähler (Anzahl Regeln mit Abweichung)", 0,
                   f'=COUNTIF(Regeln!$L$4:$L${letzte_r},"FEHLER")', 0.0))
    zeilen.append(("Summe verletzter Prüfungen = Zeilen der Bereinigungsliste", int(p.zaehler.verletzt.sum()),
                   f"=COUNTA(Bereinigungsliste!$A$4:$A${max(letzte_b, 4)})", 0.0))
    for i, (text, py, formel, tol) in enumerate(zeilen, start=4):
        ws.cell(i, 1, text)
        _setze(ws, i, 2, float(py), "0.00", eingabe=True)
        _formel(ws, i, 3, formel, "0.00")
        _formel(ws, i, 4, f"=C{i}-B{i}", "0.000")
        _formel(ws, i, 5, f'=IF(ABS(D{i})<={tol},"OK","FEHLER")')
    letzte = 3 + len(zeilen)
    ws.cell(letzte + 2, 1, "Gesamtstatus").font = Font(name=SCHRIFT, bold=True)
    _formel(ws, letzte + 2, 5, f'=IF(COUNTIF(E4:E{letzte},"FEHLER")=0,"OK","FEHLER")')
    ws.cell(letzte + 2, 5).font = Font(name=SCHRIFT, bold=True)
    _status_formatierung(ws, f"E4:E{letzte + 2}")
    return _speichern(wb)


# =============================================================================
# Excel – Golden-Record-Entscheidungen
# =============================================================================


def golden_record_excel(lauf, entscheidungen: Sequence) -> bytes:  # noqa: ANN001
    """Entscheidungen (Entscheider, Zeitpunkt, Begründung), Zuordnung alt → neu und alle Vorschläge je Feld."""
    wb = _neue_mappe()
    _hinweise(wb, "DataGuard-AI · Golden-Record-Entscheidungen", [
        "Blatt „Zuordnung alt → neu“: Ergebnis für das Migrationsprojekt – nur übernommene Cluster, jüngste "
        "Entscheidung je Cluster.",
        "Blatt „Entscheidungen“: jede namentliche Entscheidung (übernehmen / ablehnen / zurückstellen), append-only.",
        "Blatt „Vorschläge“: Golden-Record-Vorschlag je Cluster und Feld mit Überlebensregel und Alternativen.",
        "Keine automatische Zusammenführung: Quelldaten bleiben unverändert. IBAN nur maskiert.",
        f"Stand: {len(entscheidungen)} Entscheidungen zu {len(lauf.vorschlaege)} Vorschlägen.",
    ])
    zl = zuordnungsliste(list(entscheidungen))
    ws = wb.create_sheet("Zuordnung alt → neu")
    _titel(ws, "Zuordnung alt → neu", "Übergabe an das Migrationsprojekt (Nummern im Quellsystem)")
    _tabelle(ws, 3, zl.rename(columns={"cluster": "Cluster", "alt": "alt", "neu": "neu", "entscheider": "Entscheider",
                                       "zeitpunkt": "Zeitpunkt", "begruendung": "Begründung"}),
             [26, 10, 10, 24, 20, 50])
    ws = wb.create_sheet("Entscheidungen")
    _titel(ws, "Entscheidungen (append-only)", "jede Entscheidung mit Namen und Zeitpunkt")
    ent = pd.DataFrame([{"Cluster": e.cluster_id, "Entscheidung": e.entscheidung, "Ziel": e.ziel,
                         "Entscheider": e.entscheider, "Zeitpunkt": e.zeitpunkt, "Begründung": e.begruendung,
                         "Zuordnungen": len(e.zuordnung)} for e in entscheidungen],
                       columns=["Cluster", "Entscheidung", "Ziel", "Entscheider", "Zeitpunkt", "Begründung",
                                "Zuordnungen"])
    _tabelle(ws, 3, ent, [26, 14, 10, 24, 20, 50, 12])
    ws = wb.create_sheet("Vorschläge")
    _titel(ws, "Golden-Record-Vorschläge je Feld", "Überlebensregeln: gültig vor ungültig · vollständig vor leer · "
                                                    "Quelle mit Buchungen · jüngste Änderung · kleinste Nummer")
    vz = pd.DataFrame([{"Cluster": f"C-{i:02d}", "Cluster-ID": v.cluster_id, "Objekt": OBJEKTNAME[v.objekt],
                        "Sätze": ", ".join(v.nummern), "Score": v.max_score, "Ziel": v.ziel, "Feld": f.bezeichnung,
                        "Vorschlag": f.wert, "aus Satz": f.quelle,  # IBAN bereits maskiert (golden_record._anzeige)
                        "Regel": f.regel, "Alternativen": " | ".join(f.alternativen)}
                       for i, v in enumerate(lauf.vorschlaege, start=1) for f in v.felder])
    _tabelle(ws, 3, vz, [8, 26, 10, 26, 8, 10, 16, 32, 10, 30, 40], {"Score": "0.0"})
    return _speichern(wb)


# =============================================================================
# LibreOffice: Formeln berechnen und Gegenprüfung auslesen
# =============================================================================


def neu_berechnen(daten: bytes, timeout: int = 120) -> bytes | None:
    """Formeln mit LibreOffice berechnen und mit Ergebniswerten speichern (None ohne LibreOffice)."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        return None
    with tempfile.TemporaryDirectory(prefix="dataguard_calc_") as tmp, \
            tempfile.TemporaryDirectory(prefix="lo_profil_") as profil:
        quelle = Path(tmp) / "eingabe.xlsx"
        quelle.write_bytes(daten)
        ziel = Path(tmp) / "aus"
        subprocess.run([soffice, f"-env:UserInstallation={Path(profil).as_uri()}", "--headless", "--calc",
                        "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(ziel), str(quelle)],
                       env={**os.environ, "SAL_USE_VCLPLUGIN": "svp"}, capture_output=True, timeout=timeout,
                       check=False)
        ergebnis = ziel / "eingabe.xlsx"
        return ergebnis.read_bytes() if ergebnis.exists() else None


def pruefe_excel(daten: bytes) -> dict[str, Any]:
    """Berechnet die Mappe und liest Gesamtstatus, Einzelprüfungen und Formelfehler aus."""
    berechnet = neu_berechnen(daten)
    if berechnet is None:
        return {"berechnet": False}
    wb = load_workbook(io.BytesIO(berechnet), data_only=True)
    fehlerwerte = ("#VALUE!", "#REF!", "#NAME?", "#DIV/0!", "#N/A", "#NUM!", "Err:")
    formelfehler = [f"{ws.title}!{c.coordinate}" for ws in wb.worksheets for z in ws.iter_rows() for c in z
                    if isinstance(c.value, str) and c.value.startswith(fehlerwerte)]
    ergebnis: dict[str, Any] = {"berechnet": True, "formelfehler": formelfehler, "daten": berechnet}
    if "Gegenprüfung" in wb.sheetnames:
        ws = wb["Gegenprüfung"]
        pruefungen = {ws.cell(i, 1).value: ws.cell(i, 5).value for i in range(4, ws.max_row + 1)
                      if ws.cell(i, 1).value and ws.cell(i, 5).value in ("OK", "FEHLER")}
        ergebnis["gesamtstatus"] = pruefungen.pop("Gesamtstatus", None)
        ergebnis["pruefungen"] = pruefungen
    return ergebnis


# =============================================================================
# CSV im deutschen Format
# =============================================================================


def csv_bytes(df: pd.DataFrame) -> bytes:
    """Semikolon, Dezimalkomma, Datum TT.MM.JJJJ, UTF-8 mit BOM; Texte entschärft."""
    aus = df.copy()
    for spalte in aus.columns:
        if not pd.api.types.is_numeric_dtype(aus[spalte]) or pd.api.types.is_bool_dtype(aus[spalte]):
            aus[spalte] = aus[spalte].map(
                lambda v: v.strftime("%d.%m.%Y") if isinstance(v, (date, datetime)) else entschaerfen(v))
    return aus.to_csv(sep=";", decimal=",", index=False, date_format="%d.%m.%Y").encode("utf-8-sig")


def _zip(dateien: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in dateien.items():
            z.writestr(name, inhalt)
    return puffer.getvalue()


# =============================================================================
# Power BI
# =============================================================================

DAX_MEASURES = """// ---------------------------------------------------------------------------
// DataGuard-AI – DAX-Measures (Tabelle „Measures“ anlegen und Ausdrücke einfügen)
// Score je DAMA-Dimension = bestandene ÷ anwendbare Prüfungen; Gesamtscore = ungewichteter Mittelwert.
// Readiness-Quote = bereit ÷ (alle − archivieren). Gleiche Definition wie in Python (docs/methodik.md).
// ---------------------------------------------------------------------------

Anwendbar = SUM ( fakt_pruefung[Anwendbar] )
Verletzt = SUM ( fakt_pruefung[Verletzt] )
Bestanden = [Anwendbar] - [Verletzt]
DAMA Score = DIVIDE ( [Bestanden], [Anwendbar] ) * 100
DAMA Gesamtscore =
    AVERAGEX (
        VALUES ( dim_dimension[Dimension] ),
        CALCULATE ( DIVIDE ( SUM ( fakt_pruefung[Anwendbar] ) - SUM ( fakt_pruefung[Verletzt] ),
                             SUM ( fakt_pruefung[Anwendbar] ) ) * 100 )
    )

Sätze = COUNTROWS ( fakt_status )
Bereit = CALCULATE ( COUNTROWS ( fakt_status ), fakt_status[Status] = "bereit" )
Archivieren = CALCULATE ( COUNTROWS ( fakt_status ), fakt_status[Status] = "archivieren" )
Blockiert = CALCULATE ( COUNTROWS ( fakt_status ), fakt_status[Status] = "blockiert" )
Readiness-Quote = DIVIDE ( [Bereit], [Sätze] - [Archivieren] ) * 100
Archivierungsquote = DIVIDE ( [Archivieren], [Sätze] ) * 100

Befunde = COUNTROWS ( fakt_befund )
Blocker-Befunde = CALCULATE ( COUNTROWS ( fakt_befund ), dim_regel[Schweregrad] = "Blocker" )

// Verlauf (12 Monatsstände) und Zerlegung der Readiness-Veränderung in Pp
Readiness-Quote Verlauf = AVERAGE ( fakt_verlauf[Readiness_Quote] )
DAMA Gesamtscore Verlauf = AVERAGE ( fakt_verlauf[DAMA_Gesamtscore] )
Beitrag Readiness Pp = SUM ( fakt_zerlegung[Beitrag_Pp] )

// IBCS-Farblogik für bedingte Formatierung (günstig / ungünstig)
Farbe Beitrag = IF ( [Beitrag Readiness Pp] >= 0, "#2E6B30", "#F06A4F" )
"""

POWER_QUERY = """// Power Query (M) – Import einer DataGuard-CSV im deutschen Format.
// Für jede Datei eine Abfrage anlegen und den Dateinamen anpassen.
let
    Ordner = "C:\\\\DataGuard\\\\powerbi\\\\",
    Datei = "fakt_status.csv",
    Quelle = Csv.Document(File.Contents(Ordner & Datei),
        [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Kopf = Table.PromoteHeaders(Quelle, [PromoteAllScalars = true]),
    // Typen mit deutscher Kultur (Dezimalkomma, Datum TT.MM.JJJJ)
    Typen = Table.TransformColumnTypes(Kopf, {{"Stichtag", type date}}, "de-DE")
in
    Typen
"""

MODELL_MD = """# Power-BI-Paket DataGuard-AI

Sternschema der Stammdatenprüfung der fiktiven {firma} (synthetische Daten), Stichtag {stichtag}.
Keine Bankdaten im Paket: IBAN, Kontonummer, BLZ und BIC werden nicht exportiert.

## Dateien

| Datei | Typ | Inhalt |
|---|---|---|
| `fakt_befund.csv` | Fakt | je Befund: Satz, Regel, Wert (maskiert), Stichtag |
| `fakt_pruefung.csv` | Fakt | je Regel und Objekt: anwendbare und verletzte Prüfungen (Grundlage DAMA-Score) |
| `fakt_status.csv` | Fakt | Readiness-Status je Satz |
| `fakt_verlauf.csv` | Fakt | 12 Monatsstände: Kennzahlen und Score je Dimension |
| `fakt_zerlegung.csv` | Fakt | Zerlegung der Readiness-Veränderung je Monat, Ursache und Benutzer (Pp) |
| `dim_satz.csv` | Dimension | Sätze (Objekt, Nummer, Name, Kontengruppe, Land, Region, Kennzeichen, letzte Buchung) |
| `dim_regel.csv` | Dimension | Regelkatalog (Dimension, Schweregrad, SAP-Feld, CVI-Blocker) |
| `dim_dimension.csv` | Dimension | DAMA-Dimensionen |
| `dim_objekt.csv` | Dimension | Debitor / Kreditor |
| `dim_monat.csv` | Dimension | Monatsenden {von}–{bis} |
| `measures.dax` | DAX | DAMA-Score, DAMA-Gesamtscore, Readiness-Quote, Archivierungsquote, Verlauf, Zerlegung |
| `power_query.m` | M | Import im deutschen Format (Semikolon, Dezimalkomma, UTF-8) |

## Beziehungen (alle 1:n, einfache Filterrichtung)

```mermaid
erDiagram
    dim_satz ||--o{{ fakt_befund : Satz_ID
    dim_satz ||--o{{ fakt_status : Satz_ID
    dim_regel ||--o{{ fakt_befund : Regel_ID
    dim_regel ||--o{{ fakt_pruefung : Regel_ID
    dim_dimension ||--o{{ dim_regel : Dimension
    dim_objekt ||--o{{ dim_satz : Objekt
    dim_objekt ||--o{{ fakt_pruefung : Objekt
    dim_monat ||--o{{ fakt_verlauf : Monatsende
    dim_monat ||--o{{ fakt_zerlegung : Monatsende
```

## Kontrollwerte (Python, Stichtag {stichtag})

| Measure | Wert |
|---|---:|
{kontrolle}

## Format

Semikolon als Trennzeichen, Dezimalkomma, Datum `TT.MM.JJJJ`, UTF-8 mit BOM.
Beim Import Gebietsschema **Deutsch (Deutschland)** verwenden.
"""


def powerbi_tabellen(lauf, verlauf) -> dict[str, pd.DataFrame]:  # noqa: ANN001
    p, r, s = lauf.pruefung, lauf.readiness, lauf.saetze
    sid = lambda schluessel: schluessel.str.replace(":", "-", regex=False)  # noqa: E731
    stichtag = lauf.stichtag
    befund = pd.DataFrame({"Satz_ID": sid(p.befunde.schluessel), "Regel_ID": p.befunde.regel,
                           "Wert_maskiert": p.befunde.wert, "Stichtag": stichtag})
    zo = p.zaehler_objekt
    pruefung = pd.DataFrame({"Regel_ID": zo.regel, "Objekt": zo.satzobjekt, "Anwendbar": zo.anwendbar.astype(int),
                             "Verletzt": zo.verletzt.astype(int), "Stichtag": stichtag})
    status = pd.DataFrame({"Satz_ID": sid(r.status.schluessel), "Status": r.status.status,
                           "Blocker": r.status.blocker, "Fehler": r.status.fehler,
                           "BP_Gruppierung": r.status.bp_gruppierung, "Stichtag": stichtag})
    satz = pd.DataFrame({
        "Satz_ID": sid(s.schluessel), "Objekt": s.objekt, "Nummer": s.nr, "Name": s.name1, "Kontengruppe": s.ktogr,
        "Land": s.land, "PLZ": s.plz, "Ort": s.ort, "Region": s.bzirk, "Anlagedatum": s.erdat,
        "Letzte_Buchung": s.letzte_buchung, "Anzahl_Belege_2024_2026": s.anz_belege,
        "Kennzeichen": [kennzeichen(k, q) for k, q in zip(s.schluessel, s.quelle, strict=True)]})
    regel = pd.DataFrame([{"Regel_ID": x.id, "Beschreibung": x.beschreibung, "Dimension": x.dimension,
                           "Schweregrad": x.schweregrad, "SAP_Feld": x.sap_feld, "Objekt": x.objekt,
                           "CVI_Blocker": x.cvi_blocker} for x in REGEL.values()])
    vk = verlauf.kennzahlen
    fv = pd.DataFrame({"Monatsende": vk.monatsende, "DAMA_Gesamtscore": vk["DAMA-Gesamtscore"],
                       "Readiness_Quote": vk["Migration-Readiness-Quote"],
                       "Offene_Dublettencluster": vk["Offene Dublettencluster"],
                       "Blocker_Befunde": vk["Blocker-Befunde"],
                       "Archivierungskandidaten": vk["Archivierungskandidaten"],
                       **{f"Score_{d}": vk[f"Score {d}"] for d in DIMENSIONEN}, "Saetze": vk["Sätze"]})
    z = verlauf.zerlegung
    zerlegung = pd.DataFrame({"Monatsende": z.monatsende, "Ursache": z.ursache, "Benutzer": z.benutzer,
                              "Beitrag_Pp": z.beitrag_pp.round(4)})
    return {
        "fakt_befund.csv": befund, "fakt_pruefung.csv": pruefung, "fakt_status.csv": status,
        "fakt_verlauf.csv": fv, "fakt_zerlegung.csv": zerlegung, "dim_satz.csv": satz, "dim_regel.csv": regel,
        "dim_dimension.csv": pd.DataFrame({"Dimension": list(DIMENSIONEN)}),
        "dim_objekt.csv": pd.DataFrame({"Objekt": ["DEBI", "KRED"], "Bezeichnung": ["Debitor", "Kreditor"]}),
        "dim_monat.csv": pd.DataFrame({"Monatsende": vk.monatsende,
                                       "Monat": [f"{m:%m}.{m:%Y}" for m in vk.monatsende]}),
    }


def powerbi_paket(lauf, verlauf) -> bytes:  # noqa: ANN001
    """Power-BI-Paket als ZIP (CSV, DAX, Power Query, Modellbeschreibung)."""
    from src import format as fmt

    tabellen = powerbi_tabellen(lauf, verlauf)
    dateien = {f"dataguard_powerbi/{n}": csv_bytes(df) for n, df in tabellen.items()}
    kontrolle = [("DAMA Gesamtscore", fmt.prozent(lauf.pruefung.gesamtscore)),
                 *((f"DAMA Score {d}", fmt.prozent(w)) for d, w in lauf.pruefung.dimension_score.items()),
                 ("Readiness-Quote", fmt.prozent(lauf.readiness.quote)),
                 ("Archivierungsquote", fmt.prozent(lauf.archivquote, 1)),
                 ("Befunde", fmt.zahl(len(lauf.pruefung.befunde)))]
    vk = verlauf.kennzahlen
    dateien["dataguard_powerbi/measures.dax"] = DAX_MEASURES.encode("utf-8")
    dateien["dataguard_powerbi/power_query.m"] = POWER_QUERY.encode("utf-8")
    dateien["dataguard_powerbi/README.md"] = MODELL_MD.format(
        firma=UNTERNEHMEN, stichtag=f"{lauf.stichtag:%d.%m.%Y}", von=f"{vk.monatsende.iloc[0]:%d.%m.%Y}",
        bis=f"{vk.monatsende.iloc[-1]:%d.%m.%Y}",
        kontrolle="\n".join(f"| {n} | {w} |" for n, w in kontrolle)).encode("utf-8")
    return _zip(dateien)


def dax_spaltenreferenzen(dax: str) -> set[tuple[str, str]]:
    """Alle ``tabelle[spalte]``-Referenzen in einem DAX-Text (für die Modellprüfung)."""
    return set(re.findall(r"\b(fakt_\w+|dim_\w+)\[([^\]]+)\]", dax))


# =============================================================================
# Übergabe-CSV für das SAP S/4HANA Migration Cockpit (Beispiel)
# =============================================================================

#: Beispielhafte Feldnamen (angelehnt an BP-Strukturen BUT000/ADRC/BUT0BK/DFKKBPTAXNUM) – im System prüfen.
MIGRATION_SPALTEN = {
    "QUELLE_NR": "Quellnummer (KUNNR/LIFNR)", "BU_GROUP": "BP-Gruppierung", "BU_TYPE": "Partnertyp (2 = Organisation)",
    "NAME_ORG1": "Name 1", "STREET": "Straße", "HOUSE_NUM1": "Hausnummer", "POST_CODE1": "PLZ", "CITY1": "Ort",
    "COUNTRY": "Land", "LANGU": "Sprache", "TELNR_LONG": "Telefon", "SMTP_ADDR": "E-Mail",
    "TAXTYPE": "Steuernummernkat.",
    "TAXNUM": "USt-IdNr.", "KTOGR_QUELLE": "Kontengruppe (Quelle)", "AKONT": "Abstimmkonto", "ZTERM": "Zahlungsbed.",
    "ROLLE": "BP-Rolle", "BANKS": "Bankland", "IBAN_MASKIERT": "IBAN (nur Kontrolle, maskiert)",
}

LIESMICH = """BEISPIEL – Übergabe-CSV für das SAP S/4HANA Migration Cockpit (Geschäftspartner)
=====================================================================================

Diese Dateien sind eine VORLAGE zur Veranschaulichung, keine geprüfte Migrationsdatei.
• Feldnamen und Strukturen sind Beispiele (angelehnt an BUT000, ADRC, DFKKBPTAXNUM, BUT0BK) – im System prüfen.
  Das Migration Cockpit liefert je Release eigene Vorlagen (Migrationsobjekt „Kunde“ bzw. „Lieferant“).
• Enthalten sind nur Sätze mit Readiness-Status „bereit“ ({bereit} Sätze). Sätze, die laut Golden-Record-
  Entscheidung in einen Zielsatz übergehen, sind ausgeschlossen ({ausgeschlossen} Sätze); die Zuordnung alt → neu
  steht in der Excel-Datei „Golden-Record-Entscheidungen“.
• Bankverbindungen werden NICHT exportiert: Die IBAN steht nur maskiert zur Kontrolle in der Datei; die
  Bankdaten übernimmt das Migrationsprojekt direkt aus dem Quellsystem (KNBK/LFBK).
• Steuernummernkategorie DE0 / EU-Kategorien sind Beispiele – im Customizing prüfen.
• Stand: Stichtag {stichtag} · {firma} (fiktiv) · synthetische Daten.

Spalten:
{spalten}
"""

_STEUERKAT = {"DE": "DE0"}


def migrationscockpit_tabellen(lauf, entscheidungen: Sequence = ()) -> dict[str, pd.DataFrame]:  # noqa: ANN001
    """Je Objekt eine Tabelle der migrierbaren Sätze (Status „bereit“), ohne zusammengeführte Altsätze."""
    st = dict(zip(lauf.readiness.status.schluessel, lauf.readiness.status.status, strict=True))
    zl = zuordnungsliste(list(entscheidungen))
    weg = set()
    for c, alt in zip(zl.cluster, zl.alt, strict=True):
        weg.add(f"{c.split('-')[0]}:{alt}")
    ergebnis = {}
    for objekt, rolle in (("DEBI", "FLCU00/FLCU01 (Kunde)"), ("KRED", "FLVN00/FLVN01 (Lieferant)")):
        s = lauf.saetze[(lauf.saetze.objekt == objekt) & lauf.saetze.schluessel.map(lambda k: st.get(k) == "bereit")
                        & ~lauf.saetze.schluessel.isin(weg)]
        zeilen = []
        for z in s.itertuples(index=False):
            kg = KONTENGRUPPE.get((z.objekt, z.ktogr))
            ust = pz.ust_normal(z.ust_id)
            zeilen.append({
                "QUELLE_NR": z.nr, "BU_GROUP": kg.bp_gruppierung if kg else "", "BU_TYPE": "2", "NAME_ORG1": z.name1,
                "STREET": z.strasse, "HOUSE_NUM1": z.hausnr, "POST_CODE1": z.plz, "CITY1": z.ort, "COUNTRY": z.land,
                "LANGU": z.sprache, "TELNR_LONG": z.telefon, "SMTP_ADDR": z.email,
                "TAXTYPE": (_STEUERKAT.get(ust[:2], f"{ust[:2]}0") if ust else ""), "TAXNUM": ust,
                "KTOGR_QUELLE": z.ktogr, "AKONT": z.akont, "ZTERM": z.zterm, "ROLLE": rolle, "BANKS": z.banks,
                "IBAN_MASKIERT": pz.iban_maskieren(z.iban) if z.iban else ""})
        ergebnis[objekt] = pd.DataFrame(zeilen, columns=list(MIGRATION_SPALTEN))
    return ergebnis


def migrationscockpit_paket(lauf, entscheidungen: Sequence = ()) -> bytes:  # noqa: ANN001
    tabellen = migrationscockpit_tabellen(lauf, entscheidungen)
    bereit = int((lauf.readiness.status.status == "bereit").sum())
    ausgeschlossen = bereit - sum(len(t) for t in tabellen.values())
    dateien = {
        "BEISPIEL_MigrationCockpit_BP_Debitoren.csv": csv_bytes(tabellen["DEBI"]),
        "BEISPIEL_MigrationCockpit_BP_Kreditoren.csv": csv_bytes(tabellen["KRED"]),
        "LIESMICH_BEISPIEL.txt": LIESMICH.format(
            bereit=bereit, ausgeschlossen=ausgeschlossen, stichtag=f"{lauf.stichtag:%d.%m.%Y}", firma=UNTERNEHMEN,
            spalten="\n".join(f"  {k:<14} {v}" for k, v in MIGRATION_SPALTEN.items())).encode("utf-8-sig"),
    }
    return _zip({f"dataguard_migration_cockpit_BEISPIEL/{n}": d for n, d in dateien.items()})
