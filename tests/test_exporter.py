"""Exporte: Gegenprüfung per Formel, deutsches CSV-Format, DAX-Modell, Freigaberegel – und nirgends eine IBAN."""

from __future__ import annotations

import io
import re
import shutil
import zipfile

import pandas as pd
import pytest
from openpyxl import load_workbook

from src import bericht_export as be
from src import exporter as ex
from src import pruefziffern as pz
from src.agent import IBAN_MUSTER_I, Aufgabe, DataGuardAgent, baue_faktenblatt
from src.config import VORMONAT
from src.golden_record import entscheide

LIBREOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


@pytest.fixture(scope="module")
def vormonat(demo):
    from src.analyse import laufe

    return laufe(demo["daten"], VORMONAT, mit_vorschlaegen=False)


@pytest.fixture(scope="module")
def vl(demo):
    from src.analyse import verlauf

    return verlauf(demo["daten"])


@pytest.fixture(scope="module")
def entscheidung(lauf):
    return entscheide(lauf.vorschlaege[0], "übernehmen", "Erika Mustermann", "Test")


@pytest.fixture(scope="module")
def bericht(lauf, vormonat, vl):
    blatt, ps = baue_faktenblatt(lauf, vormonat, vl)
    fp = blatt.fingerabdruck([])
    entwurf = DataGuardAgent(blatt).entwurf(Aufgabe.ZUSAMMENFASSUNG)
    frei = entwurf.freigeben("Erika Mustermann", entwurf.text, blatt, fp)
    offen = DataGuardAgent(blatt).entwurf(Aufgabe.PLAN)  # nicht freigegeben → darf nicht im Bericht stehen
    seiten = be.berichtseiten(lauf, vormonat, vl, [frei, offen], fp, ps)
    return {"seiten": seiten, "pptx": be.erstelle_pptx(seiten), "pdf": be.erstelle_pdf(seiten), "blatt": blatt,
            "frei": frei, "offen": offen, "ps": ps}


@pytest.fixture(scope="module")
def alle_exporte(lauf, vl, entscheidung, bericht):
    return {
        "bereinigung.xlsx": ex.bereinigungsliste_excel(lauf),
        "golden.xlsx": ex.golden_record_excel(lauf, [entscheidung]),
        "bericht.pptx": bericht["pptx"], "bericht.pdf": bericht["pdf"],
        "powerbi.zip": ex.powerbi_paket(lauf, vl), "migration.zip": ex.migrationscockpit_paket(lauf, [entscheidung]),
    }


# ── Textinhalt jeder Exportart ───────────────────────────────────────────────────────────────────────────────


def _text_xlsx(daten: bytes) -> str:
    wb = load_workbook(io.BytesIO(daten))
    return "\n".join(str(c.value) for ws in wb.worksheets for z in ws.iter_rows() for c in z if c.value is not None)


def _text_pptx(daten: bytes) -> str:
    from pptx import Presentation

    return "\n".join(sh.text_frame.text for folie in Presentation(io.BytesIO(daten)).slides for sh in folie.shapes
                     if sh.has_text_frame)


