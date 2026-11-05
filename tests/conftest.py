"""Gemeinsame Fixtures: Demo-Bestand Seed 42 und Prüf-Seed 4242 einmal je Testlauf in einem temporären Ordner."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from src.config import PRUEF_SEED, SEED
from src.datenbasis import lade
from src.seed_data import erzeuge_datenbank


@pytest.fixture(scope="session")
def demo(tmp_path_factory):
    ordner = tmp_path_factory.mktemp("seed42")
    db, wahrheit = erzeuge_datenbank(SEED, ordner)
    return {"db": db, "daten": lade(db), "wahrheit": json.loads(wahrheit.read_text(encoding="utf-8"))}


@pytest.fixture(scope="session")
def pruefseed(tmp_path_factory):
    ordner = tmp_path_factory.mktemp("seed4242")
    db, wahrheit = erzeuge_datenbank(PRUEF_SEED, ordner)
    return {"db": db, "daten": lade(db), "wahrheit": json.loads(wahrheit.read_text(encoding="utf-8"))}


@pytest.fixture(scope="session")
def lauf(demo):
    from src.analyse import laufe

    return laufe(demo["daten"])


GRUNDSATZ = {
    "objekt": "KRED", "nr": "101234", "ktogr": "KINL", "name1": "Muster Metallbau GmbH", "name2": "", "sortl": "MUSTER",
    "strasse": "Industriestraße", "hausnr": "12", "plz": "65189", "ort": "Wiesbaden", "land": "DE", "sprache": "DE",
    "telefon": "+49 611 1234567", "email": "info@muster-metallbau.example", "ust_id": "DE214365872",
    "akont": "160000", "zterm": "ZB30", "bzirk": "", "banks": "DE", "bankl": "50040000", "bankn": "0611223344",
    "iban": "DE59500400000611223344", "swift": "COBADEFFXXX", "loevm": "", "sperr": "", "erdat": date(2025, 3, 1),
    "ernam": "TEST", "letzte_buchung": date(2026, 9, 1), "op": "X", "verknuepft": "", "branche": "",
    "anz_belege": None, "quelle": "Test",
}


def satz(**aenderungen) -> dict:
    s = {**GRUNDSATZ, **aenderungen}
    if s["objekt"] == "DEBI" and "bzirk" not in aenderungen:
        s["bzirk"] = "WEST"
    if s["objekt"] == "DEBI" and "ktogr" not in aenderungen:
        s["ktogr"] = "DINL"
    if s["objekt"] == "DEBI" and "nr" not in aenderungen:
        s["nr"] = "200100"
    if s["objekt"] == "DEBI" and "akont" not in aenderungen:
        s["akont"] = "140000"
    s["schluessel"] = f"{s['objekt']}:{s['nr']}"
    return s


def bestand(*saetze: dict) -> pd.DataFrame:
    from src.datenbasis import SPALTEN

    return pd.DataFrame(list(saetze))[SPALTEN]
