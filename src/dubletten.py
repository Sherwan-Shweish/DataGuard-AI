"""Dublettenerkennung für Debitoren und Kreditoren – deterministisch, erklärbar, messbar.

Ablauf je Objekt (Debitoren und Kreditoren werden getrennt verglichen; Kunde = Lieferant prüft ``regeln.py``):

1. **Normalisierung** (``src/normalisierung.py``): Umlaute, Rechtsformen, Satzzeichen, „Straße/Str.“, Hausnummer.
2. **Blocking** – nur Kandidatenpaare vergleichen statt jeder mit jedem:
   Pass 1 gleiche PLZ · Pass 2 gleiche (gültige) IBAN oder gleiche USt-IdNr. · Pass 3 gleicher Namensanfang
   (5 Zeichen nach Normalisierung) im selben Land.
3. **Score 0–100** = 0,60 × Name (token_sort_ratio) + 0,25 × Straße + Hausnummer (ratio) + 0,15 × Ort
   (100 bei gleicher PLZ, sonst 0,6 × Ähnlichkeit des Ortsnamens) + Zuschläge für harte Merkmale
   (gleiche IBAN +15, gleiche USt-IdNr. +15, gleiche Telefonnummer +10) − 20, wenn beide eine *verschiedene*
   USt-IdNr. tragen (verschiedene Unternehmen). Begrenzung auf 0–100.
4. **Schwellen** (fest, auf Seed 42 festgelegt, auf dem Prüf-Seed nie angepasst): ≥ 90 „sehr wahrscheinlich“,
   75–89 „prüfen“, darunter keine Meldung.
5. **Cluster** über transitive Paare (Union-Find) ab der Prüfschwelle.

Jedes Paar trägt seine Merkmalswerte und Beiträge (Erklärbarkeit). Gemessen wird gegen die Wahrheitsdatei:
Precision, Recall, F1 auf Paarebene sowie der Blocking-Recall (Anteil echter Paare, die überhaupt verglichen wurden).
"""

from __future__ import annotations

from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from itertools import combinations

import pandas as pd
from rapidfuzz import fuzz

from src import pruefziffern as pz
from src.normalisierung import adresse_normal, name_normal, namensanfang, ort_normal

SCHWELLE_SEHR_WAHRSCHEINLICH = 90
SCHWELLE_PRUEFEN = 75
GEWICHT_NAME, GEWICHT_STRASSE, GEWICHT_ORT = 0.60, 0.25, 0.15
ZUSCHLAG_IBAN, ZUSCHLAG_UST, ZUSCHLAG_TELEFON = 15, 15, 10
ABSCHLAG_UST_VERSCHIEDEN = 20
PAESSE = ("PLZ", "IBAN/USt", "Namensanfang")


@dataclass
class Paar:
    objekt: str
    a: str  # Nummer
    b: str
    score: float
    stufe: str  # "sehr wahrscheinlich" | "prüfen" | "kein Treffer"
    merkmale: dict[str, float | bool | str]
    paesse: tuple[str, ...]


@dataclass
class Dublettenergebnis:
    paare: list[Paar]  # nur bewertete Kandidatenpaare
    cluster: dict[str, list[list[str]]]  # je Objekt, ab Prüfschwelle, sortiert
    vergleiche_ohne_blocking: dict[str, int]
    vergleiche_mit_blocking: dict[str, int]
    kandidaten_je_pass: dict[str, dict[str, int]] = field(default_factory=dict)

    def treffer(self, schwelle: float = SCHWELLE_PRUEFEN) -> list[Paar]:
        return [p for p in self.paare if p.score >= schwelle]

    def als_dataframe(self, schwelle: float = SCHWELLE_PRUEFEN) -> pd.DataFrame:
        zeilen = [{"objekt": p.objekt, "a": p.a, "b": p.b, "score": p.score, "stufe": p.stufe,
                   "paesse": ", ".join(p.paesse), **p.merkmale} for p in self.treffer(schwelle)]
        return pd.DataFrame(zeilen)


def stufe(score: float) -> str:
    if score >= SCHWELLE_SEHR_WAHRSCHEINLICH:
        return "sehr wahrscheinlich"
    if score >= SCHWELLE_PRUEFEN:
        return "prüfen"
    return "kein Treffer"


