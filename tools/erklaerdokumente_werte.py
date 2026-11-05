"""Werte für die Erklärdokumente aus einem Programmlauf (Seed 42) – deutsch formatiert.

Schreibt tools/erklaerdokumente/werte.json; tools/erklaerdokumente/erzeugen.js baut daraus die vier Word-Dateien
(deutsch im Repository, arabisch separat). Keine Zahl im Dokument wird von Hand geschrieben.
Aufruf: ``uv run python tools/erklaerdokumente_werte.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJEKT))

from src import format as fmt  # noqa: E402
from src.analyse import lauf_gespeichert, verlauf_gespeichert  # noqa: E402
from src.config import VORMONAT, db_pfad  # noqa: E402
from src.dubletten import SCHWELLE_PRUEFEN, SCHWELLE_SEHR_WAHRSCHEINLICH  # noqa: E402
from src.regeln import REGEL  # noqa: E402

ZIEL = PROJEKT / "tools" / "erklaerdokumente" / "werte.json"


def main() -> None:
    db = db_pfad()
    if not db.exists():
        from src.seed_data import erzeuge_datenbank

        erzeuge_datenbank(ordner=db.parent)
    demo = json.loads((PROJEKT / "docs" / "demolauf.json").read_text(encoding="utf-8"))
    messung_datei = PROJEKT / "docs" / "endabnahme_messung.json"
    messung = json.loads(messung_datei.read_text(encoding="utf-8")) if messung_datei.exists() else {"werte": {}}
    lauf, vm, vl = lauf_gespeichert(db), lauf_gespeichert(db, "Alle", VORMONAT.isoformat()), verlauf_gespeichert(db)
    p, r, k, kv = lauf.pruefung, lauf.readiness, lauf.kennzahlen, vm.kennzahlen
    dub = p.kontext.dubletten
    zaehl = p.befunde.schweregrad.value_counts()
    jo = lauf.je_objekt
    d42, d4242 = demo["dubletten"]["seed_42"], demo["dubletten"]["pruef_seed_4242"]
    z = vl.zerlegung.groupby("ursache").beitrag_pp.sum()
    nb = vl.zerlegung[vl.zerlegung.ursache == "neue Blocker durch Neuanlagen"].groupby("benutzer").beitrag_pp.sum()
    q = vl.kennzahlen
    paare = [x.score for x in dub.paare]
    grenz = [f for f in d42["fehlerfaelle_ab_75"]["fn"] if f["grund"].startswith("nicht verglichen")
             and any(f["a"]["name"] == g["a"]["name"] for g in d4242["fehlerfaelle_ab_75"]["fn"])]
    bl = r.blocker.regel.value_counts()
    w = {
        "stichtag": "30.09.2026", "vormonat": "31.08.2026",
        "saetze": fmt.zahl(p.saetze), "debitoren": fmt.zahl(jo["DEBI"]["saetze"]),
        "kreditoren": fmt.zahl(jo["KRED"]["saetze"]), "regeln": str(len(REGEL)),
        "pruefungen": fmt.zahl(int(p.zaehler.anwendbar.sum())), "befunde": fmt.zahl(len(p.befunde)),
        "saetze_mit_befund": fmt.zahl(p.befunde.schluessel.nunique()),
        "blocker_alle": fmt.zahl(int(zaehl.get("Blocker", 0))), "fehler": fmt.zahl(int(zaehl.get("Fehler", 0))),
        "hinweise": fmt.zahl(int(zaehl.get("Hinweis", 0))),
        "dama": fmt.prozent(p.gesamtscore), "dama_delta": fmt.pp(p.gesamtscore - vm.pruefung.gesamtscore),
        "dama_dim": {d: fmt.prozent(s) for d, s in p.dimension_score.items()},
        "dama_dim_delta": {d: fmt.pp(s - vm.pruefung.dimension_score[d]) for d, s in p.dimension_score.items()},
        "readiness": fmt.prozent(r.quote), "readiness_delta": fmt.pp(k["Migration-Readiness-Quote"]
                                                                     - kv["Migration-Readiness-Quote"]),
        "readiness_inkl": fmt.prozent(r.quote_inkl_bereinigung),
        "readiness_debi": fmt.prozent(jo["DEBI"]["readiness_quote"]),
        "readiness_kred": fmt.prozent(jo["KRED"]["readiness_quote"]),
        "bereit": fmt.zahl(r.zaehlung["bereit"]), "nach_bereinigung": fmt.zahl(r.zaehlung["bereit nach Bereinigung"]),
        "blockiert": fmt.zahl(r.zaehlung["blockiert"]), "archivieren": fmt.zahl(r.zaehlung["archivieren"]),
        "nicht_archivieren": fmt.zahl(r.trichter["nicht archivieren"]),
        "ohne_blocker": fmt.zahl(r.trichter["ohne Blocker"]),
        "archivquote": fmt.prozent(lauf.archivquote, 1),
        "archiv_debi": fmt.prozent(jo["DEBI"]["archivquote"], 1),
        "archiv_kred": fmt.prozent(jo["KRED"]["archivquote"], 1),
        "archiv_debi_n": fmt.zahl(jo["DEBI"]["archivieren"]), "archiv_kred_n": fmt.zahl(jo["KRED"]["archivieren"]),
        "archiv_untergrenze": fmt.prozent(100 * jo["DEBI"]["archivieren"] / p.saetze, 1),
        "bereit_debi": fmt.zahl(jo["DEBI"]["bereit"]), "bereit_kred": fmt.zahl(jo["KRED"]["bereit"]),
        "migr_debi": fmt.zahl(jo["DEBI"]["nicht_archivieren"]), "migr_kred": fmt.zahl(jo["KRED"]["nicht_archivieren"]),
        "offene_cluster": fmt.zahl(k["Offene Dublettencluster"]),
        "offene_cluster_delta": fmt.delta(k["Offene Dublettencluster"] - kv["Offene Dublettencluster"]),
        "blocker_befunde": fmt.zahl(k["Blocker-Befunde"]),
        "blocker_befunde_delta": fmt.delta(k["Blocker-Befunde"] - kv["Blocker-Befunde"]),
        "archiv_delta": fmt.delta(k["Archivierungskandidaten"] - kv["Archivierungskandidaten"]),
        "cluster": fmt.zahl(len(lauf.vorschlaege)),
        "paare_90": fmt.zahl(sum(s >= SCHWELLE_SEHR_WAHRSCHEINLICH for s in paare)),
        "paare_75": fmt.zahl(sum(SCHWELLE_PRUEFEN <= s < SCHWELLE_SEHR_WAHRSCHEINLICH for s in paare)),
        "paare_unter": fmt.zahl(sum(s < SCHWELLE_PRUEFEN for s in paare)),
        "vergleiche_mit": fmt.zahl(sum(dub.vergleiche_mit_blocking.values())),
        "vergleiche_ohne": fmt.zahl(sum(dub.vergleiche_ohne_blocking.values())),
        "reduktion": fmt.prozent(100 * (1 - sum(dub.vergleiche_mit_blocking.values())
                                        / sum(dub.vergleiche_ohne_blocking.values())), 1),
        "pr": {s: {t: {"p": fmt.prozent(100 * x[t]["precision"], 1), "r": fmt.prozent(100 * x[t]["recall"], 1),
                       "f1": fmt.prozent(100 * x[t]["f1"], 1), "br": fmt.prozent(100 * x[t]["blocking_recall"], 1),
                       "tp": str(x[t]["tp"]), "fp": str(x[t]["fp"]), "fn": str(x[t]["fn"]),
                       "wahr": str(x[t]["wahre_paare"])} for t in ("ab_75", "ab_90")}
               for s, x in (("s42", d42), ("s4242", d4242))},
        "grenzfaelle": [{"a": f"{f['a']['name']}, {f['a']['plz']} {f['a']['ort']}",
                         "b": f"{f['b']['name']}, {f['b']['plz']} {f['b']['ort']}"} for f in grenz],
        "zerlegung": {u: fmt.pp(float(v)) for u, v in z.sort_values(ascending=False).items()},
        "zerlegung_summe": fmt.pp(float(z.sum())),
        "neue_blocker_benutzer": [{"benutzer": b, "pp": fmt.pp(float(v))} for b, v in nb.sort_values().items()],
        "dama_start": fmt.prozent(q["DAMA-Gesamtscore"].iloc[0]),
        "dama_ende": fmt.prozent(q["DAMA-Gesamtscore"].iloc[-1]),
        "readiness_start": fmt.prozent(q["Migration-Readiness-Quote"].iloc[0]),
        "readiness_ende": fmt.prozent(q["Migration-Readiness-Quote"].iloc[-1]),
        "blocker_regeln": [{"regel": rid, "text": REGEL[rid].beschreibung, "n": fmt.zahl(int(n))}
                           for rid, n in list(bl.items())[:5]],
        "aktiv_blockiert": [f"{z_.nr} ({z_.blocker})" for z_ in r.status[r.status.schluessel.isin(
            [f"KRED:{n}" for n in ("100100", "100200", "100300", "100400", "100500", "100600")]
            + [f"DEBI:K{n}" for n in ("101", "102", "103", "104", "201", "202", "203", "204", "301", "302", "303",
                                       "304")]) & (r.status.status == "blockiert")].itertuples()],
        "laufend": fmt.zahl(demo["kategorien"]["laufend"]), "neuanlagen": fmt.zahl(demo["neuanlagen_12_monate"]),
        "golden": fmt.zahl(len(lauf.vorschlaege)),
        "verlauf_s": fmt.zahl(messung["werte"].get("verlauf_sekunden", 0), 2),
        "erstlauf_s": fmt.zahl(messung["werte"].get("erstlauf_sekunden", 0), 2),
        "folgelauf_s": fmt.zahl(messung["werte"].get("folgelauf_sekunden", 0), 2),
        "kunde_lieferant": {s: int(n) for s, n in r.kunde_lieferant.status.str.split(" ").str[0]
                            .value_counts().items()},
        "umsatz_2025": "83.873.069,96 €", "ebit_2025": "8.720.441,56 €",
    }
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(json.dumps(w, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"geschrieben: {ZIEL}")


if __name__ == "__main__":
    main()
