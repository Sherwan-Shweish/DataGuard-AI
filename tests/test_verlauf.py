"""Qualitätsverlauf: zwölf Monatsstände aus dem Änderungsprotokoll, bewertet mit derselben Engine."""

from __future__ import annotations

import pytest

from src.analyse import laufe, verlauf
from src.config import MONATSENDEN, STICHTAG, VORMONAT


@pytest.fixture(scope="module")
def vl(demo):
    return verlauf(demo["daten"])


def test_zwoelf_monatsstaende(vl):
    assert list(vl.kennzahlen.monatsende) == list(MONATSENDEN) and len(vl.bewegungen) == 11


@pytest.mark.invariante
def test_letzter_stand_gleich_aktuellem_lauf(vl, lauf):
    letzte = vl.kennzahlen.iloc[-1]
    for k, w in lauf.kennzahlen.items():
        assert letzte[k] == w


def test_vormonat_gleich_rekonstruktion(vl, demo):
    vm = laufe(demo["daten"], VORMONAT, mit_vorschlaegen=False)
    assert vl.kennzahlen.iloc[-2]["DAMA-Gesamtscore"] == vm.kennzahlen["DAMA-Gesamtscore"]


def test_bereinigungswelle_sichtbar(vl):
    k = vl.kennzahlen
    assert k["DAMA-Gesamtscore"].iloc[-1] > k["DAMA-Gesamtscore"].iloc[0]
    assert k["Score Aktualität"].iloc[-1] > k["Score Aktualität"].iloc[0]
    assert k["Sätze"].is_monotonic_increasing  # spätere Anlagen sind in früheren Ständen ausgeblendet


def test_rekonstruktion_nimmt_spaetere_aenderungen_zurueck(demo):
    d = demo["daten"]
    a = d.aenderungen[(d.aenderungen.feld == "email") & (d.aenderungen.datum > VORMONAT)]
    z = a.iloc[0]
    alt = d.stand(VORMONAT).set_index("schluessel").loc[f"{z.objekt}:{z.nr}", "email"]
    neu = d.stand(STICHTAG).set_index("schluessel").loc[f"{z.objekt}:{z.nr}", "email"]
    assert (alt, neu) == (z.alt, z.neu)


def test_verursacher(vl):
    s = vl.verursacher.groupby("benutzer")[["neue_befunde", "erledigte_befunde"]].sum()
    assert s.loc["STAMM_ZENTRAL", "erledigte_befunde"] > 0 and s.loc["VERTRIEB_03", "neue_befunde"] > 0


# ── Zerlegung der Readiness-Veränderung ────────────────────────────────────────────────────────────────────────


def test_zerlegung_summiert_exakt_auf_die_veraenderung(vl):
    q = vl.kennzahlen.set_index("monatsende")["Migration-Readiness-Quote"]
    # Kennzahl ist auf 2 Stellen gerundet, die Zerlegung rechnet mit ungerundeten Quoten → Toleranz Rundung
    je_monat = vl.zerlegung.groupby("monatsende").beitrag_pp.sum()
    for monat, summe in je_monat.items():
        assert summe == pytest.approx(q[monat] - q[q.index < monat].iloc[-1], abs=0.011)
    assert vl.zerlegung.beitrag_pp.sum() == pytest.approx(q.iloc[-1] - q.iloc[0], abs=0.011)


def test_zerlegung_aus_protokoll_nicht_gesetzt(vl, demo):
    """Neue Blocker durch Neuanlagen gehören zu echten Anlagebenutzern; Bereinigung zu Änderungsbenutzern."""
    z = vl.zerlegung
    anleger = set(demo["daten"].saetze.ernam)
    aendernde = set(demo["daten"].aenderungen.benutzer)
    assert set(z[z.ursache == "neue Blocker durch Neuanlagen"].benutzer) <= anleger
    assert set(z[z.ursache == "bereinigt"].benutzer) <= aendernde
    s = z.groupby("ursache").beitrag_pp.sum()
    assert s["bereinigt"] > 0 and s["neue Blocker durch Neuanlagen"] < 0      # „DAMA steigt, Readiness sinkt“
    k = vl.kennzahlen
    assert k["DAMA-Gesamtscore"].iloc[-1] > k["DAMA-Gesamtscore"].iloc[0]
    assert k["Migration-Readiness-Quote"].iloc[-1] < k["Migration-Readiness-Quote"].iloc[0]


@pytest.mark.invariante
@pytest.mark.parametrize("monat", [0, 4, 9])
def test_inkrementell_gleich_vollstaendig(vl, demo, monat):
    """Mit gemeinsamem Rechenspeicher (inkrementell) entsteht exakt derselbe Monatsstand wie bei Einzelberechnung."""
    einzeln = laufe(demo["daten"], MONATSENDEN[monat], mit_vorschlaegen=False)
    zeile = vl.kennzahlen.iloc[monat]
    for k, w in einzeln.kennzahlen.items():
        assert zeile[k] == w, k
    for d, s in einzeln.pruefung.dimension_score.items():
        assert zeile[f"Score {d}"] == s
    assert zeile["Befunde"] == len(einzeln.pruefung.befunde)


@pytest.mark.laufzeit
def test_verlauf_ohne_cache_schutzwert(demo):
    """Schutzwert gegen grobe Verschlechterung (≤ 5 s auf jedem Rechner). Den Zielwert ≤ 1,5 s weist
    tools/endabnahme_messen.py nach (docs/Endabnahme.md)."""
    import time

    from src.datenbasis import lade

    frisch = lade(demo["db"])
    start = time.perf_counter()
    verlauf(frisch)
    dauer = time.perf_counter() - start
    print(f"Monatsverlauf ohne Cache: {dauer:.2f} s")
    assert dauer <= 5.0, dauer


def test_ergebniscache_nach_dateistand(tmp_path, demo):
    import os
    import shutil

    from src import zwischenspeicher
    from src.zwischenspeicher import STATISTIK, nach_dateistand

    db = tmp_path / "kopie.db"
    shutil.copy(demo["db"], db)
    aufrufe = []

    @nach_dateistand
    def zaehle(pfad):
        aufrufe.append(pfad)
        return len(aufrufe)

    zwischenspeicher.leeren()
    assert zaehle(db) == 1 and zaehle(db) == 1 and len(aufrufe) == 1 and STATISTIK["treffer"] >= 1
    stand = db.stat()
    os.utime(db, ns=(stand.st_atime_ns, stand.st_mtime_ns + 1_000_000))   # Datei „geändert“
    assert zaehle(db) == 2                                                  # neuer Dateistand → neu berechnet
