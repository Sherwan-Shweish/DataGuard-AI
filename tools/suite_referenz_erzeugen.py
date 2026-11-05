"""Gemeinsames Zahlenwerk der RheinMain Controlling-Suite für DataGuard-AI erzeugen – einmalig, reproduzierbar.

DataGuard-AI liest zur Laufzeit nur ``src/suite_referenz.json`` – nie die anderen Agenten. Diese Datei entsteht in
drei Schritten; jeder Schritt läuft **im Projektordner des jeweiligen Referenzagenten mit dessen Umgebung**:

    T=/pfad/zu/DataGuard-AI/tools/suite_referenz_erzeugen.py
    Z=/pfad/zu/DataGuard-AI/src/suite_referenz.json
    cd /pfad/zu/VarianceAI   && uv run python $T varianceai $Z
    cd /pfad/zu/FlowAudit-AI && uv run python $T flowaudit  $Z
    cd /pfad/zu/ControllAI   && uv run python $T controllai $Z

1. ``varianceai`` (führendes Finanzsystem): 12 aktive Debitoren K101–K304 mit Name, Vertriebsregion, Umsatz 2025
   (Cent) und Datum der letzten Faktura – gesamt und je Monatsende Oktober 2025 bis September 2026. Grundlage ist das
   Universal Journal (Ist, Erlöskonto 800000) ohne die Demonstrationsdublette 9099999999, wie in der VarianceAI-
   Datenprüfung. Zusätzlich Kostenstellen, Produktgruppen und Regionen (nur Bezeichnungen).
2. ``flowaudit``: 6 aktive Kreditoren 100100–100600 mit Name, Anschrift, USt-IdNr., E-Mail, BLZ/Konto/BIC,
   Zahlungsbedingung, IBAN (Berechnung wie FlowAudit ``_iban``) und den protokollierten Bankänderungen – mit
   absolutem Datum, bezogen auf den festen Demo-Stichtag von FlowAudit (``data/invoices/manifest.json``,
   28.10.2026). Eine Suite, eine Zeitachse: Änderungen nach dem 30.09.2026 sieht DataGuard noch nicht.
3. ``controllai``: Abgleich Umsatz 2025 je Kunde (Cent) mit Schritt 1 – Abbruch bei Abweichung; zusätzlich die
   Branche je Kunde (ControllAI-Stammdaten) und HK 2025 als Kontrollwert.

Die Referenzagenten werden dabei nur gelesen und nicht verändert.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

STICHTAG = date(2026, 9, 30)
MONATSENDEN = [
    "2025-10-31", "2025-11-30", "2025-12-31", "2026-01-31", "2026-02-28", "2026-03-31",
    "2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30",
]
DUBLETTE_VARIANCEAI = "9099999999"


def _lade(ziel: Path) -> dict:
    if ziel.exists():
        return json.loads(ziel.read_text(encoding="utf-8"))
    return {"stichtag": STICHTAG.isoformat(), "quellen": {}}


def _schreibe(ziel: Path, daten: dict) -> None:
    ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def schritt_varianceai(ziel: Path) -> None:
    from src.seed_data import KONTO_ERLOES, KONTO_HK, erzeuge_daten  # Modul aus VarianceAI

    d = erzeuge_daten(seed=42)
    a = d.acdoca[(d.acdoca.belnr != DUBLETTE_VARIANCEAI) & (d.acdoca.version == "IST")].copy()
    a = a[a.budat <= STICHTAG.isoformat()]
    erl = a[a.racct == KONTO_ERLOES]
    hk = a[a.racct == KONTO_HK]
    debitoren = []
    for r in d.kunden.itertuples():
        e = erl[erl.kunnr == r.kunnr]
        je_monat = {}
        for m in MONATSENDEN:
            bis = e[e.budat <= m]
            je_monat[m] = str(bis.budat.max()) if len(bis) else None
        debitoren.append({
            "kunnr": r.kunnr,
            "name": r.name,
            "region": r.regio,
            "umsatz_2025_cent": int(-e[e.gjahr == 2025].hsl_cent.sum()),
            "hk_2025_cent": int(hk[(hk.kunnr == r.kunnr) & (hk.gjahr == 2025)].hsl_cent.sum()),
            "letzte_faktura": str(e.budat.max()),
            "letzte_faktura_je_monatsende": je_monat,
        })
    daten = _lade(ziel)
    daten["firma"] = {"name": "RheinMain Industrietechnik GmbH", "strasse": "Mainzer Straße 120", "plz": "65189",
                      "ort": "Wiesbaden", "buchungskreis": "1000"}
    daten["debitoren"] = debitoren
    daten["kostenstellen"] = [{"kostenstelle": r.rcntr, "bezeichnung": r.bezeichnung}
                              for r in d.kostenstellen.itertuples()]
    daten["produktgruppen"] = [{"produktgruppe": r.prodh, "bezeichnung": r.bezeichnung}
                               for r in d.produktgruppen.itertuples()]
    daten["regionen"] = [{"region": r.regio, "bezeichnung": r.bezeichnung} for r in d.regionen.itertuples()]
    daten["quellen"]["varianceai"] = ("VarianceAI 1.2, src/seed_data.erzeuge_daten(seed=42); Ist, Erlöskonto 800000, "
                                      f"ohne Demonstrationsdublette {DUBLETTE_VARIANCEAI}, Buchungsdatum ≤ {STICHTAG}")
    summe = sum(x["umsatz_2025_cent"] for x in debitoren)
    daten["kontrollwerte"] = {"umsatz_2025_summe_cent": summe}
    _schreibe(ziel, daten)
    print(f"VarianceAI: {len(debitoren)} Debitoren, Umsatz 2025 = {summe / 100:,.2f} €")


def schritt_flowaudit(ziel: Path) -> None:
    from src.einvoice_parser import ust_id_de_gueltig  # Modul aus FlowAudit-AI

    from src.seed_data import BANKAENDERUNGEN, KAEUFER, LIEFERANTEN, _iban  # Modul aus FlowAudit-AI

    kreditoren = []
    for f in LIEFERANTEN.values():
        if not ust_id_de_gueltig(f.ust_id):
            raise SystemExit(f"Abbruch: USt-IdNr. {f.ust_id} von {f.lifnr} ist in FlowAudit ungültig.")
        kreditoren.append({
            "lifnr": f.lifnr, "name": f.name, "strasse": f.strasse, "plz": f.plz, "ort": f.ort, "land": "DE",
            "ust_id": f.ust_id, "email": f.email, "blz": f.blz, "konto": f.konto, "bic": f.swift,
            "zterm": f.zterm, "iban": _iban(f.blz, f.konto),
        })
    daten = _lade(ziel)
    daten["kreditoren"] = kreditoren
    daten["eigene_ust_id"] = KAEUFER.ust_id
    from datetime import timedelta

    fa_stichtag = date.fromisoformat(
        json.loads(Path("data/invoices/manifest.json").read_text(encoding="utf-8"))["referenzdatum"])
    daten["flowaudit_stichtag"] = fa_stichtag.isoformat()
    daten["bankaenderungen"] = [
        {"lifnr": lifnr, "datum": (fa_stichtag - timedelta(days=tage)).isoformat(), "benutzer": benutzer,
         "alte_iban_endung": alt}
        for lifnr, tage, benutzer, alt, _ in BANKAENDERUNGEN
    ]
    daten["quellen"]["flowaudit"] = ("FlowAudit-AI 1.2.1, src/seed_data.LIEFERANTEN, KAEUFER, BANKAENDERUNGEN; "
                                     "IBAN mit src/seed_data._iban; "
                                     "USt-IdNr. mit src/einvoice_parser.ust_id_de_gueltig")
    _schreibe(ziel, daten)
    print(f"FlowAudit-AI: {len(kreditoren)} Kreditoren, Bankänderungen {len(daten['bankaenderungen'])}")


def schritt_controllai(ziel: Path) -> None:
    import tempfile

    import pandas as pd
    from src.strategie import cent  # Modul aus ControllAI

    from src.seed_data import erzeuge_alles  # Modul aus ControllAI

    daten = _lade(ziel)
    if "debitoren" not in daten:
        raise SystemExit("Abbruch: zuerst den Schritt 'varianceai' ausführen.")
    with tempfile.TemporaryDirectory() as tmp:
        ergebnis = erzeuge_alles(tmp, seed=42)
        import sqlite3

        with sqlite3.connect(ergebnis.db_path) as con:
            tx = pd.read_sql("SELECT * FROM umsatz_transaktionen", con)
            kunden = pd.read_sql("SELECT * FROM kunden", con)
    tx = tx[(tx.geschaeftsjahr == 2025) & (tx.ist_ausreisser == 0)]
    tx = tx.assign(u=tx.umsatz_eur.map(cent), h=tx.variable_kosten_eur.map(cent))
    je_kunde = tx.groupby("kunden_nr")[["u", "h"]].sum()
    abweichungen = []
    for k in daten["debitoren"]:
        u = int(je_kunde.loc[k["kunnr"], "u"]) if k["kunnr"] in je_kunde.index else 0
        h = int(je_kunde.loc[k["kunnr"], "h"]) if k["kunnr"] in je_kunde.index else 0
        if u != k["umsatz_2025_cent"] or h != k["hk_2025_cent"]:
            abweichungen.append((k["kunnr"], k["umsatz_2025_cent"], u, k["hk_2025_cent"], h))
    if abweichungen:
        zeilen = "\n".join(f"  {n}: Umsatz VarianceAI {a} ≠ ControllAI {b} · HK {c} ≠ {d}"
                           for n, a, b, c, d in abweichungen)
        raise SystemExit("Abbruch: Umsatz/HK 2025 je Kunde nicht centgleich mit VarianceAI:\n" + zeilen)
    branche = dict(zip(kunden.kunden_nr, kunden.branche, strict=True))
    for k in daten["debitoren"]:
        k["branche"] = branche[k["kunnr"]]
    daten["abgleich_controllai"] = {
        "ergebnis": "centgleich",
        "kunden": len(daten["debitoren"]),
        "umsatz_2025_cent": int(je_kunde.u.sum()),
        "hk_2025_cent": int(je_kunde.h.sum()),
        "differenz_cent": 0,
    }
    daten["quellen"]["controllai"] = ("ControllAI 2.2.1, src/seed_data.erzeuge_alles(seed=42), Tabelle "
                                      "umsatz_transaktionen 2025 ohne Ausreißer; Branche aus Tabelle kunden")
    _schreibe(ziel, daten)
    print(f"ControllAI: Umsatz und HK 2025 je Kunde centgleich ({len(daten['debitoren'])} Kunden), Branchen übernommen")


SCHRITTE = {"varianceai": schritt_varianceai, "flowaudit": schritt_flowaudit, "controllai": schritt_controllai}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in SCHRITTE:
        raise SystemExit("Aufruf: python suite_referenz_erzeugen.py varianceai|flowaudit|controllai <ziel.json>")
    SCHRITTE[sys.argv[1]](Path(sys.argv[2]).resolve())
