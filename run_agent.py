"""DataGuard-AI – Kommandozeile für den Stammdaten-Check.

Beispiele::

    python run_agent.py daten                       # synthetische Daten → data/sample/dataguard.db (+ wahrheit.json)
    python run_agent.py diagnose                    # Umgebung, Suite-Kontrollwerte, Datenbank
    python run_agent.py pruefen --objekt KRED       # Regelwerk: DAMA-Scores und Befunde je Regel
    python run_agent.py dubletten                   # Cluster, Blocking, Precision/Recall (Seed 42 und Prüf-Seed)
    python run_agent.py readiness                   # Migration Readiness (CVI) mit Trichter und Blockern
    python run_agent.py verlauf                     # Qualitätsverlauf über 12 Monatsstände

Alle Prüfungen laufen offline und deterministisch. Die Kennzahlen stammen ausschließlich aus Programmläufen.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from src import format as fmt
from src.config import PRUEF_SEED, PRUEFSEED_VERZEICHNIS, SEED, STICHTAG, VORMONAT, WAHRHEIT_PFAD, db_pfad


def _daten():
    from src.datenbasis import lade

    if not db_pfad().exists():
        from src.seed_data import erzeuge_datenbank

        erzeuge_datenbank(SEED, db_pfad().parent)
    return lade(db_pfad())


def befehl_daten(args: argparse.Namespace) -> int:
    from src.seed_data import erzeuge_datenbank

    ordner = Path(args.ordner) if args.ordner else (PRUEFSEED_VERZEICHNIS if args.seed == PRUEF_SEED
                                                    else db_pfad().parent)
    db, wahrheit = erzeuge_datenbank(args.seed, ordner)
    w = json.loads(wahrheit.read_text(encoding="utf-8"))
    print(f"Seed {args.seed}: {w['umfang']['DEBI']} Debitoren, {w['umfang']['KRED']} Kreditoren → {db}")
    print("  Kategorien: " + ", ".join(f"{k} {v}" for k, v in w["kategorien"].items()))
    print(f"  Dublettencluster: {len(w['dubletten']['DEBI'])} Debitoren, {len(w['dubletten']['KRED'])} Kreditoren")
    print(f"  Wahrheitsdatei: {wahrheit}")
    return 0


def befehl_diagnose(args: argparse.Namespace) -> int:
    from src.diagnose import bericht

    print(bericht())
    return 0


def befehl_pruefen(args: argparse.Namespace) -> int:
    from src.analyse import laufe
    from src.regeln import REGEL

    lauf = laufe(_daten(), objekt=args.objekt, mit_vorschlaegen=False)
    p = lauf.pruefung
    print(f"Regelwerk · {args.objekt} · Stand {fmt.datum(STICHTAG)} · {fmt.zahl(p.saetze)} Sätze · "
          f"{len(REGEL)} Regeln · synthetische Daten")
    for d, s in p.dimension_score.items():
        print(f"  {d:<16} {fmt.prozent(s):>9}")
    print(f"  {'DAMA-Gesamt':<16} {fmt.prozent(p.gesamtscore):>9}  (Mittelwert der fünf Dimensionen)")
    print("\nBefunde je Regel (verletzt / anwendbar):")
    for z in p.zaehler[p.zaehler.verletzt > 0].sort_values(["schweregrad", "verletzt"], ascending=[True, False]) \
            .itertuples():
        print(f"  {z.regel}  {z.schweregrad:<8} {z.beschreibung[:62]:<62} {fmt.zahl(z.verletzt):>5} / "
              f"{fmt.zahl(z.anwendbar)}")
    return 0


def befehl_dubletten(args: argparse.Namespace) -> int:
    from src.datenbasis import lade
    from src.dubletten import SCHWELLE_PRUEFEN, SCHWELLE_SEHR_WAHRSCHEINLICH, finde_dubletten, miss

    daten = _daten()
    e = finde_dubletten(daten.saetze)
    print("Dublettenerkennung · Score = 0,60 Name + 0,25 Straße + 0,15 Ort + Merkmale (IBAN/USt +15, Telefon +10)")
    for o in ("DEBI", "KRED"):
        print(f"  {o}: Vergleiche ohne Blocking {fmt.zahl(e.vergleiche_ohne_blocking.get(o, 0))} · mit Blocking "
              f"{fmt.zahl(e.vergleiche_mit_blocking[o])} · Cluster ab {SCHWELLE_PRUEFEN}: {len(e.cluster[o])}")
    proben = [("Seed 42", WAHRHEIT_PFAD, None)]
    pruef_db = PRUEFSEED_VERZEICHNIS / "dataguard.db"
    if args.pruefseed and not pruef_db.exists():
        from src.seed_data import erzeuge_datenbank

        erzeuge_datenbank(PRUEF_SEED, PRUEFSEED_VERZEICHNIS)
    if pruef_db.exists():
        proben.append((f"Prüf-Seed {PRUEF_SEED}", PRUEFSEED_VERZEICHNIS / "wahrheit.json", pruef_db))
    print("\nMessung gegen die Wahrheitsdatei (Paarebene):")
    for name, wpfad, db in proben:
        if not Path(wpfad).exists():
            continue
        w = json.loads(Path(wpfad).read_text(encoding="utf-8"))
        erg = e if db is None else finde_dubletten(lade(db).saetze)
        for s in (SCHWELLE_PRUEFEN, SCHWELLE_SEHR_WAHRSCHEINLICH):
            m = miss(erg, w, s)
            print(f"  {name:<15} ab {s}: Precision {fmt.prozent(100 * m.precision, 1):>8} · Recall "
                  f"{fmt.prozent(100 * m.recall, 1):>8} · F1 {fmt.prozent(100 * m.f1, 1):>8} · "
                  f"TP {m.tp} FP {m.fp} FN {m.fn} · Blocking-Recall {fmt.prozent(100 * m.blocking_recall, 1)}")
    print("\nStärkste Paare:")
    for p in sorted(e.treffer(), key=lambda x: -x.score)[: args.top]:
        print(f"  {p.objekt} {p.a}–{p.b}  {fmt.zahl(p.score, 1):>5}  {p.stufe:<20} "
              f"Name {p.merkmale['name_aehnlichkeit']:.0f}"
              f" · Straße {p.merkmale['strasse_aehnlichkeit']:.0f} · IBAN {'ja' if p.merkmale['gleiche_iban'] else '–'}"
              f" · USt {'ja' if p.merkmale['gleiche_ust'] else '–'} · Pässe: {', '.join(p.paesse)}")
    return 0


def befehl_readiness(args: argparse.Namespace) -> int:
    from src.analyse import laufe

    daten = _daten()
    lauf = laufe(daten, objekt=args.objekt, mit_vorschlaegen=False)
    vm = laufe(daten, VORMONAT, args.objekt, mit_vorschlaegen=False)
    r = lauf.readiness
    print(f"Migration Readiness (CVI) · {args.objekt} · Stand {fmt.datum(STICHTAG)}")
    print(f"  Readiness-Quote: {fmt.prozent(r.quote)} (Vormonat {fmt.prozent(vm.readiness.quote)}, "
          f"{fmt.pp(r.quote - vm.readiness.quote)}) = bereit / (alle − archivieren)")
    print(f"  inkl. „bereit nach Bereinigung“: {fmt.prozent(r.quote_inkl_bereinigung)}")
    print("  Trichter: " + " → ".join(f"{k} {fmt.zahl(v)}" for k, v in r.trichter.items()))
    print("  Status:   " + " · ".join(f"{k} {fmt.zahl(v)}" for k, v in r.zaehlung.items()))
    print("\nBlocker nach Regel:")
    for regel, n in r.blocker.regel.value_counts().items():
        print(f"  {regel}  {fmt.zahl(n):>4}")
    print(f"\nKunde = Lieferant: {len(r.kunde_lieferant)} Paare "
          f"({(r.kunde_lieferant.status.str.startswith('verknüpft')).sum()} verknüpft)")
    print("\nAktive Partner der Suite:")
    aktiv = r.status[r.status.nr.str.match(r"^(K\d{3}|100[1-6]00)$")]
    for z in aktiv.itertuples():
        print(f"  {z.schluessel:<12} {z.name[:40]:<40} {z.status:<24} {z.blocker or z.fehler}")
    return 0


def befehl_verlauf(args: argparse.Namespace) -> int:
    from src.analyse import verlauf

    v = verlauf(_daten(), args.objekt)
    print(f"Qualitätsverlauf · {args.objekt} · 12 Monatsstände aus dem Änderungsprotokoll rekonstruiert")
    print(f"  {'Monatsende':<11} {'DAMA':>8} {'Readiness':>10} {'Cluster':>8} {'Blocker':>8} {'Archiv':>7} "
          f"{'Sätze':>6}")
    for _, z in v.kennzahlen.iterrows():
        print(f"  {fmt.datum(z['monatsende']):<11} {fmt.prozent(z['DAMA-Gesamtscore']):>8} "
              f"{fmt.prozent(z['Migration-Readiness-Quote']):>10} {z['Offene Dublettencluster']:>8} "
              f"{z['Blocker-Befunde']:>8} {z['Archivierungskandidaten']:>7} {z['Sätze']:>6}")
    print("\nVerursacher (Summe neue / erledigte Befunde im Zeitraum):")
    s = v.verursacher.groupby("benutzer")[["neue_befunde", "erledigte_befunde"]].sum()
    for b, z in s.sort_values("erledigte_befunde", ascending=False).iterrows():
        print(f"  {b:<22} neu {z.neue_befunde:>4} · erledigt {z.erledigte_befunde:>4}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_agent.py", description="DataGuard-AI – Stammdaten-Copilot (offline)")
    befehle = p.add_subparsers(dest="befehl", required=True)
    d = befehle.add_parser("daten", help="synthetische Stammdaten und Wahrheitsdatei erzeugen")
    d.add_argument("--seed", type=int, default=SEED)
    d.add_argument("--ordner", default=None, help="Zielordner (Standard: data/sample bzw. data/pruefseed)")
    d.set_defaults(fn=befehl_daten)
    befehle.add_parser("diagnose", help="Umgebung und Suite-Kontrollwerte prüfen").set_defaults(fn=befehl_diagnose)
    for name, fn, hilfe in (("pruefen", befehl_pruefen, "Regelwerk und DAMA-Scores"),
                            ("readiness", befehl_readiness, "Migration Readiness (CVI)"),
                            ("verlauf", befehl_verlauf, "Qualitätsverlauf über 12 Monatsstände")):
        x = befehle.add_parser(name, help=hilfe)
        x.add_argument("--objekt", default="Alle", choices=["Alle", "DEBI", "KRED"])
        x.set_defaults(fn=fn)
    u = befehle.add_parser("dubletten", help="Dublettenerkennung mit Messung")
    u.add_argument("--top", type=int, default=10)
    u.add_argument("--pruefseed", action="store_true", help=f"Prüf-Seed {PRUEF_SEED} erzeugen, falls nicht vorhanden")
    u.set_defaults(fn=befehl_dubletten)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
