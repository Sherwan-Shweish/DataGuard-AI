"""Migration Readiness (CVI): Status je Satz, Quote, Trichter, Blocker, Kunde = Lieferant."""

from __future__ import annotations

import pytest

from src.config import STICHTAG
from src.migration import STATUS, bewerte
from src.regeln import pruefe
from tests.conftest import bestand, satz


def _status(*saetze):
    df = bestand(*saetze)
    r = bewerte(pruefe(df, STICHTAG), df)
    return dict(zip(r.status.schluessel, r.status.status, strict=True)), r


def test_vier_status():
    st, r = _status(
        satz(),                                                        # bereit
        satz(nr="101300", name1="Hinweis Bau KG", plz="10115", ort="Berlin", ust_id="DE287654316",
             iban="", banks="", bankl="", bankn="", swift="", email="x@@y.example"),  # Fehler V10, G08
        satz(nr="700100", ktogr="ZMIT", name1="Anna Muster", plz="80331", ort="München", ust_id="",
             iban="", banks="", bankl="", bankn="", swift=""),        # K02 Blocker
        satz(nr="101400", name1="Alt Handel GmbH", plz="01067", ort="Dresden", ust_id="DE149832767", iban="",
             banks="", bankl="", bankn="", swift="", letzte_buchung=None, op="", loevm="X"),  # archivieren
    )
    assert st == {"KRED:101234": "bereit", "KRED:101300": "bereit nach Bereinigung", "KRED:700100": "blockiert",
                  "KRED:101400": "archivieren"}
    assert r.quote == round(100 * 1 / 3, 2) and r.quote_inkl_bereinigung == round(100 * 2 / 3, 2)
    assert r.trichter == {"alle Sätze": 4, "nicht archivieren": 3, "ohne Blocker": 2, "bereit": 1}
    assert set(r.zaehlung) == set(STATUS)


def test_dublette_mit_archiviertem_partner_blockiert_nicht():
    st, _ = _status(satz(), satz(nr="101235", name1="Muster Metallbau G.m.b.H.", letzte_buchung=None, op="",
                                 erdat=__import__("datetime").date(2019, 1, 1)))
    assert st["KRED:101234"] == "bereit" and st["KRED:101235"] == "archivieren"


def test_dublette_mit_zwei_migrierenden_saetzen_blockiert():
    st, r = _status(satz(), satz(nr="101235", name1="Muster Metallbau G.m.b.H."))
    assert st == {"KRED:101234": "blockiert", "KRED:101235": "blockiert"}
    assert "E01" in set(r.blocker.regel) and "E03" in set(r.blocker.regel)


@pytest.mark.invariante
def test_demo_aktive_partner(lauf):
    st = dict(zip(lauf.readiness.status.schluessel, lauf.readiness.status.status, strict=True))
    assert st["DEBI:K101"] == "bereit"            # Altsatz wird archiviert → kein Hindernis
    assert st["KRED:100100"] == "blockiert"       # doppelter Kreditor mit gleicher IBAN
    assert st["KRED:100300"] == "blockiert"       # zugleich neuer Kunde ohne Verknüpfung
    assert st["KRED:100400"] == "bereit"          # Bankänderung erst am 23.10.2026 (nach dem Stichtag)


@pytest.mark.invariante
def test_quote_definition(lauf):
    r = lauf.readiness
    z = r.zaehlung
    assert sum(z.values()) == len(lauf.saetze)
    assert r.quote == round(100 * z["bereit"] / (len(lauf.saetze) - z["archivieren"]), 2)
    assert r.trichter["alle Sätze"] >= r.trichter["nicht archivieren"] >= r.trichter["ohne Blocker"] \
        >= r.trichter["bereit"]


def test_kunde_lieferant_liste(lauf, demo):
    kl = lauf.readiness.kunde_lieferant
    unverkn = kl[kl.status.str.startswith("unverknüpft")]
    assert len(unverkn) == len(demo["wahrheit"]["kunde_lieferant"]["unverknuepft"])
    assert ("DEBI:" + demo["wahrheit"]["sonderfaelle"]["kunde_lieferant_100300"], "KRED:100300") in set(
        zip(unverkn.debitor, unverkn.kreditor, strict=True))


def test_pflichtfeldmatrix(lauf):
    m = lauf.readiness.pflichtfelder
    assert set(m.pflichtangabe) >= {"Name", "Land", "BP-Gruppierung", "Bankverbindung"}
    assert ((m.quote >= 0) & (m.quote <= 100)).all()
