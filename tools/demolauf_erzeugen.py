"""Erzeugt docs/demolauf.json aus einem vollständigen Programmlauf (Seed 42 und Prüf-Seed 4242).

Alle Zahlen in README, docs/methodik.md und den Erklärdokumenten stammen aus dieser Datei – nichts wird geschätzt.
Aufruf:  uv run python tools/demolauf_erzeugen.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyse import laufe, verlauf  # noqa: E402
from src.config import PRUEF_SEED, SEED, VORMONAT  # noqa: E402
from src.datenbasis import lade  # noqa: E402
from src.dubletten import (  # noqa: E402
    SCHWELLE_PRUEFEN,
    SCHWELLE_SEHR_WAHRSCHEINLICH,
    finde_dubletten,
    miss,
    wahre_paare,
)
from src.regeln import REGELN  # noqa: E402
from src.seed_data import erzeuge_datenbank  # noqa: E402
from src.suite import aktive_schluessel  # noqa: E402

ZIEL = Path(__file__).resolve().parents[1] / "docs" / "demolauf.json"


def _messung(seed: int, ordner: Path) -> dict:
    db, w = erzeuge_datenbank(seed, ordner)
    wahrheit = json.loads(w.read_text(encoding="utf-8"))
    daten = lade(db)
    start = time.perf_counter()
    e = finde_dubletten(daten.saetze)
    dauer = time.perf_counter() - start
    return {
        "seed": seed, "umfang": wahrheit["umfang"],
        "wahre_cluster": {o: len(c) for o, c in wahrheit["dubletten"].items()},
        "gefundene_cluster": {o: len(c) for o, c in e.cluster.items()},
        "vergleiche_ohne_blocking": e.vergleiche_ohne_blocking, "vergleiche_mit_blocking": e.vergleiche_mit_blocking,
        "kandidaten_je_pass": e.kandidaten_je_pass,
        "ab_75": miss(e, wahrheit, SCHWELLE_PRUEFEN).als_dict(),
        "ab_90": miss(e, wahrheit, SCHWELLE_SEHR_WAHRSCHEINLICH).als_dict(),
        "laufzeit_sekunden": round(dauer, 3),
        "fehlerfaelle_ab_75": _fehlerfaelle(e, wahrheit, daten),
    }, daten, wahrheit


def _fehlerfaelle(e, wahrheit: dict, daten) -> dict:  # noqa: ANN001
    """Nicht erkannte (FN) und falsch erkannte (FP) Paare ab Schwelle 75 – mit Grund (nicht verglichen / Score)."""
    s = daten.saetze.set_index("schluessel")
    wahr = wahre_paare(wahrheit)
    score = {(p.objekt, p.a, p.b): p.score for p in e.paare}
    treffer = {k for k, v in score.items() if v >= SCHWELLE_PRUEFEN}

    def satz(o: str, n: str) -> dict:
        z = s.loc[f"{o}:{n}"]
        return {"nr": n, "name": z["name1"], "plz": z["plz"], "ort": z["ort"],
                "iban_oder_ust": bool(z["iban"] or z["ust_id"])}

    return {
        "fn": [{"objekt": o, "a": satz(o, a), "b": satz(o, b), "score": score.get((o, a, b)),
                "grund": "nicht verglichen (kein Blocking-Pass)" if (o, a, b) not in score else "Score unter 75"}
               for o, a, b in sorted(wahr - treffer)],
        "fp": [{"objekt": o, "a": satz(o, a), "b": satz(o, b), "score": score[(o, a, b)]}
               for o, a, b in sorted(treffer - wahr)],
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dub42, daten, wahrheit = _messung(SEED, Path(tmp) / "s42")
        dub4242, _, _ = _messung(PRUEF_SEED, Path(tmp) / "s4242")
        start = time.perf_counter()
        lauf = laufe(daten)
        t_lauf = time.perf_counter() - start
        vm = laufe(daten, VORMONAT, mit_vorschlaegen=False)
        zeiten = []
        for _ in range(5):  # kalt: jeweils frisch geladen, ohne Ergebniscache
            frisch = lade(Path(tmp) / "s42" / "dataguard.db")
            start = time.perf_counter()
            vl = verlauf(frisch)
            zeiten.append(time.perf_counter() - start)
        t_verlauf = sorted(zeiten)[2]
    p, r = lauf.pruefung, lauf.readiness
    zaehler = p.zaehler.set_index("regel")
    st = r.status.set_index("schluessel")
    ergebnis = {
        "hinweis": "Synthetische Daten der fiktiven RheinMain Industrietechnik GmbH – "
                   "erzeugt per tools/demolauf_erzeugen.py",
        "stichtag": lauf.stichtag.isoformat(), "vormonat": VORMONAT.isoformat(), "seed": SEED,
        "umfang": wahrheit["umfang"], "kategorien": wahrheit["kategorien"], "regeln": len(REGELN),
        "neuanlagen_12_monate": wahrheit["neuanlagen_12_monate"],
        "archivquote": lauf.archivquote,
        "je_objekt": lauf.je_objekt,
        "archiv_je_objekt": {o: {"archivieren": int(((r.status.objekt == o)
                                                     & (r.status.status == "archivieren")).sum()),
                                 "saetze": int((r.status.objekt == o).sum())} for o in ("DEBI", "KRED")},
        "fehlerkatalog": {r_.id: {"beschreibung": r_.beschreibung, "dimension": r_.dimension,
                                  "schweregrad": r_.schweregrad, "eingebaut": len(wahrheit["befunde"].get(r_.id, [])),
                                  "gefunden": int(zaehler.loc[r_.id, "verletzt"]),
                                  "anwendbar": int(zaehler.loc[r_.id, "anwendbar"])} for r_ in REGELN},
        "dama": p.dimension_score, "dama_gesamt": p.gesamtscore,
        "kennzahlen": lauf.kennzahlen, "kennzahlen_vormonat": vm.kennzahlen,
        "readiness": {"quote": r.quote, "quote_inkl_bereinigung": r.quote_inkl_bereinigung, "zaehlung": r.zaehlung,
                      "trichter": r.trichter, "blocker_je_regel": r.blocker.regel.value_counts().to_dict(),
                      "kunde_lieferant": r.kunde_lieferant.status.str.split(" ").str[0].value_counts().to_dict()},
        "aktive_partner": {s: {"status": st.loc[s, "status"], "blocker": st.loc[s, "blocker"]}
                           for s in sorted(aktive_schluessel())},
        "dubletten": {"seed_42": dub42, "pruef_seed_4242": dub4242},
        "golden_record_vorschlaege": len(lauf.vorschlaege),
        "verlauf": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in z.items()}
                    for z in vl.kennzahlen.to_dict("records")],
        "verursacher": vl.verursacher.groupby("benutzer")[["neue_befunde", "erledigte_befunde"]].sum()
        .reset_index().to_dict("records"),
        "zerlegung_readiness": vl.zerlegung.assign(monatsende=vl.zerlegung.monatsende.map(str))
        .groupby("ursache").beitrag_pp.sum().round(2).to_dict(),
        "zerlegung_je_monat": [{**z, "monatsende": str(z["monatsende"]), "beitrag_pp": round(z["beitrag_pp"], 3)}
                               for z in vl.zerlegung.to_dict("records")],
        "laufzeiten_sekunden": {"gesamtlauf": round(t_lauf, 2), "verlauf_12_monate_median_kalt": round(t_verlauf, 2)},
    }
    ZIEL.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1, default=int) + "\n", encoding="utf-8")
    print(f"geschrieben: {ZIEL}")


if __name__ == "__main__":
    main()