class Rechenspeicher:
    """Wiederverwendung innerhalb *einer* Berechnung (z. B. zwölf Monatsstände): unveränderte Sätze und Paare werden
    nicht erneut normalisiert, bewertet oder geprüft – das ist die inkrementelle Anwendung des Änderungsprotokolls.
    Der Speicher lebt nur so lange wie die Berechnung; er ist kein persistenter Ergebniscache."""

    def __init__(self) -> None:
        self.normal: dict[tuple, tuple] = {}
        self.paar: dict[tuple, tuple[float, dict]] = {}
        self.regel: dict[tuple, tuple] = {}
        self.satz: dict[tuple, tuple] = {}  # abgeleitete Vergleichswerte je Satzinhalt (Kontext)
        self.eimer: dict[tuple, tuple] = {}  # Blocking-Eimer (Mitglieder) → Kombinationen
        # schlanker Modus (Monatsverlauf): Kandidaten inkrementell, Ergebnis nur Paare ab Prüfschwelle
        self.schlank = False
        self.eimer_index: dict[tuple, set[int]] = defaultdict(set)  # Eimer → alle je gesehenen Satzinhalte
        self.kand: set[tuple[int, int]] = set()  # Kandidatenpaare (vid, vid) des vorigen Stands
        self.vorher: set[int] = set()  # Satzinhalte des vorigen Stands
        self.score: dict[tuple[int, int], Paar] = {}  # bewertete Paare (vid, vid)
        self.treffer: set[tuple[int, int]] = set()  # Paare ab Prüfschwelle


_VERGLEICHSFELDER = ("objekt", "nr", "land", "plz", "name1", "strasse", "hausnr", "ort", "iban", "ust_id", "telefon")
_V_SPALTEN = ["objekt", "nr", "land", "plz", "name_n", "adr_n", "ort_n", "iban_n", "ust_n", "tel_n", "anfang"]


def _normalisiere(objekt, nr, land, plz, name1, strasse, hausnr, ort, iban, ust_id, telefon) -> tuple:
    return (objekt, nr, land or "", (plz or "").strip(), name_normal(name1), adresse_normal(strasse, hausnr),
            ort_normal(ort), pz.iban_normal(iban) if iban and pz.iban_gueltig(iban) else "", pz.ust_normal(ust_id),
            pz.telefon_ziffern(telefon), namensanfang(name1))


def vorbereiten(df: pd.DataFrame, speicher: Rechenspeicher | None = None) -> pd.DataFrame:
    """Vergleichsspalten je Satz (normalisiert); Spalte ``vid`` = Kennung des Satzinhalts im Rechenspeicher."""
    cache = speicher.normal if speicher is not None else {}
    zeilen, ids = [], []
    for schluessel in zip(*(df[f].tolist() for f in _VERGLEICHSFELDER), strict=True):
        eintrag = cache.get(schluessel)
        if eintrag is None:
            eintrag = cache[schluessel] = (len(cache), _normalisiere(*schluessel))
        ids.append(eintrag[0])
        zeilen.append(eintrag[1])
    v = pd.DataFrame(zeilen, columns=_V_SPALTEN, dtype=object)
    v["vid"] = ids
    return v


def _eimer_schluessel(objekt, land, plz, iban_n, ust_n, anfang) -> tuple:
    s = []
    if plz:
        s.append(("PLZ", objekt, plz))
    if iban_n:
        s.append(("IBAN/USt", objekt, "I", iban_n))
    if ust_n:
        s.append(("IBAN/USt", objekt, "U", ust_n))
    if len(anfang) >= 3 and land:
        s.append(("Namensanfang", objekt, land, anfang))
    return tuple(s)


def kandidaten(v: pd.DataFrame, speicher: Rechenspeicher | None = None) -> dict[tuple[int, int], set[str]]:
    """Kandidatenpaare (Indexpaare i < j innerhalb eines Objekts) mit den Pässen, die sie erzeugt haben.

    Mit Rechenspeicher: Eimer, deren Mitglieder sich gegenüber einem früheren Stand nicht geändert haben, liefern
    ihre Paare aus dem Speicher (inkrementelle Monatsstände)."""
    eimer: dict[tuple, list[int]] = defaultdict(list)
    vids = v.vid.tolist() if "vid" in v.columns else list(range(len(v)))
    for i, zeile in enumerate(zip(v.objekt, v.land, v.plz, v.iban_n, v.ust_n, v.anfang, strict=True)):
        for schluessel in _eimer_schluessel(*zeile):
            eimer[schluessel].append(i)
    paar_cache = speicher.eimer if speicher is not None else {}
    paare: dict[tuple[int, int], set[str]] = defaultdict(set)
    for schluessel, idx in eimer.items():
        if len(idx) < 2:
            continue
        mitglieder = tuple(vids[i] for i in idx)
        kombi = paar_cache.get(mitglieder)
        if kombi is None:
            kombi = paar_cache[mitglieder] = tuple(combinations(range(len(idx)), 2))
        for x, y in kombi:
            paare[(idx[x], idx[y])].add(schluessel[0])
    return paare