def _text_pdf(daten: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(seite.extract_text() for seite in PdfReader(io.BytesIO(daten)).pages)


def _text_zip(daten: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        return "\n".join(z.read(n).decode("utf-8-sig") for n in z.namelist())


def text_von(name: str, daten: bytes) -> str:
    return {"xlsx": _text_xlsx, "pptx": _text_pptx, "pdf": _text_pdf, "zip": _text_zip}[name.rsplit(".", 1)[1]](daten)


@pytest.mark.parametrize("name", ["bereinigung.xlsx", "golden.xlsx", "bericht.pptx", "bericht.pdf", "powerbi.zip",
                                  "migration.zip"])
def test_kein_export_enthaelt_eine_unmaskierte_iban(demo, alle_exporte, name):
    text = text_von(name, alle_exporte[name])
    kompakt = text.upper().replace(" ", "")
    saetze = demo["daten"].saetze
    ibans = [pz.iban_normal(i) for i in saetze.iban if i]
    assert not any(i in kompakt for i in ibans), name
    gueltig = [m.group(0) for m in IBAN_MUSTER_I.finditer(text) if pz.iban_gueltig(m.group(0).upper())]
    assert gueltig == [], gueltig                                                   # USt-IdNrn. ähneln dem Muster
    konten = [str(k) for k in saetze.bankn if k and len(str(k)) >= 6]
    assert not any(k in text for k in konten), name                       # auch keine Kontonummern
    assert "500400000611223344" not in kompakt and "0611223344" not in kompakt


def test_iban_erscheint_nur_maskiert(alle_exporte):
    text = _text_xlsx(alle_exporte["bereinigung.xlsx"]) + _text_zip(alle_exporte["migration.zip"])
    assert re.search(r"[A-Z]{2}\d{2} •••• \d{4}", text)


# ── Excel: Bereinigungsliste mit Gegenprüfung ────────────────────────────────────────────────────────────────


def test_bereinigungsliste_struktur(lauf, alle_exporte):
    wb = load_workbook(io.BytesIO(alle_exporte["bereinigung.xlsx"]))
    assert wb.sheetnames == ["Hinweise", "Gegenprüfung", "Bereinigungsliste", "Regeln", "Status"]
    ws = wb["Bereinigungsliste"]
    kopf = [c.value for c in ws[3]]
    for spalte in ("Satz", "Objekt", "SAP-Feld", "Regel", "Schweregrad", "Vorschlag", "Status"):
        assert spalte in kopf
    assert ws.max_row - 3 == len(lauf.pruefung.befunde)
    assert ws["C5"].font.name == "Arial"
    assert str(wb["Gegenprüfung"]["C4"].value).startswith("=SUMIFS(")                 # echte Formeln


@pytest.mark.skipif(LIBREOFFICE is None, reason="LibreOffice nicht installiert")
def test_gegenpruefung_python_gleich_excel(alle_exporte):
    e = ex.pruefe_excel(alle_exporte["bereinigung.xlsx"])
    assert e["formelfehler"] == []
    assert e["gesamtstatus"] == "OK", {k: v for k, v in e["pruefungen"].items() if v != "OK"}
    assert len(e["pruefungen"]) >= 12 and set(e["pruefungen"].values()) == {"OK"}


def test_golden_record_excel(alle_exporte, entscheidung):
    wb = load_workbook(io.BytesIO(alle_exporte["golden.xlsx"]))
    assert {"Zuordnung alt → neu", "Entscheidungen", "Vorschläge"} <= set(wb.sheetnames)
    ws = wb["Zuordnung alt → neu"]
    werte = [[c.value for c in z] for z in ws.iter_rows(min_row=4)]
    assert len(werte) == len(entscheidung.zuordnung)
    assert all(z[3] == "Erika Mustermann" for z in werte)
    assert wb["Entscheidungen"]["D4"].value == "Erika Mustermann"


def test_formel_injection_wird_entschaerft():
    assert ex.entschaerfen("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert ex.entschaerfen("@SUM(A1)") == "'@SUM(A1)"
    assert ex.entschaerfen("-cmd|calc") == "'-cmd|calc"
    assert ex.entschaerfen("+49 611 1234567") == "+49 611 1234567"           # Telefonnummern bleiben lesbar
    assert ex.entschaerfen("Muster GmbH") == "Muster GmbH" and ex.entschaerfen(42) == 42
    df = pd.DataFrame({"Name": ["=1+1"]})
    assert ex.csv_bytes(df).decode("utf-8-sig").splitlines()[1] == "'=1+1"


# ── Power BI ─────────────────────────────────────────────────────────────────────────────────────────────────


def _pbi(daten: bytes) -> dict[str, pd.DataFrame]:
    with zipfile.ZipFile(io.BytesIO(daten)) as z:
        return {n.split("/")[-1]: pd.read_csv(io.BytesIO(z.read(n)), sep=";", decimal=",", encoding="utf-8-sig",
                                              dtype=str)
                for n in z.namelist() if n.endswith(".csv")}


def test_powerbi_format_deutsch(alle_exporte):
    with zipfile.ZipFile(io.BytesIO(alle_exporte["powerbi.zip"])) as z:
        roh = z.read("dataguard_powerbi/fakt_verlauf.csv")
        assert roh.startswith(b"\xef\xbb\xbf")                                    # UTF-8 mit BOM
        zeilen = roh.decode("utf-8-sig").splitlines()
        assert zeilen[0].startswith("Monatsende;DAMA_Gesamtscore;")
        assert re.match(r"^31\.10\.2025;\d+,\d+;", zeilen[1])                      # TT.MM.JJJJ, Dezimalkomma
        assert {"measures.dax", "power_query.m", "README.md"} <= {n.split("/")[-1] for n in z.namelist()}


def test_dax_referenzen_existieren(alle_exporte):
    tabellen = _pbi(alle_exporte["powerbi.zip"])
    for tabelle, spalte in ex.dax_spaltenreferenzen(ex.DAX_MEASURES):
        assert spalte in tabellen[f"{tabelle}.csv"].columns, (tabelle, spalte)


def test_powerbi_ergibt_dieselben_kennzahlen(lauf, alle_exporte):
    t = _pbi(alle_exporte["powerbi.zip"])
    pr = t["fakt_pruefung.csv"].astype({"Anwendbar": int, "Verletzt": int}).merge(
        t["dim_regel.csv"][["Regel_ID", "Dimension"]], on="Regel_ID")
    g = pr.groupby("Dimension")[["Anwendbar", "Verletzt"]].sum()
    score = ((g.Anwendbar - g.Verletzt) / g.Anwendbar * 100).round(2).to_dict()
    assert score == lauf.pruefung.dimension_score
    s = t["fakt_status.csv"].Status
    quote = round(100 * (s == "bereit").sum() / (len(s) - (s == "archivieren").sum()), 2)
    assert quote == lauf.readiness.quote and len(t["fakt_befund.csv"]) == len(lauf.pruefung.befunde)
    assert not any("iban" in c.lower() and "maskiert" not in c.lower() for df in t.values() for c in df.columns)


# ── Migration Cockpit (Beispiel) ─────────────────────────────────────────────────────────────────────────────


def test_migrationscockpit_beispiel(lauf, alle_exporte, entscheidung):
    with zipfile.ZipFile(io.BytesIO(alle_exporte["migration.zip"])) as z:
        namen = z.namelist()
        assert all("BEISPIEL" in n for n in namen)
        liesmich = z.read(next(n for n in namen if n.endswith(".txt"))).decode("utf-8-sig")
        deb = pd.read_csv(io.BytesIO(z.read(next(n for n in namen if "Debitoren" in n))), sep=";", dtype=str,
                          encoding="utf-8-sig", keep_default_na=False)
    assert "VORLAGE" in liesmich and "im System prüfen" in liesmich and "NICHT exportiert" in liesmich
    assert list(deb.columns) == list(ex.MIGRATION_SPALTEN)
    st = dict(zip(lauf.readiness.status.schluessel, lauf.readiness.status.status, strict=True))
    assert all(st[f"DEBI:{n}"] == "bereit" for n in deb.QUELLE_NR)
    assert "BANKL" not in deb.columns and "BANKN" not in deb.columns
    for alt, _ in entscheidung.zuordnung:                                         # zusammengeführte Altsätze fehlen
        assert alt not in set(deb.QUELLE_NR)


# ── Readiness-Bericht ────────────────────────────────────────────────────────────────────────────────────────


def test_bericht_nur_freigegebene_kommentare(bericht):
    text = _text_pptx(bericht["pptx"])
    assert "Freigabe: Erika Mustermann" in text
    assert bericht["offen"].text.splitlines()[0][:40] not in text                 # Entwurf nicht im Bericht
    assert "Debitorenquote folgt aus der Suite-Vorgabe" in text


def test_bericht_ohne_gueltige_freigabe(lauf, vormonat, vl, bericht, entscheidung):
    neu = bericht["blatt"].fingerabdruck([entscheidung])                           # Entscheidung ändert den Stand
    seiten = be.berichtseiten(lauf, vormonat, vl, [bericht["frei"]], neu, bericht["ps"])
    assert seiten[-1]["titel"] == "Freigegebene Kommentare"
    assert "keine freigegebenen Kommentare" in seiten[-1]["zeilen"][0]


def test_bericht_pdf_und_deutsches_zahlenformat(bericht):
    text = _text_pdf(bericht["pdf"])
    assert "Stammdaten-Readiness-Bericht" in text and "94,37 %" in text
    assert re.search(r"\d+,\d{2} Pp", text)
    assert len(bericht["seiten"]) >= 6
