"""Golden Record: Vorschlag je Dublettencluster mit festen Überlebensregeln (Survivorship) – Entscheidung nur durch
einen Menschen mit Namen.

Überlebensregeln je Feld (in dieser Reihenfolge, erste Regel mit eindeutigem Ergebnis entscheidet):
1. **gültig vor ungültig** (Formal-/Prüfziffernprüfung des Feldes),
2. **vollständig vor leer**,
3. **Quelle mit Buchungen vor ungebuchter Quelle** (jüngste letzte Buchung zuerst),
4. **jüngste Änderung** (Änderungsprotokoll, sonst Anlagedatum),
5. bei Gleichstand die kleinste Nummer.

Zielnummer (überlebender Satz): aktiver Suite-Partner > Satz mit jüngster Buchung > Satz ohne Löschvormerkung >
ältestes Anlagedatum > kleinste Nummer. Ergebnis einer Übernahme ist eine **Zuordnungsliste alt → neu**; die
Quelldaten werden nie verändert (kein automatisches Zusammenführen, Löschen oder Ändern).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src import pruefziffern as pz
from src.customizing import ZAHLUNGSBEDINGUNGEN, erwartete_region
from src.regeln import INJEKTIONSMUSTER
from src.suite import aktive_schluessel

FELDER: tuple[tuple[str, str], ...] = (
    ("name1", "Name"), ("strasse", "Straße"), ("hausnr", "Hausnummer"), ("plz", "PLZ"), ("ort", "Ort"),
    ("land", "Land"), ("sprache", "Sprache"), ("telefon", "Telefon"), ("email", "E-Mail"), ("ust_id", "USt-IdNr."),
    ("iban", "IBAN"), ("swift", "BIC"), ("zterm", "Zahlungsbedingung"), ("bzirk", "Vertriebsgebiet"),
)
ENTSCHEIDUNGEN = ("übernehmen", "ablehnen", "zurückstellen")


def feld_gueltig(feld: str, z) -> bool:
    w = str(getattr(z, feld) or "")
    if not w:
        return False
    pruefung = {
        "name1": lambda: not INJEKTIONSMUSTER.search(w),
        "plz": lambda: pz.plz_gueltig(w, z.land) is not False,
        "land": lambda: w in pz.LAENDER,
        "sprache": lambda: w in pz.SPRACHEN,
        "telefon": lambda: pz.telefon_gueltig(w),
        "email": lambda: pz.email_gueltig(w),
        "ust_id": lambda: pz.ust_format_gueltig(w) and (not w.startswith("DE") or pz.ust_id_de_gueltig(w)),
        "iban": lambda: pz.iban_gueltig(w),
        "swift": lambda: pz.bic_gueltig(w),
        "zterm": lambda: w in ZAHLUNGSBEDINGUNGEN,
        "bzirk": lambda: erwartete_region(z.land, z.plz) in (None, w),
    }.get(feld)
    return pruefung() if pruefung else True


@dataclass
class Feldvorschlag:
    feld: str
    bezeichnung: str
    wert: str  # Anzeige (IBAN maskiert)
    quelle: str  # Nummer des Satzes, aus dem der Wert stammt
    regel: str  # entscheidende Überlebensregel
    alternativen: list[str] = field(default_factory=list)


@dataclass
class Vorschlag:
    cluster_id: str
    objekt: str
    nummern: list[str]
    ziel: str
    ziel_begruendung: str
    felder: list[Feldvorschlag]
    max_score: float

    @property
    def zuordnung(self) -> list[tuple[str, str]]:
        return [(n, self.ziel) for n in self.nummern if n != self.ziel]


def _anzeige(feld: str, wert: str) -> str:
    return pz.iban_maskieren(wert) if feld == "iban" else wert


def cluster_id(objekt: str, nummern: list[str]) -> str:
    return f"{objekt}-{'-'.join(sorted(nummern))}"


def vorschlag(objekt: str, nummern: list[str], df: pd.DataFrame, letzte_aenderung: dict[str, date],
              max_score: float = 0.0) -> Vorschlag:
    z = {s.nr: s for s in df[(df.objekt == objekt) & (df.nr.isin(nummern))].itertuples(index=False)}
    aktiv = aktive_schluessel()
    leer = date(1900, 1, 1)

    def rang_ziel(n: str):
        s = z[n]
        return (f"{objekt}:{n}" not in aktiv, -(s.letzte_buchung or leer).toordinal(), s.loevm == "X",
                s.erdat.toordinal(), n)

    ziel = sorted(nummern, key=rang_ziel)[0]
    zs = z[ziel]
    if f"{objekt}:{ziel}" in aktiv:
        begr = "aktiver Partner der Suite (Umsatz/Rechnungen in den anderen Agenten)"
    elif zs.letzte_buchung:
        begr = f"jüngste Buchung ({zs.letzte_buchung:%d.%m.%Y})"
    else:
        begr = "ohne Löschvormerkung, ältestes Anlagedatum" if zs.loevm != "X" else "ältestes Anlagedatum"
    felder = []
    for feld, bez in FELDER:
        kandidaten = []
        for n in nummern:
            s = z[n]
            wert = str(getattr(s, feld) or "")
            # Regel 1 bewertet nur vorhandene Werte: gültig vor (ungültig oder leer); Regel 2 dann vorhanden vor leer
            kandidaten.append((not feld_gueltig(feld, s), not wert, -(s.letzte_buchung or leer).toordinal(),
                               -letzte_aenderung.get(f"{objekt}:{n}", s.erdat).toordinal(), n, wert))
        kandidaten.sort()
        sieger = kandidaten[0]
        if all(not k[5] for k in kandidaten):
            felder.append(Feldvorschlag(feld, bez, "", "–", "kein Satz hat einen Wert"))
            continue
        zweiter = kandidaten[1] if len(kandidaten) > 1 else None
        if zweiter is None or sieger[5] == zweiter[5]:
            regel = "gleicher Wert in allen Quellen" if len({k[5] for k in kandidaten}) == 1 else "gleicher Wert"
        elif sieger[0] != zweiter[0]:
            regel = "vollständig vor leer" if not zweiter[5] else "gültig vor ungültig"
        elif sieger[1] != zweiter[1]:
            regel = "vollständig vor leer"
        elif sieger[2] != zweiter[2]:
            regel = "Quelle mit Buchungen vor ungebuchter Quelle"
        elif sieger[3] != zweiter[3]:
            regel = "jüngste Änderung"
        else:
            regel = "kleinste Nummer"
        alternativen = sorted({_anzeige(feld, k[5]) for k in kandidaten if k[5] and k[5] != sieger[5]})
        felder.append(Feldvorschlag(feld, bez, _anzeige(feld, sieger[5]), sieger[4], regel, alternativen))
    return Vorschlag(cluster_id(objekt, nummern), objekt, sorted(nummern), ziel, begr, felder, max_score)


def alle_vorschlaege(cluster: dict[str, list[list[str]]], df: pd.DataFrame, letzte_aenderung: dict[str, date],
                     paare=None) -> list[Vorschlag]:
    scores: dict[tuple[str, str], float] = {}
    for p in paare or []:
        for n in (p.a, p.b):
            scores[(p.objekt, n)] = max(scores.get((p.objekt, n), 0.0), p.score)
    aktiv = aktive_schluessel()
    geloescht = set(df.schluessel[df.loevm == "X"]) if "schluessel" in df else set()
    v, rang = [], {}
    for objekt, liste in cluster.items():
        for c in liste:
            x = vorschlag(objekt, c, df, letzte_aenderung, max(scores.get((objekt, n), 0.0) for n in c))
            schl = [f"{objekt}:{n}" for n in c]
            # Reihenfolge der Bearbeitung: aktive Suite-Partner → offene Cluster (≥ 2 Sätze ohne Löschvormerkung)
            # → Score absteigend → Cluster-ID
            rang[x.cluster_id] = (not any(s in aktiv for s in schl), sum(s not in geloescht for s in schl) < 2,
                                  -x.max_score, x.cluster_id)
            v.append(x)
    return sorted(v, key=lambda x: rang[x.cluster_id])


# ── Entscheidungen (Human-in-the-Loop) ─────────────────────────────────────────────────────────────────────────


@dataclass
class Entscheidung:
    cluster_id: str
    entscheidung: str  # übernehmen | ablehnen | zurückstellen
    entscheider: str
    zeitpunkt: str
    begruendung: str = ""
    ziel: str = ""
    zuordnung: list[tuple[str, str]] = field(default_factory=list)


class EntscheidungOhneName(ValueError):
    pass


def entscheide(v: Vorschlag, entscheidung: str, entscheider: str, begruendung: str = "",
               zeitpunkt: datetime | None = None) -> Entscheidung:
    """Namentliche Entscheidung; nur „übernehmen“ erzeugt eine Zuordnungsliste. Quelldaten bleiben unverändert."""
    name = (entscheider or "").strip()
    if len(name) < 3 or " " not in name:
        raise EntscheidungOhneName("Entscheidung nur mit Vor- und Nachnamen der verantwortlichen Person.")
    if entscheidung not in ENTSCHEIDUNGEN:
        raise ValueError(f"Unbekannte Entscheidung: {entscheidung}")
    zp = (zeitpunkt or datetime.now()).isoformat(timespec="seconds")
    return Entscheidung(v.cluster_id, entscheidung, name, zp, begruendung.strip(), v.ziel,
                        v.zuordnung if entscheidung == "übernehmen" else [])


def zuordnungsliste(entscheidungen: list[Entscheidung]) -> pd.DataFrame:
    """Mapping alt → neu für das Migrationsprojekt (nur übernommene Cluster, jüngste Entscheidung je Cluster)."""
    juengste: dict[str, Entscheidung] = {}
    for e in entscheidungen:
        juengste[e.cluster_id] = e
    zeilen = [(e.cluster_id, alt, neu, e.entscheider, e.zeitpunkt, e.begruendung)
              for e in juengste.values() if e.entscheidung == "übernehmen" for alt, neu in e.zuordnung]
    return pd.DataFrame(zeilen, columns=["cluster", "alt", "neu", "entscheider", "zeitpunkt", "begruendung"])


def speichere(entscheidungen: list[Entscheidung], pfad: Path) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps([asdict(e) for e in entscheidungen], ensure_ascii=False, indent=1), encoding="utf-8")


def lade(pfad: Path) -> list[Entscheidung]:
    if not pfad.exists():
        return []
    return [Entscheidung(**{**e, "zuordnung": [tuple(x) for x in e["zuordnung"]]})
            for e in json.loads(pfad.read_text(encoding="utf-8"))]
