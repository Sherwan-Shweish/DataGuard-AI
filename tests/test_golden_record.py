"""Golden Record: Überlebensregeln je Feld, Zielnummer, namentliche Entscheidung, Zuordnung alt → neu."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src import golden_record as gr
from tests.conftest import bestand, satz


def _vorschlag(*saetze, aenderung=None):
    df = bestand(*saetze)
    la = aenderung or {s: date(2025, 1, 1) for s in df.schluessel}
    return gr.vorschlag("KRED", list(df.nr), df, la), df


def test_gueltig_vor_ungueltig_und_vollstaendig_vor_leer():
    v, _ = _vorschlag(satz(email="info@@muster.example", telefon=""),
                      satz(nr="101235", email="info@muster.example", letzte_buchung=None, op=""))
    f = {x.feld: x for x in v.felder}
    assert (f["email"].wert, f["email"].regel) == ("info@muster.example", "gültig vor ungültig")
    assert (f["telefon"].wert, f["telefon"].regel) == ("+49 611 1234567", "vollständig vor leer")


def test_quelle_mit_buchung_und_juengste_aenderung():
    a = satz(zterm="ZB14", letzte_buchung=date(2026, 9, 1))
    b = satz(nr="101235", zterm="ZB30", letzte_buchung=None, op="")
    v, _ = _vorschlag(a, b)
    assert {x.feld: (x.wert, x.regel) for x in v.felder}["zterm"] == ("ZB14", "Quelle mit Buchungen vor ungebuchter "
                                                                              "Quelle")
    c = satz(nr="101236", zterm="ZB45", letzte_buchung=None, op="")
    v2, _ = _vorschlag(b, c, aenderung={"KRED:101235": date(2024, 1, 1), "KRED:101236": date(2026, 6, 1)})
    assert {x.feld: (x.wert, x.regel) for x in v2.felder}["zterm"] == ("ZB45", "jüngste Änderung")


def test_zielnummer_und_iban_maskiert():
    v, _ = _vorschlag(satz(nr="101235", letzte_buchung=None, op=""), satz(letzte_buchung=date(2026, 9, 1)))
    assert v.ziel == "101234" and v.zuordnung == [("101235", "101234")]
    assert {x.feld: x.wert for x in v.felder}["iban"] == "DE59 •••• 3344"


def test_entscheidung_nur_mit_namen_und_ohne_aenderung_der_quelldaten():
    v, df = _vorschlag(satz(), satz(nr="101235", letzte_buchung=None, op=""))
    vorher = df.copy()
    for name in ("", "  ", "Max"):
        with pytest.raises(gr.EntscheidungOhneName):
            gr.entscheide(v, "übernehmen", name)
    e = gr.entscheide(v, "übernehmen", "Erika Mustermann", "geprüft", datetime(2026, 10, 1, 9, 30))
    assert e.zuordnung == [("101235", "101234")] and e.zeitpunkt == "2026-10-01T09:30:00"
    assert gr.entscheide(v, "ablehnen", "Erika Mustermann").zuordnung == []
    assert df.equals(vorher)
    with pytest.raises(ValueError):
        gr.entscheide(v, "löschen", "Erika Mustermann")


def test_zuordnungsliste_juengste_entscheidung_gilt(tmp_path):
    v, _ = _vorschlag(satz(), satz(nr="101235", letzte_buchung=None, op=""))
    e1 = gr.entscheide(v, "übernehmen", "Erika Mustermann")
    e2 = gr.entscheide(v, "zurückstellen", "Max Beispiel")
    assert len(gr.zuordnungsliste([e1])) == 1 and gr.zuordnungsliste([e1, e2]).empty
    pfad = tmp_path / "entscheidungen.json"
    gr.speichere([e1, e2], pfad)
    assert gr.lade(pfad) == [e1, e2]


def test_demo_k101(lauf, demo):
    alt = demo["wahrheit"]["sonderfaelle"]["k101_altsatz"]
    v = next(x for x in lauf.vorschlaege if "K101" in x.nummern)
    assert v.ziel == "K101" and (alt, "K101") in v.zuordnung
    f = {x.feld: x for x in v.felder}
    assert f["name1"].wert == "Hanse Fördertechnik GmbH" and f["ust_id"].regel == "vollständig vor leer"
