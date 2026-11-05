"""Gesamtlauf: Prüfen → Dubletten → Golden Record → Readiness, Kennzahlen und Qualitätsverlauf.

Alle Kennzahlen entstehen aus Programmläufen derselben Engine – auch die zwölf Monatsstände des Verlaufs, die aus
dem Änderungsprotokoll (CDHDR/CDPOS) rekonstruiert und neu bewertet werden (keine hart codierten Werte).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import MONATSENDEN
from src.datenbasis import Stammdaten, letzte_aenderung
from src.dubletten import Rechenspeicher
from src.golden_record import Vorschlag, alle_vorschlaege
from src.migration import Readiness, bewerte
from src.regeln import Pruefergebnis, pruefe, verdichte

KENNZAHLEN = ("DAMA-Gesamtscore", "Migration-Readiness-Quote", "Offene Dublettencluster", "Blocker-Befunde",
              "Archivierungskandidaten")


@dataclass
class Lauf:
    stichtag: date
    objekt: str  # Alle | DEBI | KRED
    saetze: pd.DataFrame
    pruefung: Pruefergebnis
    readiness: Readiness
    vorschlaege: list[Vorschlag]

    @property
    def kennzahlen(self) -> dict[str, float]:
        return {
            "DAMA-Gesamtscore": self.pruefung.gesamtscore,
            "Migration-Readiness-Quote": self.readiness.quote,
            "Offene Dublettencluster": len(self.readiness.offene_cluster),
            "Blocker-Befunde": len(self.readiness.blocker),
            "Archivierungskandidaten": self.readiness.zaehlung["archivieren"],
        }

    @property
    def je_objekt(self) -> dict[str, dict[str, float]]:
        """Readiness- und Archivierungsquote getrennt nach Debitoren und Kreditoren (aus dem Status je Satz).

        Archivierungsquote = archivieren ÷ alle Sätze des Objekts × 100;
        Readiness-Quote = bereit ÷ (alle − archivieren) × 100 (wie gesamt)."""
        st = self.readiness.status
        ergebnis = {}
        for objekt in ("DEBI", "KRED"):
            s = st.status[st.objekt == objekt].tolist()
            n, archiv, bereit = len(s), s.count("archivieren"), s.count("bereit")
            if not n:
                continue
            basis = n - archiv
            ergebnis[objekt] = {"saetze": n, "archivieren": archiv, "nicht_archivieren": basis, "bereit": bereit,
                                "archivquote": round(100 * archiv / n, 1),
                                "readiness_quote": round(100 * bereit / basis, 2) if basis else 0.0}
        return ergebnis

    @property
    def archivquote(self) -> float:
        n = len(self.readiness.status)
        return round(100 * self.readiness.zaehlung["archivieren"] / n, 1) if n else 0.0


def filtern(df: pd.DataFrame, objekt: str) -> pd.DataFrame:
    return df if objekt == "Alle" else df[df.objekt == objekt].reset_index(drop=True)


def laufe(daten: Stammdaten, stichtag: date | None = None, objekt: str = "Alle", mit_vorschlaegen: bool = True,
          speicher: Rechenspeicher | None = None, voll: bool = True) -> Lauf:
    """Ein vollständiger, deterministischer Lauf zum Stichtag (None = aktueller Stand 30.09.2026).

    Kunde = Lieferant und Nummernkonflikte brauchen beide Objekte; deshalb wird immer der Gesamtbestand geprüft und
    erst danach nach Objekt verdichtet.
    """
    stand = daten.stand(stichtag)
    tag = stichtag or daten.stichtag
    pruefung = pruefe(stand, tag, daten.aenderungen, speicher=speicher)
    readiness = bewerte(pruefung, stand, voll=voll)
    vorschlaege = []
    if mit_vorschlaegen:
        vorschlaege = alle_vorschlaege(pruefung.kontext.dubletten.cluster, stand, letzte_aenderung(daten, tag),
                                       pruefung.kontext.dubletten.paare)
    if objekt != "Alle":
        pruefung, readiness, vorschlaege, stand = _nach_objekt(pruefung, readiness, vorschlaege, stand, objekt)
    return Lauf(tag, objekt, stand, pruefung, readiness, vorschlaege)


def _nach_objekt(p: Pruefergebnis, r: Readiness, v: list[Vorschlag], stand: pd.DataFrame, objekt: str):
    """Sicht auf ein Objekt: Befunde, Zähler, Scores und Readiness nur für dieses Objekt verdichtet."""
    zt, score, gesamt = verdichte(p.zaehler_objekt, objekt=objekt)
    teil = filtern(stand, objekt)
    p2 = replace(p, befunde=p.befunde[p.befunde.objekt == objekt].reset_index(drop=True), zaehler=zt,
                 dimension_score=score, gesamtscore=gesamt, saetze=len(teil))
    st = r.status[r.status.objekt == objekt].reset_index(drop=True)
    zaehlung = {s: int((st.status == s).sum()) for s in r.zaehlung}
    basis = len(st) - zaehlung["archivieren"]

    def nur(df: pd.DataFrame, spalte: str = "objekt") -> pd.DataFrame:
        return df[df[spalte] == objekt].reset_index(drop=True) if len(df) else df

    kl = r.kunde_lieferant
    r2 = replace(
        r, status=st, zaehlung=zaehlung,
        quote=round(100 * zaehlung["bereit"] / basis, 2) if basis else 0.0,
        quote_inkl_bereinigung=round(100 * (zaehlung["bereit"] + zaehlung["bereit nach Bereinigung"]) / basis, 2)
        if basis else 0.0,
        trichter={"alle Sätze": len(st), "nicht archivieren": basis, "ohne Blocker": basis - zaehlung["blockiert"],
                  "bereit": zaehlung["bereit"]},
        blocker=nur(r.blocker), pflichtfelder=nur(r.pflichtfelder), archiv=nur(r.archiv),
        kunde_lieferant=kl,  # Paare betreffen immer beide Objekte
        offene_cluster=[c for c in r.offene_cluster if c[0].startswith(objekt)],
    )
    return p2, r2, [x for x in v if x.objekt == objekt], teil


# ── Qualitätsverlauf ───────────────────────────────────────────────────────────────────────────────────────────


@dataclass
class Verlauf:
    kennzahlen: pd.DataFrame  # je Monatsende: Kennzahlen, Dimensionsscores, Anzahl Sätze/Befunde
    bewegungen: pd.DataFrame  # je Monat: neue und erledigte Befunde
    verursacher: pd.DataFrame  # je Monat und Benutzer: neue/erledigte Befunde (Änderung/Anlage im Monat)
    zerlegung: pd.DataFrame  # je Monat und Ursache: Beitrag zur Veränderung der Readiness-Quote in Pp
    sekunden: float = 0.0


URSACHEN = ("bereinigt", "neue Blocker durch Neuanlagen", "Neuanlagen bereit", "verschlechtert durch Änderung",
            "Alterung/Zeitablauf")


def verlauf(daten: Stammdaten, objekt: str = "Alle") -> Verlauf:
    """Zwölf Monatsstände Oktober 2025 – September 2026, je Stand vollständige Neubewertung.

    Inkrementell: ein gemeinsamer Rechenspeicher für die zwölf Stände – unveränderte Sätze und Paare werden nur
    einmal normalisiert, bewertet und geprüft; der Monatsstand selbst wird vektorisiert rekonstruiert.

    Zerlegung der Readiness-Quote q = B/N (B bereit, N = alle − archivieren) je Satz i:
    Beitrag c_i = (Δb_i − q₀·Δn_i) / N₁ mit b = 1 für „bereit“, n = 1 für „nicht archivieren“. Σ c_i = q₁ − q₀ exakt.
    Zuordnung: im Monat angelegt → „neue Blocker durch Neuanlagen“ (nicht bereit) bzw. „Neuanlagen bereit“, je
    Anlagebenutzer; bestehende Sätze mit Änderung im Monat → „bereinigt“ (c > 0) bzw. „verschlechtert durch Änderung“
    (c < 0), je Änderungsbenutzer; ohne Änderung → „Alterung/Zeitablauf“.
    """
    import gc
    import time

    from src import normalisierung, pruefziffern

    normalisierung.memo_leeren()  # Kaltstart: keine Zwischenergebnisse früherer Berechnungen
    pruefziffern.memo_leeren()
    start = time.perf_counter()
    gc_an = gc.isenabled()
    gc.disable()  # viele kurzlebige Objekte, keine Zyklen – Speicherbereinigung erst am Ende
    try:
        return _verlauf(daten, objekt, start)
    finally:
        if gc_an:
            gc.enable()


def _verlauf(daten: Stammdaten, objekt: str, start: float) -> Verlauf:
    import time

    speicher = Rechenspeicher()
    speicher.schlank = True  # Dubletten inkrementell, nur Paare ab Prüfschwelle (für Kennzahlen ausreichend)
    zeilen, bew, urs, zerl = [], [], [], []
    vorher: set[tuple[str, str]] | None = None
    vorher_status: dict[str, str] = {}
    vorher_tag, q0 = None, 0.0
    a = daten.aenderungen
    a_schl, a_datum, a_benutzer = a.schluessel.tolist(), a.datum.tolist(), a.benutzer.tolist()
    anleger = dict(zip(daten.saetze.schluessel, daten.saetze.ernam, strict=True))
    anlage = dict(zip(daten.saetze.schluessel, daten.saetze.erdat, strict=True))
    for tag in MONATSENDEN:
        lauf = laufe(daten, tag, objekt, mit_vorschlaegen=False, speicher=speicher, voll=False)
        p, r = lauf.pruefung, lauf.readiness
        zeilen.append({"monatsende": tag, **lauf.kennzahlen, **{f"Score {d}": s for d, s in p.dimension_score.items()},
                       "Sätze": p.saetze, "Befunde": len(p.befunde)})
        aktuell = set(zip(p.befunde.regel, p.befunde.schluessel, strict=True))
        status = dict(zip(r.status.schluessel, r.status.status, strict=True))
        if vorher is not None:
            neu, erledigt = aktuell - vorher, vorher - aktuell
            bew.append({"monatsende": tag, "neu": len(neu), "erledigt": len(erledigt)})
            wer = {s: b for s, d, b in zip(a_schl, a_datum, a_benutzer, strict=True) if vorher_tag < d <= tag}
            zaehl: dict[str, list[int]] = {}
            for menge, idx in ((neu, 0), (erledigt, 1)):
                for _, s in menge:
                    zaehl.setdefault(wer.get(s, "Alterung/Zeitablauf"), [0, 0])[idx] += 1
            for benutzer in sorted(zaehl):
                urs.append({"monatsende": tag, "benutzer": benutzer, "neue_befunde": zaehl[benutzer][0],
                            "erledigte_befunde": zaehl[benutzer][1]})
            n1 = r.trichter["nicht archivieren"]
            beitrag: dict[tuple[str, str], float] = {}
            for s in set(status) | set(vorher_status):
                s0, s1 = vorher_status.get(s), status.get(s)
                db = (s1 == "bereit") - (s0 == "bereit")
                dn = (s1 not in (None, "archivieren")) - (s0 not in (None, "archivieren"))
                if db == 0 and dn == 0:
                    continue
                c = 100 * (db - q0 / 100 * dn) / n1 if n1 else 0.0
                if s0 is None and anlage.get(s, tag) > vorher_tag:
                    ursache = "Neuanlagen bereit" if s1 == "bereit" else "neue Blocker durch Neuanlagen"
                    benutzer = anleger.get(s, "")
                elif s in wer:
                    ursache = "bereinigt" if c > 0 else "verschlechtert durch Änderung"
                    benutzer = wer[s]
                else:
                    ursache, benutzer = "Alterung/Zeitablauf", ""
                beitrag[(ursache, benutzer)] = beitrag.get((ursache, benutzer), 0.0) + c
            for (ursache, benutzer), c in sorted(beitrag.items()):
                zerl.append({"monatsende": tag, "ursache": ursache, "benutzer": benutzer, "beitrag_pp": c})
        basis = r.trichter["nicht archivieren"]
        vorher, vorher_status, vorher_tag = aktuell, status, tag
        q0 = 100 * r.zaehlung["bereit"] / basis if basis else 0.0  # ungerundet – Zerlegung summiert exakt
    return Verlauf(pd.DataFrame(zeilen), pd.DataFrame(bew), pd.DataFrame(urs),
                   pd.DataFrame(zerl, columns=["monatsende", "ursache", "benutzer", "beitrag_pp"]),
                   round(time.perf_counter() - start, 3))


# ── zwischengespeicherte Einstiege (Oberfläche, Kommandozeile) ─────────────────────────────────────────────────

from src.zwischenspeicher import nach_dateistand  # noqa: E402


@nach_dateistand
def daten_geladen(db: Path) -> Stammdaten:
    from src.datenbasis import lade

    return lade(db)


@nach_dateistand
def lauf_gespeichert(db: Path, objekt: str = "Alle", stichtag: str = "") -> Lauf:
    """Lauf zum Stichtag (ISO-Datum, leer = aktueller Stand) – Cache nach Funktion und Dateistand der Datenbank."""
    return laufe(daten_geladen(db), date.fromisoformat(stichtag) if stichtag else None, objekt,
                 mit_vorschlaegen=not stichtag)


@nach_dateistand
def verlauf_gespeichert(db: Path, objekt: str = "Alle") -> Verlauf:
    return verlauf(daten_geladen(db), objekt)