def bewerte(x, y) -> tuple[float, dict]:
    """Score und Merkmale eines Paars (x, y: Zeilen aus ``vorbereiten``)."""
    name = float(fuzz.token_sort_ratio(x.name_n, y.name_n)) if x.name_n and y.name_n else 0.0
    strasse = float(fuzz.ratio(x.adr_n, y.adr_n)) if x.adr_n and y.adr_n else 50.0
    if x.plz and x.plz == y.plz:
        ort = 100.0
    elif x.ort_n and y.ort_n:
        ort = 0.6 * float(fuzz.ratio(x.ort_n, y.ort_n))
    else:
        ort = 0.0
    gleiche_iban = bool(x.iban_n and x.iban_n == y.iban_n)
    gleiche_ust = bool(x.ust_n and x.ust_n == y.ust_n)
    gleiche_tel = bool(x.tel_n and len(x.tel_n) >= 8 and x.tel_n == y.tel_n)
    ust_verschieden = bool(x.ust_n and y.ust_n and x.ust_n != y.ust_n)
    b_name, b_strasse, b_ort = GEWICHT_NAME * name, GEWICHT_STRASSE * strasse, GEWICHT_ORT * ort
    zuschlag = ZUSCHLAG_IBAN * gleiche_iban + ZUSCHLAG_UST * gleiche_ust + ZUSCHLAG_TELEFON * gleiche_tel
    abschlag = ABSCHLAG_UST_VERSCHIEDEN * ust_verschieden
    score = round(max(0.0, min(100.0, b_name + b_strasse + b_ort + zuschlag - abschlag)), 1)
    merkmale = {
        "name_aehnlichkeit": round(name, 1), "strasse_aehnlichkeit": round(strasse, 1), "ort_wert": round(ort, 1),
        "gleiche_plz": bool(x.plz and x.plz == y.plz), "gleiche_iban": gleiche_iban, "gleiche_ust": gleiche_ust,
        "gleiche_telefon": gleiche_tel, "ust_verschieden": ust_verschieden,
        "beitrag_name": round(b_name, 1), "beitrag_strasse": round(b_strasse, 1), "beitrag_ort": round(b_ort, 1),
        "beitrag_merkmale": round(zuschlag - abschlag, 1),
    }
    return score, merkmale


_VZeile = namedtuple("_VZeile", _V_SPALTEN)


class _UnionFind:
    def __init__(self) -> None:
        self.eltern: dict[str, str] = {}

    def finde(self, x: str) -> str:
        self.eltern.setdefault(x, x)
        while self.eltern[x] != x:
            self.eltern[x] = self.eltern[self.eltern[x]]
            x = self.eltern[x]
        return x

    def vereinige(self, a: str, b: str) -> None:
        ra, rb = self.finde(a), self.finde(b)
        if ra != rb:
            self.eltern[max(ra, rb)] = min(ra, rb)


def cluster_bilden(paare: list[Paar], schwelle: float = SCHWELLE_PRUEFEN) -> dict[str, list[list[str]]]:
    ergebnis: dict[str, list[list[str]]] = {}
    treffer = [p for p in paare if p.score >= schwelle]
    for objekt in ("DEBI", "KRED"):
        uf = _UnionFind()
        for p in treffer:
            if p.objekt == objekt:
                uf.vereinige(p.a, p.b)
        gruppen: dict[str, list[str]] = defaultdict(list)
        for x in list(uf.eltern):
            gruppen[uf.finde(x)].append(x)
        ergebnis[objekt] = sorted(sorted(g) for g in gruppen.values() if len(g) > 1)
    return ergebnis


