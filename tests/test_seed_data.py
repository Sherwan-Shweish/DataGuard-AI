"""Datengenerator: Reproduzierbarkeit, Umfang, eingebaute Fehler = Befunde der Engine, Änderungsprotokoll."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date

import pytest

from src import pruefziffern as pz
from src.config import PRUEF_SEED, SEED, STICHTAG
from src.regeln import pruefe
from src.seed_data import INJEKTIONSTEXT, erzeuge_datenbank


def _hash(db) -> str:
    with sqlite3.connect(db) as con:
        return hashlib.sha256("\n".join(con.iterdump()).encode()).hexdigest()


@pytest.mark.invariante
def test_gleicher_seed_gleiche_datenbank(tmp_path, demo):
    db, _ = erzeuge_datenbank(SEED, tmp_path)
    assert _hash(db) == _hash(demo["db"])


def test_anderer_seed_andere_datenbank(demo, pruefseed):
    assert _hash(demo["db"]) != _hash(pruefseed["db"])
    assert pruefseed["wahrheit"]["seed"] == PRUEF_SEED


@pytest.mark.parametrize("fixture", ["demo", "pruefseed"])
def test_umfang_realistisch(fixture, request):
    w = request.getfixturevalue(fixture)["wahrheit"]
    assert 600 <= w["umfang"]["DEBI"] <= 1500 and 400 <= w["umfang"]["KRED"] <= 1000
    assert all(2 <= len(c) <= 4 for o in ("DEBI", "KRED") for c in w["dubletten"][o])


@pytest.mark.invariante
@pytest.mark.parametrize("fixture", ["demo", "pruefseed"])
def test_eingebaute_fehler_werden_exakt_gefunden(fixture, request):
    """Jede Regel außer E01/E02 (Dubletten – über Precision/Recall gemessen) findet genau die Wahrheitsdatei."""
    d = request.getfixturevalue(fixture)
    e = pruefe(d["daten"].saetze, STICHTAG, d["daten"].aenderungen)
    ist = {r: set(g.schluessel) for r, g in e.befunde.groupby("regel")}
    for regel, erwartet in d["wahrheit"]["befunde"].items():
        assert ist.get(regel, set()) == set(erwartet), regel
    assert set(ist) - {"E01", "E02"} <= set(d["wahrheit"]["befunde"])


def test_sonderfaelle(demo):
    df = demo["daten"].saetze.set_index("schluessel")
    w = demo["wahrheit"]["sonderfaelle"]
    alt = df.loc[f"DEBI:{w['k101_altsatz']}"]
    assert alt["name1"] == "Hanse Foerdertechnik G.m.b.H." and alt["letzte_buchung"] is None
    dup = df.loc[f"KRED:{w['kreditor_100100_dublette']}"]
    assert dup["iban"] == df.loc["KRED:100100", "iban"]
    assert INJEKTIONSTEXT in df.loc[w["datentext_angriff"], "name2"]
    assert df.loc[f"DEBI:{w['kunde_lieferant_100300']}", "ust_id"] == df.loc["KRED:100300", "ust_id"]


def test_bankaenderungen_auf_einer_zeitachse_mit_flowaudit(demo):
    """FlowAudit-AI (Stichtag 28.10.2026): 100100 am 01.04.2026, 100400 am 23.10.2026 – nach unserem Stichtag."""
    a = demo["daten"].aenderungen
    b = a[a.feld == "iban"].set_index("nr")
    assert b.loc["100100", "datum"] == date(2026, 4, 1) and b.loc["100100", "benutzer"] == "KRED_SACHB1"
    assert "100400" not in b.index  # erst im laufenden Rechnungseingang sichtbar (FlowAudit-AI)
    vier_augen = demo["wahrheit"]["sonderfaelle"]["vier_augen_bankaenderung"]
    assert demo["wahrheit"]["befunde"]["A04"] == [f"KRED:{vier_augen}"]


def test_vier_augen_fall_im_eigenen_bestand(demo):
    nr = demo["wahrheit"]["sonderfaelle"]["vier_augen_bankaenderung"]
    a = demo["daten"].aenderungen
    b = a[(a.nr == nr) & (a.feld == "iban")]
    assert nr not in {"100100", "100200", "100300", "100400", "100500", "100600"}
    assert list(b.datum) == [date(2026, 9, 25)] and b.alt.iloc[0].endswith("2468") and "••••" in b.alt.iloc[0]


def test_protokoll_bank_nur_maskiert_und_gueltig(demo):
    """IBAN im Protokoll nur maskiert; Bankänderungen nur von gültig nach gültig (Rekonstruktion bleibt korrekt)."""
    with sqlite3.connect(demo["db"]) as con:
        werte = con.execute("SELECT VALUE_OLD, VALUE_NEW FROM CDPOS WHERE FNAME IN ('IBAN','BANKN')").fetchall()
    assert werte and all("••••" in a and "••••" in n for a, n in werte if a or n)
    assert all(not pz.iban_gueltig(a.replace(" ", "")) for a, _ in werte)  # nie im Klartext
    a = demo["daten"].aenderungen
    assert set(a[a.feld == "iban"].nr) == {"100100", demo["wahrheit"]["sonderfaelle"]["vier_augen_bankaenderung"]}


def test_buchungsdaten_ohne_betraege(demo):
    b = demo["daten"].buchungsdaten
    assert set(b.columns) == {"schluessel", "objekt", "nr", "budat"}
    with sqlite3.connect(demo["db"]) as con:
        spalten = {r[1] for t in ("ZDG_VERKEHR", "ZDG_BUCHUNGSDATEN") for r in con.execute(f"PRAGMA table_info({t})")}
    assert not any(s.startswith(("BETRAG", "WRBTR", "DMBTR", "HSL")) for s in spalten)
    k101 = b[b.schluessel == "DEBI:K101"].budat
    assert k101.max() == date(2026, 9, 3)
    assert demo["daten"].stand(date(2026, 8, 31)).set_index("schluessel").loc["DEBI:K101", "letzte_buchung"] \
        <= date(2026, 8, 31)
