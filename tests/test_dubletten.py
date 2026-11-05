"""Dublettenerkennung: Blocking, Score, Erklärbarkeit, Cluster, Messung und Laufzeit."""

from __future__ import annotations

import time

import pytest

from src.config import STICHTAG
from src.dubletten import (
    SCHWELLE_PRUEFEN,
    SCHWELLE_SEHR_WAHRSCHEINLICH,
    Paar,
    cluster_bilden,
    finde_dubletten,
    miss,
    wahre_paare,
)
from tests.conftest import bestand, satz


def test_blocking_paesse():
    df = bestand(
        satz(),
        satz(nr="101235", name1="Muster Metallbau G.m.b.H.", strasse="Industriestr."),  # gleiche PLZ
        satz(nr="101236", name1="Ganz Anders AG", plz="10115", ort="Berlin", ust_id="DE287654316"),  # gleiche IBAN
        satz(nr="101237", name1="Muster Metallbau GmbH", plz="80331", ort="München", iban="", ust_id=""),  # Anfang
        satz(nr="101238", name1="Zebra Werke KG", plz="01067", ort="Dresden", iban="", ust_id=""),
    )
    e = finde_dubletten(df)
    paare = {(p.a, p.b): p.paesse for p in e.paare}
    assert "PLZ" in paare[("101234", "101235")]
    assert "IBAN/USt" in paare[("101234", "101236")]
    assert "Namensanfang" in paare[("101234", "101237")]
    assert not any("101238" in k for k in paare)
    assert e.vergleiche_ohne_blocking["KRED"] == 10 and e.vergleiche_mit_blocking["KRED"] < 10


def test_score_und_erklaerung():
    df = bestand(satz(), satz(nr="101235", name1="Muster Metallbau G.m.b.H.", strasse="Industriestr."))
    p = finde_dubletten(df).paare[0]
    m = p.merkmale
    assert p.score == 100.0 and p.stufe == "sehr wahrscheinlich"
    assert m["name_aehnlichkeit"] == 100.0 and m["gleiche_iban"] and m["gleiche_ust"]
    assert round(m["beitrag_name"] + m["beitrag_strasse"] + m["beitrag_ort"] + m["beitrag_merkmale"], 1) >= p.score


def test_verschiedene_ust_senkt_score():
    a = satz()
    b = satz(nr="101235", ust_id="DE287654316", iban="", telefon="+49 611 9999999")
    p = finde_dubletten(bestand(a, b)).paare[0]
    assert p.merkmale["ust_verschieden"] and p.score == 80.0  # 60 + 25 + 15 − 20 + 0


def test_cluster_transitiv_union_find():
    paare = [Paar("DEBI", "1", "2", 95, "", {}, ()), Paar("DEBI", "2", "3", 80, "", {}, ()),
             Paar("DEBI", "4", "5", 60, "", {}, ())]
    assert cluster_bilden(paare)["DEBI"] == [["1", "2", "3"]]


def test_schwellen_fest():
    assert (SCHWELLE_SEHR_WAHRSCHEINLICH, SCHWELLE_PRUEFEN) == (90, 75)


@pytest.mark.parametrize("fixture", ["demo", "pruefseed"])
def test_messung_precision_recall(fixture, request):
    """Ehrliche Messung – Grenzwerte sichern nur gegen Rückschritte; Schwellen auf dem Prüf-Seed nie angepasst."""
    d = request.getfixturevalue(fixture)
    e = finde_dubletten(d["daten"].saetze)
    m75, m90 = miss(e, d["wahrheit"], SCHWELLE_PRUEFEN), miss(e, d["wahrheit"], SCHWELLE_SEHR_WAHRSCHEINLICH)
    assert m75.precision >= 0.90 and m75.recall >= 0.90 and m75.f1 >= 0.90
    assert m90.precision >= 0.98
    assert m75.blocking_recall < 1.0  # Grenzfälle (Umzug + vertauschte Wortfolge) werden bewusst nicht gefunden
    print(f"\n{fixture}: P {m75.precision:.4f} R {m75.recall:.4f} F1 {m75.f1:.4f} · ≥90: P {m90.precision:.4f} "
          f"R {m90.recall:.4f} · Blocking-Recall {m75.blocking_recall:.4f}")


def test_blocking_grenzfaelle_nicht_verglichen(demo):
    e = finde_dubletten(demo["daten"].saetze)
    verglichen = {(p.objekt, p.a, p.b) for p in e.paare}
    for objekt in ("debi", "kred"):
        a, b = sorted(demo["wahrheit"]["sonderfaelle"][f"blocking_grenze_{objekt}"])
        assert (objekt.upper(), a, b) not in verglichen


def test_factoring_keine_dublette(demo):
    a, b = demo["wahrheit"]["sonderfaelle"]["factoring"]
    e = finde_dubletten(demo["daten"].saetze)
    p = next(p for p in e.paare if (p.a, p.b) == tuple(sorted((a, b))))
    assert p.merkmale["gleiche_iban"] and p.score < SCHWELLE_PRUEFEN


def test_wahre_paare_aus_clustern():
    w = {"dubletten": {"DEBI": [["1", "2", "3"]], "KRED": [["7", "8"]]}}
    assert len(wahre_paare(w)) == 4


@pytest.mark.laufzeit
def test_laufzeit_dublettenerkennung(demo):
    start = time.perf_counter()
    finde_dubletten(demo["daten"].saetze)
    dauer = time.perf_counter() - start
    print(f"\nDublettenerkennung {len(demo['daten'].saetze)} Sätze: {dauer:.2f} s")
    assert dauer < 3.0


def test_stichtag_unabhaengig():
    assert STICHTAG.isoformat() == "2026-09-30"


@pytest.mark.invariante
def test_inkrementell_gleich_vollstaendig_je_monat(demo):
    """Schlanker Modus (Monatsverlauf) liefert je Stand dieselben Treffer, Cluster und Vergleichszahlen."""
    from src.config import MONATSENDEN
    from src.dubletten import SCHWELLE_PRUEFEN, Rechenspeicher, finde_dubletten

    sp = Rechenspeicher()
    sp.schlank = True
    for tag in MONATSENDEN:
        stand = demo["daten"].stand(tag)
        voll, schlank = finde_dubletten(stand), finde_dubletten(stand, sp)
        erwartet = {(p.objekt, p.a, p.b, p.score) for p in voll.paare if p.score >= SCHWELLE_PRUEFEN}
        assert {(p.objekt, p.a, p.b, p.score) for p in schlank.paare} == erwartet, tag
        assert schlank.cluster == voll.cluster
        assert schlank.vergleiche_mit_blocking == voll.vergleiche_mit_blocking
        assert schlank.vergleiche_ohne_blocking == voll.vergleiche_ohne_blocking