def finde_dubletten(df: pd.DataFrame, speicher: Rechenspeicher | None = None) -> Dublettenergebnis:
    """Kandidaten bilden, bewerten und clustern (alle Sätze, auch mit Löschvormerkung – die Regeln filtern).

    Jeder Satzinhalt erhält im Rechenspeicher eine Kennung (vid) mit normalisierten Werten und Blocking-Schlüsseln;
    Paare werden je (vid, vid) nur einmal bewertet. Für einen einzelnen Lauf ohne Speicher ist das Ergebnis identisch.
    """
    sp = speicher or Rechenspeicher()
    if sp.schlank:
        return _finde_inkrementell(df, sp)
    vids, zeilen_v = [], []
    for roh in zip(*(df[f].tolist() for f in _VERGLEICHSFELDER), strict=True):
        eintrag = sp.normal.get(roh)
        if eintrag is None:
            norm = _normalisiere(*roh)
            eintrag = sp.normal[roh] = (len(sp.normal), norm, _eimer_schluessel(norm[0], norm[2], norm[3], norm[7],
                                                                               norm[8], norm[10]))
        vids.append(eintrag[0])
        zeilen_v.append(eintrag)
    eimer: dict[tuple, list[int]] = defaultdict(list)
    for i, eintrag in enumerate(zeilen_v):
        for schluessel in eintrag[2]:
            eimer[schluessel].append(i)
    kand: dict[tuple[int, int], set[str]] = defaultdict(set)
    for schluessel, idx in eimer.items():
        if len(idx) < 2:
            continue
        mitglieder = tuple(vids[i] for i in idx)
        kombi = sp.eimer.get(mitglieder)
        if kombi is None:
            kombi = sp.eimer[mitglieder] = tuple(combinations(range(len(idx)), 2))
        for x, y in kombi:
            kand[(idx[x], idx[y])].add(schluessel[0])
    paare: list[Paar] = []
    mit = {"DEBI": 0, "KRED": 0}
    je_pass = {o: dict.fromkeys(PAESSE, 0) for o in ("DEBI", "KRED")}
    for (i, j), paesse in sorted(kand.items()):
        schl = (vids[i], vids[j])  # Pässe folgen eindeutig aus den beiden Satzinhalten
        paar = sp.paar.get(schl)
        if paar is None:
            x, y = zeilen_v[i][1], zeilen_v[j][1]
            score, merkmale = bewerte(_VZeile(*x), _VZeile(*y))
            a, b = sorted((x[1], y[1]))
            paar = sp.paar[schl] = Paar(x[0], a, b, score, stufe(score), merkmale,
                                        tuple(p for p in PAESSE if p in paesse))
        paare.append(paar)
        mit[paar.objekt] += 1
        for ps in paar.paesse:
            je_pass[paar.objekt][ps] += 1
    anzahl = {"DEBI": 0, "KRED": 0}
    for o in df.objekt.tolist():
        anzahl[o] += 1
    ohne = {o: n * (n - 1) // 2 for o, n in anzahl.items() if n}
    return Dublettenergebnis(paare, cluster_bilden(paare), ohne, mit, je_pass)


def _obergrenze(x: tuple, y: tuple) -> float:
    """Höchstmöglicher Score eines Paars ohne Straßen- und Ortsvergleich (Straße ≤ 25, Ort ≤ 15) – exakt nach
    ``bewerte``; erlaubt, Paare unter der Prüfschwelle im schlanken Modus ohne Vollbewertung zu überspringen."""
    name = float(fuzz.token_sort_ratio(x[4], y[4])) if x[4] and y[4] else 0.0
    harte = (ZUSCHLAG_IBAN if x[7] and x[7] == y[7] else 0) + (ZUSCHLAG_UST if x[8] and x[8] == y[8] else 0) + (
        ZUSCHLAG_TELEFON if x[9] and len(x[9]) >= 8 and x[9] == y[9] else 0)
    return GEWICHT_NAME * name + GEWICHT_STRASSE * 100 + GEWICHT_ORT * 100 + harte


def _finde_inkrementell(df: pd.DataFrame, sp: Rechenspeicher) -> Dublettenergebnis:
    """Monatsverlauf: Kandidaten aus dem Vorstand fortschreiben, nur neue Satzinhalte über ihre Eimer suchen.

    Ein Paar ist Kandidat, wenn beide Satzinhalte einen Blocking-Eimer teilen – das hängt nur von den beiden Inhalten
    ab. Deshalb gilt: Kandidaten = (Kandidaten des Vorstands, deren Inhalte noch vorhanden sind) ∪ (Paare mit einem
    neuen Inhalt). Zurückgegeben werden nur Paare ab Prüfschwelle (mehr braucht der Verlauf nicht); Cluster, Zähler
    „mit/ohne Blocking“ und Scores sind identisch zur vollständigen Berechnung (Test test_inkrementell_gleich_*)."""
    zeilen: dict[int, tuple] = {}
    for roh in zip(*(df[f].tolist() for f in _VERGLEICHSFELDER), strict=True):
        eintrag = sp.normal.get(roh)
        if eintrag is None:
            norm = _normalisiere(*roh)
            eintrag = sp.normal[roh] = (len(sp.normal), norm, _eimer_schluessel(norm[0], norm[2], norm[3], norm[7],
                                                                               norm[8], norm[10]))
        zeilen[eintrag[0]] = eintrag
    neu = [v for v in zeilen if v not in sp.vorher]
    for v in neu:
        for schluessel in zeilen[v][2]:
            sp.eimer_index[schluessel].add(v)
    kand = {pq for pq in sp.kand if pq[0] in zeilen and pq[1] in zeilen}
    for v in neu:
        for schluessel in zeilen[v][2]:
            for w in sp.eimer_index[schluessel]:
                if w != v and w in zeilen:
                    kand.add((v, w) if v < w else (w, v))
    mit = {"DEBI": 0, "KRED": 0}
    for pq in kand:
        mit[zeilen[pq[0]][1][0]] += 1
        if pq not in sp.score:
            x, y = zeilen[pq[0]], zeilen[pq[1]]
            if _obergrenze(x[1], y[1]) < SCHWELLE_PRUEFEN - 0.05:  # erreicht die Schwelle auch gerundet nicht
                sp.score[pq] = None
                continue
            score, merkmale = bewerte(_VZeile(*x[1]), _VZeile(*y[1]))
            a, b = sorted((x[1][1], y[1][1]))
            gemeinsam = {e[0] for e in set(x[2]) & set(y[2])}
            sp.score[pq] = Paar(x[1][0], a, b, score, stufe(score), merkmale,
                                tuple(p for p in PAESSE if p in gemeinsam))
            if score >= SCHWELLE_PRUEFEN:
                sp.treffer.add(pq)
    sp.kand, sp.vorher = kand, set(zeilen)
    paare = [sp.score[pq] for pq in sorted(sp.treffer) if pq in kand]
    anzahl = {"DEBI": 0, "KRED": 0}
    for o in df.objekt.tolist():
        anzahl[o] += 1
    ohne = {o: n * (n - 1) // 2 for o, n in anzahl.items() if n}
    return Dublettenergebnis(paare, cluster_bilden(paare), ohne, mit, {})


# ── Messung gegen die Wahrheitsdatei ───────────────────────────────────────────────────────────────────────────


def wahre_paare(wahrheit: dict) -> set[tuple[str, str, str]]:
    paare = set()
    for objekt, cluster in wahrheit["dubletten"].items():
        for c in cluster:
            for a, b in combinations(sorted(c), 2):
                paare.add((objekt, a, b))
    return paare


@dataclass(frozen=True)
class Messung:
    schwelle: float
    tp: int
    fp: int
    fn: int
    wahre_paare: int
    blocking_recall: float
    vergleiche_ohne: int
    vergleiche_mit: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / self.wahre_paare if self.wahre_paare else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def als_dict(self) -> dict:
        return {"schwelle": self.schwelle, "tp": self.tp, "fp": self.fp, "fn": self.fn,
                "wahre_paare": self.wahre_paare, "precision": round(self.precision, 4),
                "recall": round(self.recall, 4), "f1": round(self.f1, 4),
                "blocking_recall": round(self.blocking_recall, 4), "vergleiche_ohne_blocking": self.vergleiche_ohne,
                "vergleiche_mit_blocking": self.vergleiche_mit}


def miss(ergebnis: Dublettenergebnis, wahrheit: dict, schwelle: float = SCHWELLE_PRUEFEN) -> Messung:
    wahr = wahre_paare(wahrheit)
    vorhergesagt = {(p.objekt, p.a, p.b) for p in ergebnis.paare if p.score >= schwelle}
    verglichen = {(p.objekt, p.a, p.b) for p in ergebnis.paare}
    tp = len(wahr & vorhergesagt)
    return Messung(schwelle, tp, len(vorhergesagt - wahr), len(wahr - vorhergesagt), len(wahr),
                   len(wahr & verglichen) / len(wahr) if wahr else 1.0,
                   sum(ergebnis.vergleiche_ohne_blocking.values()), sum(ergebnis.vergleiche_mit_blocking.values()))
