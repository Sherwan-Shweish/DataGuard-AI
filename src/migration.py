"""Migration Readiness für die Customer-Vendor-Integration (CVI) nach SAP S/4HANA.

In S/4HANA ist der Geschäftspartner (BP) führend; jeder Debitor und Kreditor muss über die CVI zu einem
Geschäftspartner werden (SAP Simplification Item „Business Partner Approach“; Stand prüfen). Dieses Modul bewertet
jeden Satz deterministisch:

* **archivieren** – keine Buchung seit mehr als 24 Monaten vor dem Stichtag, nie bebucht und älter als 24 Monate,
  Löschvormerkung oder gesperrt ohne offene Posten. Diese Sätze werden nicht migriert.
* **blockiert** – mindestens ein CVI-Blocker: Befund einer Regel mit ``cvi_blocker`` (z. B. Kontengruppe ohne
  BP-Gruppierung, Nummernkonflikt, Kunde = Lieferant ohne Verknüpfung, ungültige IBAN) oder ein Dublettencluster mit
  mindestens zwei zu migrierenden Sätzen (vor der CVI zusammenführen). Befunde der Eindeutigkeit zählen nur, wenn
  mindestens ein beteiligter Partner ebenfalls migriert wird.
* **bereit nach Bereinigung** – kein Blocker, aber Befunde mit Schweregrad „Fehler“ (Feldkorrektur genügt).
* **bereit** – höchstens Hinweise.

Readiness-Quote = bereit / (alle − archivieren). Zusätzlich ausgewiesen: Quote inkl. „bereit nach Bereinigung“.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import pruefziffern as pz
from src.customizing import BP_ROLLEN, KONTENGRUPPE, steuernummernkategorie
from src.regeln import REGEL, Pruefergebnis

STATUS = ("bereit", "bereit nach Bereinigung", "blockiert", "archivieren")

#: Pflichtangaben des Geschäftspartners (Auszug; Quelle: SAP-Dokumentation Business Partner/CVI – Stand prüfen,
#: im System über das CVI-Customizing und die Feldsteuerung der BP-Gruppierung verifizieren).
BP_PFLICHTFELDER: tuple[tuple[str, str, str], ...] = (
    ("Name", "BUT000-NAME_ORG1 ← KNA1/LFA1-NAME1", "beide"),
    ("Land", "ADRC-COUNTRY ← KNA1/LFA1-LAND1", "beide"),
    ("Anschrift (Straße, PLZ, Ort)", "ADRC-STREET/POST_CODE1/CITY1", "beide"),
    ("Sprache", "BUT000-BU_LANGU / ADRC-LANGU ← SPRAS", "beide"),
    ("BP-Gruppierung", "BUT000-BU_GROUP ← CVI-Zuordnung der Kontengruppe", "beide"),
    ("Abstimmkonto", "KNB1/LFB1-AKONT (Buchungskreisdaten der FI-Rolle)", "beide"),
    ("Steuernummernkategorie", "DFKKBPTAXNUM-TAXTYPE ← STCEG (z. B. DE0)", "beide"),
    ("Bankverbindung", "BUT0BK-IBAN ← LFBK", "KRED"),
)


@dataclass
class Readiness:
    status: pd.DataFrame  # schluessel, objekt, nr, name, status, blocker, fehler, gruende_archiv, bp_gruppierung
    quote: float  # bereit / (alle − archivieren), in %
    quote_inkl_bereinigung: float
    trichter: dict[str, int]
    zaehlung: dict[str, int]
    blocker: pd.DataFrame  # je Blocker-Grund: schluessel, regel, beschreibung
    kunde_lieferant: pd.DataFrame
    pflichtfelder: pd.DataFrame
    archiv: pd.DataFrame
    offene_cluster: list[list[str]]


def _archivgruende(z, grenze) -> list[str]:
    g = []
    if z.loevm == "X":
        g.append("Löschvormerkung")
    if z.letzte_buchung is not None and z.letzte_buchung < grenze:
        g.append(f"keine Buchung seit {z.letzte_buchung:%d.%m.%Y}")
    if z.letzte_buchung is None and z.erdat < grenze:
        g.append(f"nie bebucht, angelegt {z.erdat:%d.%m.%Y}")
    if z.sperr == "X" and z.op != "X":
        g.append("gesperrt ohne offene Posten")
    return g


def offene_cluster(ergebnis: Pruefergebnis, df: pd.DataFrame) -> list[list[str]]:
    """Dublettencluster (ab Prüfschwelle) mit mindestens zwei Sätzen ohne Löschvormerkung (Schlüssel)."""
    loevm = set(df.schluessel[df.loevm == "X"])
    offen = []
    for objekt, cluster in ergebnis.kontext.dubletten.cluster.items():
        for c in cluster:
            schluessel = [f"{objekt}:{n}" for n in c]
            if sum(s not in loevm for s in schluessel) >= 2:
                offen.append(schluessel)
    return offen


def bewerte(ergebnis: Pruefergebnis, df: pd.DataFrame, voll: bool = True) -> Readiness:
    """Status je Satz; ``voll=False`` lässt die Pflichtfeld-Matrix und Kunde=Lieferant-Liste aus (Monatsverlauf)."""
    k = ergebnis.kontext
    archiv = k.archiv
    zeilen = k.zeilen if k.zeilen else {z.schluessel: z for z in df.itertuples(index=False)}
    # Dublettencluster mit ≥ 2 zu migrierenden Sätzen → Blocker für alle migrierenden Mitglieder
    cluster_blocker: dict[str, str] = {}
    for objekt, cluster in k.dubletten.cluster.items():
        for c in cluster:
            schluessel = [f"{objekt}:{n}" for n in c]
            migrierend = [s for s in schluessel if s not in archiv]
            if len(migrierend) >= 2:
                for s in migrierend:
                    cluster_blocker[s] = "Dublettencluster " + ", ".join(c)
    blocker_zeilen, status_zeilen = [], []
    je_satz: dict[str, list] = {}
    for b in ergebnis.befunde[["schluessel", "regel", "partner"]].itertuples(index=False):
        je_satz.setdefault(b.schluessel, []).append(b)
    for s, z in zeilen.items():
        kg = KONTENGRUPPE.get((z.objekt, z.ktogr))
        bp = kg.bp_gruppierung if kg else None
        if s in archiv:
            gruende = "; ".join(_archivgruende(z, k.archivgrenze)) if voll else ""
            status_zeilen.append((s, z.objekt, z.nr, z.name1, "archivieren", "", "", gruende, bp or ""))
            continue
        blocker, fehler = [], []
        if s in je_satz:
            for b in je_satz[s]:
                regel = REGEL[b.regel]
                if regel.dimension == "Eindeutigkeit" and b.partner and all(p in archiv for p in b.partner):
                    continue  # Partner wird archiviert – kein Hindernis für die Migration dieses Satzes
                if regel.id == "E01":
                    continue  # über die Clusterlogik erfasst
                if regel.cvi_blocker:
                    blocker.append(regel.id)
                elif regel.schweregrad in ("Blocker", "Fehler"):
                    fehler.append(regel.id)
        if s in cluster_blocker:
            blocker.append("E01")
        for rid in blocker:
            text = cluster_blocker[s] if rid == "E01" else REGEL[rid].beschreibung
            blocker_zeilen.append((s, z.objekt, z.nr, z.name1, rid, text))
        status = "blockiert" if blocker else "bereit nach Bereinigung" if fehler else "bereit"
        status_zeilen.append((s, z.objekt, z.nr, z.name1, status, ", ".join(sorted(set(blocker))),
                              ", ".join(sorted(set(fehler))), "", bp or ""))
    st = pd.DataFrame(status_zeilen, columns=["schluessel", "objekt", "nr", "name", "status", "blocker", "fehler",
                                              "gruende_archiv", "bp_gruppierung"], dtype=object)
    zaehlung = dict.fromkeys(STATUS, 0)
    for z in status_zeilen:
        zaehlung[z[4]] += 1
    basis = len(st) - zaehlung["archivieren"]
    quote = round(100 * zaehlung["bereit"] / basis, 2) if basis else 0.0
    quote2 = round(100 * (zaehlung["bereit"] + zaehlung["bereit nach Bereinigung"]) / basis, 2) if basis else 0.0
    trichter = {"alle Sätze": len(st), "nicht archivieren": basis, "ohne Blocker": basis - zaehlung["blockiert"],
                "bereit": zaehlung["bereit"]}
    return Readiness(st, quote, quote2, trichter, zaehlung,
                     pd.DataFrame(blocker_zeilen, columns=["schluessel", "objekt", "nr", "name", "regel", "grund"],
                                  dtype=object),
                     kunde_lieferant(ergebnis, zeilen) if voll else pd.DataFrame(),
                     pflichtfeld_matrix(df, archiv) if voll else pd.DataFrame(),
                     st[st.status == "archivieren"][["schluessel", "objekt", "nr", "name", "gruende_archiv"]],
                     offene_cluster(ergebnis, df))


def kunde_lieferant(ergebnis: Pruefergebnis, zeilen: dict) -> pd.DataFrame:
    """Partner, die zugleich Kunde und Lieferant sind: verknüpft (ein BP, zwei Rollen) oder unverknüpft (Blocker)."""
    k = ergebnis.kontext
    z = []
    for deb, kred in k.verknuepfte_paare:
        if deb in k.archiv and kred in k.archiv:
            continue
        z.append((deb, kred, zeilen[deb].name1, "verknüpft – ein BP mit Rollen "
                  + " + ".join(BP_ROLLEN["DEBI"] + BP_ROLLEN["KRED"])))
    gesehen = set()
    for s, partner in k.kunde_lieferant.items():
        if not s.startswith("DEBI:"):
            continue
        for p in partner:
            if (s, p) not in gesehen:
                gesehen.add((s, p))
                z.append((s, p, zeilen[s].name1, "unverknüpft – würde zwei BP erzeugen (E05)"))
    return pd.DataFrame(z, columns=["debitor", "kreditor", "name", "status"])


def pflichtfeld_matrix(df: pd.DataFrame, archiv: set[str]) -> pd.DataFrame:
    """Abdeckung der BP-Pflichtangaben je Objekt (nur zu migrierende Sätze), in %."""
    m = df[~df.schluessel.isin(archiv)]
    pruef = {
        "Name": lambda z: bool(z.name1),
        "Land": lambda z: z.land in pz.LAENDER,
        "Anschrift (Straße, PLZ, Ort)": lambda z: bool(z.strasse and z.plz and z.ort)
        and pz.plz_gueltig(z.plz, z.land) is not False,
        "Sprache": lambda z: z.sprache in pz.SPRACHEN,
        "BP-Gruppierung": lambda z: bool(KONTENGRUPPE.get((z.objekt, z.ktogr))
                                         and KONTENGRUPPE[(z.objekt, z.ktogr)].bp_gruppierung),
        "Abstimmkonto": lambda z: bool(z.akont),
        "Steuernummernkategorie": lambda z: bool(z.ust_id and pz.ust_format_gueltig(z.ust_id)
                                                 and steuernummernkategorie(z.ust_id)),
        "Bankverbindung": lambda z: bool(z.iban and pz.iban_gueltig(z.iban)),
    }
    zeilen = []
    for feld, quelle, objekt in BP_PFLICHTFELDER:
        for o in ("DEBI", "KRED"):
            teil = m[m.objekt == o]
            if objekt != "beide" and objekt != o:
                continue
            n = len(teil)
            ok = sum(pruef[feld](z) for z in teil.itertuples(index=False))
            zeilen.append({"pflichtangabe": feld, "quelle": quelle, "objekt": o, "saetze": n, "erfuellt": ok,
                           "quote": round(100 * ok / n, 2) if n else 100.0})
    return pd.DataFrame(zeilen)
