"""Gemeinsames Zahlenwerk der Suite: Kontrollwerte als feste Konstanten, unabhängig von der JSON-Datei."""

from __future__ import annotations

import pytest

from src import pruefziffern as pz
from src import suite
from src.datenbasis import Stammdaten

FLOWAUDIT_FELDER = ("name1", "strasse", "hausnr", "plz", "ort", "land", "ust_id", "email", "zterm", "iban", "swift",
                    "bankl", "bankn")


@pytest.mark.invariante
def test_referenz_kontrollwerte():
    ref = suite.lade_referenz()
    assert len(ref["debitoren"]) == 12 and len(ref["kreditoren"]) == 6
    assert [d["kunnr"] for d in ref["debitoren"]] == ["K101", "K102", "K103", "K104", "K201", "K202", "K203", "K204",
                                                      "K301", "K302", "K303", "K304"]
    assert sum(d["umsatz_2025_cent"] for d in ref["debitoren"]) == 8_387_306_996  # 83.873.069,96 €
    k101 = ref["debitoren"][0]
    assert (k101["name"], k101["umsatz_2025_cent"], k101["letzte_faktura"]) == (
        "Hanse Fördertechnik GmbH", 948_671_497, "2026-09-03")
    assert {d["region"] for d in ref["debitoren"]} == {"NORD", "SUED", "WEST"}


@pytest.mark.invariante
def test_kreditoren_iban_und_ust_wie_flowaudit():
    ref = {k["lifnr"]: k for k in suite.lade_referenz()["kreditoren"]}
    assert ref["100100"]["iban"] == "DE59500400000611223344"
    for lifnr, k in ref.items():
        assert pz.iban_gueltig(k["iban"]) and pz.iban_bilden("DE", k["blz"] + k["konto"]) == k["iban"]
        assert k["ust_id"] == suite.KONTROLLE_UST[lifnr] and pz.ust_id_de_gueltig(k["ust_id"])
    assert pz.ust_id_de_gueltig(suite.KONTROLLE_UST["EIGENE_FIRMA"])


@pytest.mark.invariante
def test_controllai_abgleich_centgleich():
    a = suite.lade_referenz()["abgleich_controllai"]
    assert a["ergebnis"] == "centgleich" and a["differenz_cent"] == 0 and a["umsatz_2025_cent"] == 8_387_306_996


@pytest.mark.invariante
def test_aktive_partner_unveraendert_in_der_datenbank(demo):
    daten: Stammdaten = demo["daten"]
    s = daten.saetze.set_index("schluessel")
    ref = suite.lade_referenz()
    for d in ref["debitoren"]:
        z = s.loc[f"DEBI:{d['kunnr']}"]
        assert (z["name1"], z["bzirk"]) == (d["name"], d["region"])
        assert z["letzte_buchung"].isoformat() == d["letzte_faktura"]
    for k in ref["kreditoren"]:
        z = s.loc[f"KRED:{k['lifnr']}"]
        erwartet = {"name1": k["name"], "plz": k["plz"], "ort": k["ort"], "land": k["land"], "ust_id": k["ust_id"],
                    "email": k["email"], "zterm": k["zterm"], "iban": k["iban"], "swift": k["bic"],
                    "bankl": k["blz"], "bankn": k["konto"], "strasse": k["strasse"].rsplit(" ", 1)[0],
                    "hausnr": k["strasse"].rsplit(" ", 1)[1]}
        assert {f: z[f] for f in erwartet} == erwartet


@pytest.mark.invariante
def test_altbestand_ohne_umsatz_im_suitezeitraum(demo):
    """Debitoren: kein Umsatz ab 2024 außer den 12 Suite-Kunden. Kreditoren: laufende Lieferanten nur mit Datum und
    Anzahl Belege (keine Beträge) – gekennzeichnet als „nicht Teil der FlowAudit-Stichprobe“."""
    from src.seed_data import QUELLE_LAUFEND

    df = demo["daten"].saetze
    alt = df[~df.schluessel.isin(suite.aktive_schluessel())]
    deb = alt[alt.objekt == "DEBI"]
    assert all(lb is None or lb.year < 2024 for lb in deb.letzte_buchung)
    kred_2024 = alt[(alt.objekt == "KRED") & alt.letzte_buchung.map(lambda d: d is not None and d.year >= 2024)]
    assert len(kred_2024) and (kred_2024.quelle == QUELLE_LAUFEND).all()
    assert kred_2024.anz_belege.map(lambda n: isinstance(n, int) and n >= 1).all()
    anteil = len(kred_2024) / len(alt[alt.objekt == "KRED"])
    assert 0.25 <= anteil <= 0.35, anteil


@pytest.mark.invariante
def test_neuanlagen_der_letzten_12_monate_begrenzt(demo, pruefseed):
    for d in (demo, pruefseed):
        assert 80 <= d["wahrheit"]["neuanlagen_12_monate"] <= 120


@pytest.mark.invariante
def test_aktive_partner_nur_ergaenzt_nie_fehlerhaft_in_genutzten_feldern(demo):
    """Befunde an den 18 Sätzen nur in Feldern, die kein anderer Agent nutzt (Telefon, Verknüpfung, Eindeutigkeit)."""
    from src.analyse import laufe

    lauf = laufe(demo["daten"], mit_vorschlaegen=False)
    b = lauf.pruefung.befunde[lauf.pruefung.befunde.schluessel.isin(suite.aktive_schluessel())]
    assert set(b.regel) <= {"V12", "E01", "E03", "E04", "E05", "A04"}
