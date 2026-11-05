"""Kontrolltabelle der Suite (docs/Suite-Abstimmung.md): feste Konstanten, unabhängig von src/suite_referenz.json.

Jeder Wert, den DataGuard-AI selbst nutzt, ist hier gegen die Referenzdatei, die Datenbank und das Dokument geprüft.
EBIT 2025 nutzt DataGuard nicht; es wird im Dokument nur als Referenz aus VarianceAI/ControllAI zitiert.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src import pruefziffern as pz
from src.config import BUCHUNGSKREIS, STICHTAG, UNTERNEHMEN, VORMONAT
from src.suite import lade_referenz

DOKUMENT = Path(__file__).resolve().parents[1] / "docs" / "Suite-Abstimmung.md"

KUNDEN = [  # Nummer, Name, Region, Umsatz 2025 in Cent (VarianceAI, centgleich ControllAI)
    ("K101", "Hanse Fördertechnik GmbH", "NORD", 948671497),
    ("K102", "Weser Anlagenbau AG", "NORD", 758523105),
    ("K103", "Elbe Automation KG", "NORD", 591834078),
    ("K104", "Nordwind Maschinen GmbH", "NORD", 407620258),
    ("K201", "Alpen Antriebstechnik GmbH", "SUED", 1135588287),
    ("K202", "Neckar Werkzeugmaschinen AG", "SUED", 910892062),
    ("K203", "Isar Robotics GmbH", "SUED", 715739775),
    ("K204", "Bodensee Verpackungstechnik KG", "SUED", 486055269),
    ("K301", "Rheinland Industrieanlagen GmbH", "WEST", 852785335),
    ("K302", "Ruhr Stahlbau AG", "WEST", 679278858),
    ("K303", "Mosel Prozesstechnik GmbH", "WEST", 534712298),
    ("K304", "Eifel Fördersysteme KG", "WEST", 365606174),
]
LIEFERANTEN = [  # Nummer, Name, IBAN maskiert, USt-IdNr. (FlowAudit-AI 1.2.1)
    ("100100", "Hessen Hydraulik GmbH", "DE59 •••• 3344", "DE214365872"),
    ("100200", "Taunus Präzisionsteile KG", "DE20 •••• 5667", "DE287654316"),
    ("100300", "Mainzer Elektrotechnik AG", "DE14 •••• 0400", "DE149832767"),
    ("100400", "Rheingau Logistik & Verpackung GmbH", "DE46 •••• 7654", "DE265437897"),
    ("100500", "Odenwald Industriebedarf GmbH", "DE25 •••• 8990", "DE231987458"),
    ("100600", "Bürowelt Wiesbaden e.K.", "DE07 •••• 6777", "DE298765120"),
]
UMSATZ_2025_CENT = 8387306996
EBIT_2025_ZITAT = "8.720.441,56"


def _euro(cent: int) -> str:
    return f"{cent / 100:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def test_stichtag_firma_buchungskreis():
    ref = lade_referenz()
    assert STICHTAG == date(2026, 9, 30) and VORMONAT == date(2026, 8, 31)
    assert ref["stichtag"] == "2026-09-30"
    assert UNTERNEHMEN == ref["firma"]["name"] == "RheinMain Industrietechnik GmbH"
    assert BUCHUNGSKREIS == ref["firma"]["buchungskreis"] == "1000"
    assert (ref["firma"]["strasse"], ref["firma"]["plz"], ref["firma"]["ort"]) == ("Mainzer Straße 120", "65189",
                                                                                   "Wiesbaden")


def test_zwoelf_kunden_wie_varianceai():
    ref = {x["kunnr"]: x for x in lade_referenz()["debitoren"]}
    assert len(ref) == 12
    for nr, name, region, umsatz in KUNDEN:
        assert (ref[nr]["name"], ref[nr]["region"], ref[nr]["umsatz_2025_cent"]) == (name, region, umsatz), nr
    assert sum(u for *_, u in KUNDEN) == UMSATZ_2025_CENT == lade_referenz()["kontrollwerte"]["umsatz_2025_summe_cent"]
    assert _euro(UMSATZ_2025_CENT) == "83.873.069,96"


def test_sechs_lieferanten_wie_flowaudit():
    ref = {x["lifnr"]: x for x in lade_referenz()["kreditoren"]}
    assert len(ref) == 6
    for nr, name, iban_maskiert, ust in LIEFERANTEN:
        x = ref[nr]
        assert (x["name"], pz.iban_maskieren(x["iban"]), x["ust_id"]) == (name, iban_maskiert, ust), nr
        assert pz.iban_gueltig(x["iban"]) and pz.ust_id_de_gueltig(x["ust_id"])


def test_datenbank_traegt_dieselben_schluessel(demo):
    s = demo["daten"].saetze.set_index("schluessel")
    for nr, name, region, _ in KUNDEN:
        assert (s.loc[f"DEBI:{nr}", "name1"], s.loc[f"DEBI:{nr}", "bzirk"]) == (name, region)
    for nr, name, iban_maskiert, ust in LIEFERANTEN:
        z = s.loc[f"KRED:{nr}"]
        assert (z["name1"], pz.iban_maskieren(z["iban"]), z["ust_id"]) == (name, iban_maskiert, ust)


@pytest.mark.parametrize("zeile", KUNDEN, ids=[k[0] for k in KUNDEN])
def test_dokument_kunden(zeile):
    nr, name, region, umsatz = zeile
    text = DOKUMENT.read_text(encoding="utf-8")
    assert f"| {nr} | {name} | {region} | {_euro(umsatz)} |" in text


@pytest.mark.parametrize("zeile", LIEFERANTEN, ids=[x[0] for x in LIEFERANTEN])
def test_dokument_lieferanten(zeile):
    nr, name, iban_maskiert, ust = zeile
    assert f"| {nr} | {name} | {iban_maskiert} | {ust} |" in DOKUMENT.read_text(encoding="utf-8")


def test_dokument_summen_und_ebit_zitat():
    text = DOKUMENT.read_text(encoding="utf-8")
    assert "83.873.069,96" in text and EBIT_2025_ZITAT in text
    assert "nur als Referenz zitiert" in text
    for agent in ("DataGuard-AI", "FlowAudit-AI", "VarianceAI", "ControllAI"):
        assert agent in text
