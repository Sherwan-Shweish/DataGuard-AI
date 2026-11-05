"""Regelwerk der Stammdatenqualität – als Daten (Regelkatalog), ausgewertet von einer kleinen Engine.

Jede Regel nennt Objekt, SAP-Feld, DAMA-Dimension, Schweregrad, Beschreibung, Begründung und Korrekturvorschlag und
verweist auf eine **benannte Prüfung** mit Parametern (``PRUEFUNGEN``). Eine Prüfung liefert je Satz
``True`` (verletzt), ``False`` (bestanden) oder ``None`` (nicht anwendbar). Keine verstreuten if-Abfragen: neue Regeln
entstehen durch einen weiteren Katalogeintrag.

DAMA-Dimensionen nach DAMA-DMBOK (2. Aufl., Kap. 13 „Data Quality“; Stand prüfen): Vollständigkeit, Gültigkeit,
Eindeutigkeit, Konsistenz, Aktualität.

Kennzahlen:
* Score je Dimension = bestandene / anwendbare Prüfungen (Satz × Regel) der Dimension, in %.
* Gesamtscore = ungewichteter Mittelwert der fünf Dimensionsscores.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from operator import itemgetter

import numpy as np
import pandas as pd

from src import pruefziffern as pz
from src.config import ARCHIV_MONATE, BANKAENDERUNG_TAGE, monate_zurueck
from src.customizing import (
    KONTENGRUPPE,
    ZAHLUNGSBEDINGUNGEN,
    erwartete_region,
    nummer_im_kreis,
)
from src.dubletten import (
    SCHWELLE_PRUEFEN,
    SCHWELLE_SEHR_WAHRSCHEINLICH,
    Dublettenergebnis,
    Rechenspeicher,
    finde_dubletten,
)
from src.normalisierung import ist_gesellschaft, name_normal

DIMENSIONEN = ("Vollständigkeit", "Gültigkeit", "Eindeutigkeit", "Konsistenz", "Aktualität")
SCHWEREGRADE = ("Blocker", "Fehler", "Hinweis")
#: Steueranweisungen in Datentexten (Prompt-Injection-Muster) – nur Erkennung, nie Ausführung.
INJEKTIONSMUSTER = re.compile(
    r"(ignorier\w*\s+(alle|die|vorherige\w*)|ignore\s+(all|previous|the)|system\s*prompt|gib\s+.{0,40}\baus\b"
    r"|<\s*script|```|anweisung(en)?\s+(an|f[uü]r)\s+(die\s+)?ki)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Regel:
    id: str
    objekt: str  # "beide" | "DEBI" | "KRED"
    sap_feld: str
    feld: str  # flaches Feld für Beispiele ("" = kein Einzelfeld)
    dimension: str
    schweregrad: str
    beschreibung: str
    begruendung: str
    korrektur: str
    pruefung: str
    parameter: tuple[tuple[str, object], ...] = ()
    cvi_blocker: bool = False  # verhindert die Übernahme als Geschäftspartner (siehe migration.py)

    @property
    def param(self) -> dict:
        return dict(self.parameter)


def _r(id_, objekt, sap_feld, anzeige, dimension, schweregrad, beschreibung, begruendung, korrektur, pruefung,
       cvi=False, **param) -> Regel:
    return Regel(id_, objekt, sap_feld, anzeige, dimension, schweregrad, beschreibung, begruendung, korrektur, pruefung,
                 tuple(sorted(param.items())), cvi)


V, G, E, K, A = DIMENSIONEN
B, F, H = SCHWEREGRADE

REGELN: tuple[Regel, ...] = (
    # ── Vollständigkeit ─────────────────────────────────────────────────────────────────────────────────────────
    _r("V01", "beide", "KNA1/LFA1-NAME1", "name1", V, B, "Name 1 fehlt",
       "Ohne Namen kann kein Geschäftspartner angelegt werden.", "Namen aus Vertrag/Rechnung ergänzen.",
       "pflicht", cvi=True, feld="name1"),
    _r("V02", "beide", "ADRC-STREET", "strasse", V, F, "Straße fehlt",
       "Anschrift ist Pflicht für Rechnungen (§ 14 UStG) und Mahnwesen.", "Straße ergänzen.", "pflicht",
       feld="strasse"),
    _r("V03", "beide", "ADRC-HOUSE_NUM1", "hausnr", V, H, "Hausnummer fehlt",
       "Unvollständige Anschrift erschwert Zustellung und Dublettenabgleich.", "Hausnummer ergänzen.",
       "pflicht_wenn", feld="hausnr", wenn="strasse"),
    _r("V04", "beide", "ADRC-POST_CODE1", "plz", V, B, "Postleitzahl fehlt",
       "Die Adressprüfung des Geschäftspartners verlangt eine PLZ.", "PLZ ergänzen.", "pflicht", cvi=True,
       feld="plz"),
    _r("V05", "beide", "ADRC-CITY1", "ort", V, B, "Ort fehlt", "Pflichtfeld der BP-Anschrift.", "Ort ergänzen.",
       "pflicht", cvi=True, feld="ort"),
    _r("V06", "beide", "KNA1/LFA1-LAND1", "land", V, B, "Land fehlt",
       "Land steuert Adressformat, Steuer und Bankprüfung.", "Land ergänzen.", "pflicht", cvi=True, feld="land"),
    _r("V07", "beide", "KNA1/LFA1-SPRAS", "sprache", V, F, "Sprache fehlt",
       "Korrespondenzsprache ist Pflichtfeld des Geschäftspartners.", "Sprache aus dem Land ableiten (DE → DE).",
       "pflicht", feld="sprache"),
    _r("V08", "beide", "KNA1/LFA1-STCEG", "ust_id", V, F, "USt-IdNr. fehlt (EU-Ausland)",
       "Für innergemeinschaftliche Lieferungen/Erwerbe ist die USt-IdNr. nötig (§ 6a UStG; Stand prüfen).",
       "USt-IdNr. beim Partner anfordern und über VIES bestätigen.", "ust_fehlt_eu"),
    _r("V09", "beide", "KNA1/LFA1-STCEG", "ust_id", V, H, "USt-IdNr. fehlt (Inland, Gesellschaft)",
       "Kapital- und Personengesellschaften haben in der Regel eine USt-IdNr.; erleichtert Abgleich und E-Rechnung.",
       "USt-IdNr. anfordern.", "ust_fehlt_inland"),
    _r("V10", "KRED", "LFBK-IBAN", "iban", V, F, "Kreditor ohne Bankverbindung",
       "Zahlung per Überweisung nicht möglich; Bankdaten sind BP-Pflicht für Zahlungen.",
       "Bankverbindung schriftlich anfordern (Vier-Augen-Prüfung).", "bank_fehlt"),
    _r("V11", "beide", "ADR6-SMTP_ADDR", "email", V, H, "E-Mail fehlt",
       "E-Rechnung, Avis und Mahnung per E-Mail nicht möglich.", "E-Mail-Adresse ergänzen.", "pflicht", feld="email"),
    _r("V12", "beide", "ADRC-TEL_NUMBER", "telefon", V, H, "Telefonnummer fehlt",
       "Rückfragen (z. B. Bestätigung einer Bankänderung) nicht möglich.", "Telefonnummer ergänzen.", "pflicht",
       feld="telefon"),
    _r("V13", "beide", "KNB1/LFB1-ZTERM", "zterm", V, F, "Zahlungsbedingung fehlt",
       "Fälligkeit und Skonto lassen sich nicht berechnen.", "Standard ZB30 setzen oder vertraglich klären.",
       "pflicht", feld="zterm"),
    _r("V14", "beide", "KNB1/LFB1-AKONT", "akont", V, B, "Abstimmkonto fehlt",
       "Buchungskreisdaten ohne Abstimmkonto werden von der CVI abgewiesen.", "Abstimmkonto 140000/160000 setzen.",
       "pflicht", cvi=True, feld="akont"),
    _r("V15", "beide", "KNA1-KTOKD/LFA1-KTOKK", "ktogr", V, B, "Kontengruppe fehlt",
       "Ohne Kontengruppe keine BP-Gruppierung und kein Nummernkreis.", "Kontengruppe nach Partnerart setzen.",
       "pflicht", cvi=True, feld="ktogr"),
    # ── Gültigkeit ──────────────────────────────────────────────────────────────────────────────────────────────
    _r("G01", "beide", "KNBK/LFBK-IBAN", "iban", G, B, "IBAN-Prüfziffer falsch (ISO 13616, Mod 97)",
       "Zahlung wird von der Bank abgewiesen oder landet beim falschen Empfänger.",
       "IBAN beim Partner schriftlich bestätigen lassen.", "iban_pruefziffer", cvi=True),
    _r("G02", "beide", "KNBK/LFBK-IBAN", "iban", G, B, "IBAN-Länge passt nicht zum Land",
       "Länge je Land ist fest (SWIFT IBAN Registry).", "IBAN prüfen und neu erfassen.", "iban_laenge", cvi=True),
    _r("G03", "beide", "KNBK/LFBK-IBAN", "iban", G, B, "IBAN-Ländercode unbekannt",
       "Ländercode nicht im IBAN-Verzeichnis.", "IBAN prüfen und neu erfassen.", "iban_land", cvi=True),
    _r("G04", "beide", "KNBK/LFBK-BANKL", "bankl", G, F, "Bankleitzahl im IBAN ≠ Stammdatum BLZ",
       "Widersprüchliche Bankdaten – Hinweis auf Tippfehler oder Manipulation.", "BLZ aus der IBAN übernehmen.",
       "iban_blz"),
    _r("G05", "beide", "KNA1/LFA1-STCEG", "ust_id", G, F, "USt-IdNr.-Format ungültig",
       "Format je EU-Land festgelegt (EU-Kommission, VIES).", "USt-IdNr. korrigieren und bestätigen.", "ust_format"),
    _r("G06", "beide", "KNA1/LFA1-STCEG", "ust_id", G, F, "USt-IdNr. (DE) Prüfziffer falsch",
       "Prüfziffer nach ISO 7064 MOD 11,10 (Verfahren BZSt) – wie FlowAudit-AI.",
       "Nummer beim Partner erfragen.", "ust_de_pruefziffer"),
    _r("G07", "beide", "ADRC-POST_CODE1", "plz", G, B, "PLZ-Format ungültig für das Land",
       "Die Adressprüfung des Geschäftspartners lehnt falsche PLZ-Formate ab.", "PLZ korrigieren.", "plz_format",
       cvi=True),
    _r("G08", "beide", "ADR6-SMTP_ADDR", "email", G, F, "E-Mail-Syntax ungültig",
       "E-Rechnung und Avis werden nicht zugestellt.", "E-Mail-Adresse korrigieren.", "email"),
    _r("G09", "beide", "KNA1/LFA1-SPRAS", "sprache", G, F, "Sprache nicht zulässig",
       "Sprachschlüssel nicht im System gepflegt.", "Sprache aus dem Land ableiten.", "wertebereich", feld="sprache",
       werte="SPRACHEN"),
    _r("G10", "beide", "ADRC-TEL_NUMBER", "telefon", G, H, "Telefon nicht international (+Ländervorwahl)",
       "Einheitliches Format erleichtert Abgleich und Rückruf.", "In +49-Schreibweise umstellen.", "telefon"),
    _r("G11", "beide", "KNB1/LFB1-ZTERM", "zterm", G, F, "Zahlungsbedingung unbekannt",
       "Schlüssel nicht in T052 – Fälligkeit nicht berechenbar.", "Gültige Zahlungsbedingung setzen.", "wertebereich",
       feld="zterm", werte="ZAHLUNGSBEDINGUNGEN"),
    _r("G12", "beide", "KNA1/LFA1-LAND1", "land", G, B, "Land unbekannt",
       "Kein gültiger ISO-Ländercode (z. B. Altwert „DD“).", "Land korrigieren.", "wertebereich", cvi=True,
       feld="land", werte="LAENDER"),
    _r("G13", "beide", "KNBK/LFBK-SWIFT", "swift", G, F, "BIC-Format ungültig",
       "BIC nach ISO 9362: 8 oder 11 Zeichen.", "BIC korrigieren oder leer lassen (SEPA-Inland).", "bic"),
    _r("G14", "beide", "KNA1/LFA1-NAME1/NAME2/SORTL, ADRC-STREET", "name2", G, H,
       "Freitext enthält eine Steueranweisung (Datentext-Angriff)",
       "Datentexte sind Daten – nie Anweisungen an die KI (Agenten-Standard v1).",
       "Text entfernen, Satz prüfen; Fall an IT-Sicherheit melden.", "injektion"),
    # ── Eindeutigkeit ───────────────────────────────────────────────────────────────────────────────────────────
    _r("E01", "beide", "Name/Anschrift/IBAN/USt", "", E, B, "Dublette sehr wahrscheinlich (Score ≥ 90)",
       "Vor der CVI zusammenführen – sonst entstehen doppelte Geschäftspartner.",
       "Golden Record prüfen und namentlich entscheiden.", "dublette", stufe="hoch"),
    _r("E02", "beide", "Name/Anschrift/IBAN/USt", "", E, F, "Mögliche Dublette (Score 75–89)",
       "Ähnliche Sätze – fachlich prüfen.", "Paarvergleich prüfen, ggf. Golden Record.", "dublette", stufe="pruefen"),
    _r("E03", "KRED", "LFBK-IBAN", "iban", E, B, "Gleiche IBAN bei mehreren Kreditoren",
       "Doppelzahlungsrisiko – Einzelrechnungen prüft FlowAudit-AI.", "Dublette klären oder Factoring dokumentieren.",
       "gleicher_wert", cvi=True, feld="iban"),
    _r("E04", "beide", "KNA1/LFA1-STCEG", "ust_id", E, F, "Gleiche USt-IdNr. bei mehreren Sätzen",
       "Eine USt-IdNr. gehört zu genau einem Unternehmen.", "Dublette prüfen.", "gleicher_wert", feld="ust_id"),
    _r("E05", "beide", "KNA1-LIFNR/LFA1-KUNNR", "verknuepft", E, B, "Kunde = Lieferant ohne Verknüpfung",
       "Ein Partner, zwei Rollen: ohne Verknüpfung entstehen zwei Geschäftspartner.",
       "KNA1-LIFNR und LFA1-KUNNR gegenseitig pflegen (ein BP mit zwei Rollen).", "kunde_lieferant", cvi=True),
    # ── Konsistenz ──────────────────────────────────────────────────────────────────────────────────────────────
    _r("K01", "DEBI", "KNVV-BZIRK", "bzirk", K, F, "Vertriebsgebiet passt nicht zur PLZ",
       "Falsche Region verfälscht Umsatz je Region (VarianceAI/ControllAI).", "Gebiet nach PLZ-Leitzone setzen.",
       "region_plz"),
    _r("K02", "beide", "KNA1-KTOKD/LFA1-KTOKK", "ktogr", K, B, "Kontengruppe ohne BP-Gruppierung (CVI)",
       "Ohne Zuordnung bricht die Synchronisation zum Geschäftspartner ab.",
       "CVI-Zuordnung ergänzen oder Satz einer gültigen Kontengruppe zuordnen.", "bp_zuordnung", cvi=True),
    _r("K03", "beide", "KNA1/LFA1-STCEG", "ust_id", K, F, "Land der USt-IdNr. ≠ Land der Anschrift",
       "Steuerkennzeichen und Steuernummernkategorie werden falsch abgeleitet.", "Anschrift oder USt-IdNr. klären.",
       "ust_land"),
    _r("K04", "beide", "KNBK/LFBK-BANKS", "banks", K, F, "Bankland ≠ Land der IBAN",
       "Widersprüchliche Bankdaten.", "Bankland aus der IBAN übernehmen.", "bank_land"),
    _r("K05", "beide", "KNA1-KUNNR/LFA1-LIFNR", "", K, B, "Nummer außerhalb des Nummernkreises der Kontengruppe",
       "BP-Nummer = Debitor-/Kreditornummer: Nummernkreis muss passen.", "Kontengruppe oder Nummer klären.",
       "nummernkreis", cvi=True),
    _r("K06", "beide", "KNA1-KUNNR/LFA1-LIFNR", "", K, B, "Nummernkonflikt Debitor/Kreditor",
       "Gleiche Nummer, verschiedener Partner – bei „gleiche Nummern“ in S/4HANA nicht übernehmbar.",
       "Einen der Sätze umnummerieren (neue Nummer im Migrationsmapping).", "nummernkonflikt", cvi=True),
    _r("K07", "beide", "KNA1-LIFNR/LFA1-KUNNR", "verknuepft", K, F, "Verknüpfung Kunde/Lieferant einseitig",
       "Die Gegenseite verweist nicht zurück oder existiert nicht.", "Verknüpfung beidseitig pflegen.",
       "verknuepfung"),
    _r("K08", "beide", "KNA1/LFA1-LOEVM", "loevm", K, F, "Löschvormerkung trotz offener Posten",
       "Offene Posten müssen vor Archivierung ausgeglichen sein.", "Offene Posten klären, dann archivieren.",
       "loevm_op"),
    # ── Aktualität ──────────────────────────────────────────────────────────────────────────────────────────────
    _r("A01", "beide", "BSAD/BSAK (letzte Buchung)", "", A, H, "Keine Buchung seit > 24 Monaten, keine Löschvormerkung",
       "Archivierungskandidat – nicht migrieren, sondern archivieren.", "Löschvormerkung setzen (nach Prüfung).",
       "inaktiv"),
    _r("A02", "beide", "KNA1/LFA1-ERDAT", "", A, H, "Nie bebucht und älter als 24 Monate, keine Löschvormerkung",
       "Angelegt, aber nie genutzt – nicht migrieren.", "Löschvormerkung setzen.", "nie_bebucht"),
    _r("A03", "beide", "KNA1/LFA1-SPERR", "sperr", A, H, "Gesperrt ohne offene Posten, keine Löschvormerkung",
       "Gesperrte Sätze ohne offene Posten werden nicht migriert.", "Archivieren oder Sperre begründen.",
       "gesperrt_ohne_op"),
    _r("A04", "beide", "CDHDR/CDPOS (Bank)", "iban", A, H, "Bankverbindung in den letzten 30 Tagen geändert",
       "Präventionsszenario Zahlungsumleitung: Vier-Augen-Prüfung (wie FlowAudit-AI).",
       "Rückruf unter bekannter Telefonnummer, zweite Person bestätigt.", "bankaenderung"),
)
REGEL = {r.id: r for r in REGELN}


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Kontext und Prüfungen
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════


@dataclass
class Kontext:
    stichtag: date
    archivgrenze: date
    archiv: set[str]
    dubletten: Dublettenergebnis
    dubletten_max: dict[str, tuple[float, tuple[str, ...]]]  # Schlüssel → (höchster Score, Partner ab Prüfschwelle)
    gleiche_iban: dict[str, tuple[str, ...]]
    gleiche_ust: dict[str, tuple[str, ...]]
    kunde_lieferant: dict[str, tuple[str, ...]]  # unverknüpfte Gegenstücke
    nummernkonflikt: dict[str, tuple[str, ...]]
    verknuepfung_ok: dict[str, bool]
    bankaenderung: dict[str, date]
    verknuepfte_paare: list[tuple[str, str]] = field(default_factory=list)
    zeilen: dict = field(default_factory=dict)  # Schlüssel → Satz (Zeile des geprüften Stands)
    iban_gueltig: frozenset[str] = frozenset()  # Schlüssel mit formal gültiger IBAN
    inhalte: dict = field(default_factory=dict)  # Schlüssel → Satzinhalt ohne Bewegungsfelder (Rechenspeicher)


#: Felder, die sich mit jeder Buchung ändern, aber von keiner satzbezogenen Prüfung gelesen werden – sie bleiben im
#: Schlüssel des Rechenspeichers außen vor, damit laufend bebuchte Sätze nicht jeden Monat neu geprüft werden.
_BEWEGUNGSFELDER = frozenset({"letzte_buchung", "anz_belege"})
_INHALT_GETTER: dict[tuple[str, ...], Callable] = {}


def satzinhalt(z) -> tuple:
    """Schlüssel für den Rechenspeicher: Satz ohne Bewegungsfelder."""
    getter = _INHALT_GETTER.get(z._fields)
    if getter is None:
        getter = _INHALT_GETTER[z._fields] = itemgetter(
            *(i for i, f in enumerate(z._fields) if f not in _BEWEGUNGSFELDER))
    return getter(z)


def ist_archivkandidat(s, grenze: date) -> bool:
    """Archivierung statt Migration (Definition in docs/methodik.md)."""
    lb = s.letzte_buchung
    return bool(s.loevm == "X" or (lb is not None and lb < grenze) or (lb is None and s.erdat < grenze)
                or (s.sperr == "X" and s.op != "X"))


def baue_kontext(df: pd.DataFrame, stichtag: date, aenderungen: pd.DataFrame | None = None,
                 dubletten: Dublettenergebnis | None = None, speicher: Rechenspeicher | None = None) -> Kontext:
    grenze = monate_zurueck(stichtag, ARCHIV_MONATE)
    zeilen = {z.schluessel: z for z in df.itertuples(index=False)}
    archiv = {k for k, z in zeilen.items() if ist_archivkandidat(z, grenze)}
    aktiv = {k for k, z in zeilen.items() if z.loevm != "X"}
    dub = dubletten or finde_dubletten(df, speicher)
    dmax: dict[str, tuple[float, list[str]]] = {}
    for p in dub.paare:
        ka, kb = f"{p.objekt}:{p.a}", f"{p.objekt}:{p.b}"
        if ka not in aktiv or kb not in aktiv or p.score < SCHWELLE_PRUEFEN:
            continue
        for k, partner in ((ka, kb), (kb, ka)):
            alt = dmax.get(k, (0.0, []))
            dmax[k] = (max(alt[0], p.score), [*alt[1], partner])

    cache = speicher.satz if speicher is not None else {}
    abgeleitet = {}
    inhalte = {k: satzinhalt(z) for k, z in zeilen.items()} if speicher is not None else zeilen
    for k, z in zeilen.items():
        inhalt = inhalte[k]
        a = cache.get(inhalt)
        if a is None:
            iban_ok = bool(z.iban) and pz.iban_gueltig(z.iban)
            a = cache[inhalt] = (pz.iban_normal(z.iban) if iban_ok else "", pz.ust_normal(z.ust_id), _kl_schluessel(z))
        abgeleitet[k] = a

    def gruppen(index: int, objekte: tuple[str, ...]):
        g: dict[tuple, list[str]] = defaultdict(list)
        for k, z in zeilen.items():
            wert = abgeleitet[k][index]
            if z.objekt in objekte and k in aktiv and wert:
                g[(z.objekt, wert)].append(k)
        return {k: tuple(x for x in liste if x != k) for liste in g.values() if len(liste) > 1 for k in liste}

    gleiche_iban = gruppen(0, ("KRED",))
    gleiche_ust = gruppen(1, ("DEBI", "KRED"))

    # Kunde = Lieferant: gleiche USt-IdNr., gleiche gültige IBAN oder gleicher Name + PLZ (nur zu migrierende Sätze)
    index: dict[tuple, set[str]] = defaultdict(set)
    for k, z in zeilen.items():
        if z.objekt != "KRED" or k in archiv:
            continue
        for schluessel in abgeleitet[k][2]:
            index[schluessel].add(k)
    kl: dict[str, set[str]] = defaultdict(set)
    for k, z in zeilen.items():
        if z.objekt != "DEBI" or k in archiv:
            continue
        for schluessel in abgeleitet[k][2]:
            for kred in index.get(schluessel, ()):
                kz = zeilen[kred]
                if z.verknuepft == kz.nr or kz.verknuepft == z.nr:
                    continue
                kl[k].add(kred)
                kl[kred].add(k)
    # Nummernkonflikt: gleiche Nummer bei Debitor und Kreditor, nicht verknüpft, beide zu migrieren
    nk: dict[str, tuple[str, ...]] = {}
    for k, z in zeilen.items():
        if z.objekt == "DEBI" and k not in archiv:
            g = f"KRED:{z.nr}"
            if g in zeilen and g not in archiv and not (z.verknuepft == z.nr or zeilen[g].verknuepft == z.nr):
                nk[k], nk[g] = (g,), (k,)
    # Verknüpfung beidseitig?
    vok: dict[str, bool] = {}
    paare = []
    for k, z in zeilen.items():
        if not z.verknuepft:
            continue
        gegen = zeilen.get(f"{'KRED' if z.objekt == 'DEBI' else 'DEBI'}:{z.verknuepft}")
        vok[k] = bool(gegen is not None and gegen.verknuepft == z.nr)
        if vok[k] and z.objekt == "DEBI":
            paare.append((k, gegen.schluessel))
    bank: dict[str, date] = {}
    if aenderungen is not None and len(aenderungen):
        for s, datum in _bankaenderungen(aenderungen):
            if stichtag - timedelta(days=BANKAENDERUNG_TAGE) < datum <= stichtag:
                bank[s] = max(bank.get(s, datum), datum)
    return Kontext(stichtag, grenze, archiv, dub, {k: (s, tuple(sorted(set(p)))) for k, (s, p) in dmax.items()},
                   gleiche_iban, gleiche_ust, {k: tuple(sorted(v)) for k, v in kl.items()}, nk, vok, bank, paare,
                   zeilen, frozenset(s for s, a in abgeleitet.items() if a[0]), inhalte)


_BANK_CACHE: dict[int, list[tuple[str, date]]] = {}


def _bankaenderungen(aenderungen: pd.DataFrame) -> list[tuple[str, date]]:
    """IBAN-Änderungen (Schlüssel, Datum) – je Protokoll-DataFrame einmal ermittelt."""
    schluessel = id(aenderungen)
    if schluessel not in _BANK_CACHE:
        a = aenderungen[aenderungen.feld == "iban"]
        _BANK_CACHE.clear()
        _BANK_CACHE[schluessel] = [(f"{o}:{n}", d) for o, n, d in zip(a.objekt, a.nr, a.datum, strict=True)]
    return _BANK_CACHE[schluessel]


def _kl_schluessel(z) -> list[tuple]:
    s = []
    if z.ust_id and pz.ust_format_gueltig(z.ust_id):
        s.append(("ust", pz.ust_normal(z.ust_id)))
    if z.iban and pz.iban_gueltig(z.iban):
        s.append(("iban", pz.iban_normal(z.iban)))
    if z.name1 and z.plz:
        s.append(("name_plz", name_normal(z.name1), z.plz.strip()))
    return s


Ergebnis = bool | None  # True = verletzt, False = bestanden, None = nicht anwendbar


def _pflicht(z, k: Kontext, feld: str) -> Ergebnis:
    return not str(getattr(z, feld) or "").strip()


def _pflicht_wenn(z, k: Kontext, feld: str, wenn: str) -> Ergebnis:
    return None if not getattr(z, wenn) else _pflicht(z, k, feld)


def _ust_fehlt_eu(z, k: Kontext) -> Ergebnis:
    if z.land not in pz.EU_LAENDER or z.land == "DE" or z.ktogr in ("ZMIT", "DCPD", "KCPD"):
        return None
    return not z.ust_id


def _ust_fehlt_inland(z, k: Kontext) -> Ergebnis:
    if z.land != "DE" or z.ktogr in ("ZMIT", "DCPD", "KCPD") or not ist_gesellschaft(z.name1):
        return None
    return not z.ust_id


def _bank_fehlt(z, k: Kontext) -> Ergebnis:
    return None if z.ktogr == "KCPD" else not z.iban


def _iban_land(z, k: Kontext) -> Ergebnis:
    return None if not z.iban else not pz.iban_laendercode_bekannt(z.iban)


def _iban_laenge(z, k: Kontext) -> Ergebnis:
    return None if not z.iban or not pz.iban_laendercode_bekannt(z.iban) else not pz.iban_laenge_gueltig(z.iban)


def _iban_pruefziffer(z, k: Kontext) -> Ergebnis:
    return None if not z.iban or not pz.iban_laenge_gueltig(z.iban) else not pz.iban_pruefsumme_gueltig(z.iban)


def _iban_blz(z, k: Kontext) -> Ergebnis:
    if not z.iban or not z.bankl or not pz.iban_gueltig(z.iban) or not pz.iban_normal(z.iban).startswith("DE"):
        return None
    return pz.iban_de_blz(z.iban) != z.bankl


def _ust_format(z, k: Kontext) -> Ergebnis:
    return None if not z.ust_id else not pz.ust_format_gueltig(z.ust_id)


def _ust_de_pruefziffer(z, k: Kontext) -> Ergebnis:
    u = pz.ust_normal(z.ust_id)
    return None if not u.startswith("DE") or not pz.ust_format_gueltig(u) else not pz.ust_id_de_gueltig(u)


def _plz_format(z, k: Kontext) -> Ergebnis:
    if not z.plz:
        return None
    ok = pz.plz_gueltig(z.plz, z.land)
    return None if ok is None else not ok


def _email(z, k: Kontext) -> Ergebnis:
    return None if not z.email else not pz.email_gueltig(z.email)


_WERTEBEREICHE = {"SPRACHEN": pz.SPRACHEN, "ZAHLUNGSBEDINGUNGEN": set(ZAHLUNGSBEDINGUNGEN), "LAENDER": pz.LAENDER}


def _wertebereich(z, k: Kontext, feld: str, werte: str) -> Ergebnis:
    wert = getattr(z, feld)
    return None if not wert else wert not in _WERTEBEREICHE[werte]


def _telefon(z, k: Kontext) -> Ergebnis:
    return None if not z.telefon else not pz.telefon_gueltig(z.telefon)


def _bic(z, k: Kontext) -> Ergebnis:
    return None if not z.swift else not pz.bic_gueltig(z.swift)


def _injektion(z, k: Kontext) -> Ergebnis:
    return any(INJEKTIONSMUSTER.search(str(t or "")) for t in (z.name1, z.name2, z.sortl, z.strasse))


def _dublette(z, k: Kontext, stufe: str) -> Ergebnis:
    if z.loevm == "X":
        return None
    score = k.dubletten_max.get(z.schluessel, (0.0, ()))[0]
    if stufe == "hoch":
        return score >= SCHWELLE_SEHR_WAHRSCHEINLICH
    return SCHWELLE_PRUEFEN <= score < SCHWELLE_SEHR_WAHRSCHEINLICH


def _gleicher_wert(z, k: Kontext, feld: str) -> Ergebnis:
    wert = getattr(z, feld)
    if z.loevm == "X" or not wert or (feld == "iban" and z.schluessel not in k.iban_gueltig):
        return None
    return z.schluessel in (k.gleiche_iban if feld == "iban" else k.gleiche_ust)


def _kunde_lieferant(z, k: Kontext) -> Ergebnis:
    return None if z.schluessel in k.archiv else z.schluessel in k.kunde_lieferant


def _region_plz(z, k: Kontext) -> Ergebnis:
    if not z.bzirk or not z.land or (z.land == "DE" and not pz.plz_gueltig(z.plz, "DE")):
        return None
    soll = erwartete_region(z.land, z.plz)
    return None if soll is None else soll != z.bzirk


def _bp_zuordnung(z, k: Kontext) -> Ergebnis:
    if not z.ktogr:
        return None
    kg = KONTENGRUPPE.get((z.objekt, z.ktogr))
    return kg is None or kg.bp_gruppierung is None


def _ust_land(z, k: Kontext) -> Ergebnis:
    if not z.ust_id or not z.land or z.land not in pz.LAENDER or not pz.ust_format_gueltig(z.ust_id):
        return None
    return pz.ust_land(z.ust_id) != z.land


def _bank_land(z, k: Kontext) -> Ergebnis:
    if not z.iban or not z.banks or not pz.iban_laendercode_bekannt(z.iban):
        return None
    return pz.iban_normal(z.iban)[:2] != z.banks


def _nummernkreis(z, k: Kontext) -> Ergebnis:
    ok = nummer_im_kreis(z.objekt, z.ktogr, z.nr) if z.ktogr else None
    if ok is None or (KONTENGRUPPE[(z.objekt, z.ktogr)].bp_gruppierung is None):
        return None
    return not ok


def _nummernkonflikt(z, k: Kontext) -> Ergebnis:
    return None if z.schluessel in k.archiv else z.schluessel in k.nummernkonflikt


def _verknuepfung(z, k: Kontext) -> Ergebnis:
    return None if not z.verknuepft else not k.verknuepfung_ok.get(z.schluessel, False)


def _loevm_op(z, k: Kontext) -> Ergebnis:
    return None if z.loevm != "X" else z.op == "X"


def _inaktiv(z, k: Kontext) -> Ergebnis:
    if z.letzte_buchung is None:
        return None
    return z.letzte_buchung < k.archivgrenze and z.loevm != "X"


def _nie_bebucht(z, k: Kontext) -> Ergebnis:
    if z.letzte_buchung is not None or z.op == "X":
        return None
    return z.erdat < k.archivgrenze and z.loevm != "X"


def _gesperrt_ohne_op(z, k: Kontext) -> Ergebnis:
    if z.sperr != "X" or z.loevm == "X":
        return None
    lb = z.letzte_buchung
    if (lb is not None and lb < k.archivgrenze) or (lb is None and z.erdat < k.archivgrenze):
        return None  # bereits über A01/A02 erfasst
    return z.op != "X"


def _bankaenderung(z, k: Kontext) -> Ergebnis:
    return None if not z.iban else z.schluessel in k.bankaenderung


#: Prüfungen, deren Ergebnis vom Kontext (andere Sätze, Stichtag, Protokoll) abhängt – alle übrigen hängen nur vom
#: Satz selbst ab und werden je Satzinhalt nur einmal ausgewertet (inkrementelle Monatsstände).
KONTEXT_PRUEFUNGEN = frozenset({"dublette", "gleicher_wert", "kunde_lieferant", "nummernkonflikt", "verknuepfung",
                                "inaktiv", "nie_bebucht", "gesperrt_ohne_op", "bankaenderung"})

PRUEFUNGEN: dict[str, Callable[..., Ergebnis]] = {
    "pflicht": _pflicht, "pflicht_wenn": _pflicht_wenn, "ust_fehlt_eu": _ust_fehlt_eu,
    "ust_fehlt_inland": _ust_fehlt_inland, "bank_fehlt": _bank_fehlt, "iban_land": _iban_land,
    "iban_laenge": _iban_laenge, "iban_pruefziffer": _iban_pruefziffer, "iban_blz": _iban_blz,
    "ust_format": _ust_format, "ust_de_pruefziffer": _ust_de_pruefziffer, "plz_format": _plz_format, "email": _email,
    "wertebereich": _wertebereich, "telefon": _telefon, "bic": _bic, "injektion": _injektion, "dublette": _dublette,
    "gleicher_wert": _gleicher_wert, "kunde_lieferant": _kunde_lieferant, "region_plz": _region_plz,
    "bp_zuordnung": _bp_zuordnung, "ust_land": _ust_land, "bank_land": _bank_land, "nummernkreis": _nummernkreis,
    "nummernkonflikt": _nummernkonflikt, "verknuepfung": _verknuepfung, "loevm_op": _loevm_op, "inaktiv": _inaktiv,
    "nie_bebucht": _nie_bebucht, "gesperrt_ohne_op": _gesperrt_ohne_op, "bankaenderung": _bankaenderung,
}


_PARAM: dict[str, dict] = {}


#: Kontextprüfungen mit spaltenweiser Fassung (numpy) – gleiche Semantik wie die Einzelfunktionen oben.
VEKTOR_PRUEFUNGEN = frozenset({"dublette", "gleicher_wert", "kunde_lieferant", "nummernkonflikt", "verknuepfung",
                               "inaktiv", "nie_bebucht", "gesperrt_ohne_op", "bankaenderung"})


def _spalten(zl: list, k: Kontext) -> dict[str, np.ndarray]:
    """Satzmerkmale eines Stands als Arrays (je Kontext einmal gebildet)."""
    sp = getattr(k, "_spalten", None)
    if sp is not None and len(sp["schluessel"]) == len(zl):
        return sp
    keine = -1
    sp = {
        "schluessel": [z.schluessel for z in zl],
        "objekt": np.array([z.objekt for z in zl], dtype=object),
        "loevm": np.array([z.loevm == "X" for z in zl]),
        "op": np.array([z.op == "X" for z in zl]),
        "sperr": np.array([z.sperr == "X" for z in zl]),
        "lb": np.array([z.letzte_buchung.toordinal() if isinstance(z.letzte_buchung, date) else keine for z in zl]),
        "erdat": np.array([z.erdat.toordinal() for z in zl]),
        "iban": np.array([bool(z.iban) for z in zl]),
        "ust_id": np.array([bool(z.ust_id) for z in zl]),
        "verknuepft": np.array([bool(z.verknuepft) for z in zl]),
    }
    object.__setattr__(k, "_spalten", sp)
    return sp


def _in(schluessel: list[str], menge) -> np.ndarray:
    return np.fromiter((s in menge for s in schluessel), dtype=bool, count=len(schluessel))


def kontext_vektor(r: Regel, zl: list, k: Kontext) -> tuple[np.ndarray, np.ndarray]:
    """(anwendbar, verletzt) einer Kontextregel für alle Sätze eines Stands."""
    sp = _spalten(zl, k)
    s, n = sp["schluessel"], len(zl)
    grenze = k.archivgrenze.toordinal()
    lb_da = sp["lb"] >= 0
    lb_alt = lb_da & (sp["lb"] < grenze)
    art, param = r.pruefung, r.param
    if art == "dublette":
        anw = ~sp["loevm"]
        score = np.fromiter((k.dubletten_max.get(x, (0.0,))[0] for x in s), dtype=float, count=n)
        verl = (score >= SCHWELLE_SEHR_WAHRSCHEINLICH) if param["stufe"] == "hoch" else (
            (score >= SCHWELLE_PRUEFEN) & (score < SCHWELLE_SEHR_WAHRSCHEINLICH))
    elif art == "gleicher_wert":
        feld = param["feld"]
        anw = ~sp["loevm"] & sp[feld]
        if feld == "iban":
            anw &= _in(s, k.iban_gueltig)
        verl = _in(s, k.gleiche_iban if feld == "iban" else k.gleiche_ust)
    elif art in ("kunde_lieferant", "nummernkonflikt"):
        anw = ~_in(s, k.archiv)
        verl = _in(s, k.kunde_lieferant if art == "kunde_lieferant" else k.nummernkonflikt)
    elif art == "verknuepfung":
        anw = sp["verknuepft"]
        verl = ~np.fromiter((k.verknuepfung_ok.get(x, False) for x in s), dtype=bool, count=n)
    elif art == "inaktiv":
        anw = lb_da
        verl = lb_alt & ~sp["loevm"]
    elif art == "nie_bebucht":
        anw = ~lb_da & ~sp["op"]
        verl = (sp["erdat"] < grenze) & ~sp["loevm"]
    elif art == "gesperrt_ohne_op":
        bereits = lb_alt | (~lb_da & (sp["erdat"] < grenze))
        anw = sp["sperr"] & ~sp["loevm"] & ~bereits
        verl = ~sp["op"]
    elif art == "bankaenderung":
        anw = sp["iban"]
        verl = _in(s, k.bankaenderung)
    else:  # pragma: no cover – nur über VEKTOR_PRUEFUNGEN erreichbar
        raise KeyError(art)
    if r.objekt != "beide":
        anw = anw & (sp["objekt"] == r.objekt)
    return anw, verl & anw


def regel_anwenden(regel: Regel, z, k: Kontext) -> Ergebnis:
    if regel.objekt != "beide" and regel.objekt != z.objekt:
        return None
    param = _PARAM.get(regel.id)
    if param is None:
        param = _PARAM[regel.id] = regel.param
    return PRUEFUNGEN[regel.pruefung](z, k, **param)


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Auswertung
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════


@dataclass
class Pruefergebnis:
    stichtag: date
    befunde: pd.DataFrame  # je Verletzung: regel, schluessel, objekt, nr, dimension, schweregrad, wert, partner
    zaehler: pd.DataFrame  # je Regel: anwendbar, bestanden, verletzt
    dimension_score: dict[str, float]  # in %
    gesamtscore: float
    kontext: Kontext
    saetze: int
    zaehler_objekt: pd.DataFrame | None = None  # je Regel und Satzobjekt: anwendbar, verletzt

    def befunde_von(self, schluessel: str) -> pd.DataFrame:
        return self.befunde[self.befunde.schluessel == schluessel]


def anzeige_wert(regel: Regel, z) -> str:
    """Wert für Befundliste und Beispiele – Bankdaten nur maskiert."""
    if not regel.feld:
        return ""
    wert = str(getattr(z, regel.feld) or "")
    if regel.feld == "iban":
        return pz.iban_maskieren(wert)
    if regel.feld in ("bankn",):
        return f"•••{wert[-3:]}" if wert else ""
    return wert


def _partner(regel: Regel, z, k: Kontext) -> tuple[str, ...]:
    if regel.pruefung == "dublette":
        return k.dubletten_max.get(z.schluessel, (0, ()))[1]
    if regel.pruefung == "gleicher_wert":
        return (k.gleiche_iban if regel.feld == "iban" else k.gleiche_ust).get(z.schluessel, ())
    if regel.pruefung == "kunde_lieferant":
        return k.kunde_lieferant.get(z.schluessel, ())
    if regel.pruefung == "nummernkonflikt":
        return k.nummernkonflikt.get(z.schluessel, ())
    return ()


def pruefe(df: pd.DataFrame, stichtag: date, aenderungen: pd.DataFrame | None = None,
           dubletten: Dublettenergebnis | None = None, regeln: tuple[Regel, ...] = REGELN,
           speicher: Rechenspeicher | None = None) -> Pruefergebnis:
    """Alle Regeln auf alle Sätze anwenden (deterministisch, offline)."""
    k = baue_kontext(df, stichtag, aenderungen, dubletten, speicher)
    rein = [r for r in regeln if r.pruefung not in KONTEXT_PRUEFUNGEN]
    kontextabh = [r for r in regeln if r.pruefung in KONTEXT_PRUEFUNGEN]
    gebunden = [(r, r.objekt, PRUEFUNGEN[r.pruefung], r.param) for r in kontextabh]
    vektor = [(j, g) for j, g in enumerate(gebunden) if g[0].pruefung in VEKTOR_PRUEFUNGEN]
    skalar = [(j, g) for j, g in enumerate(gebunden) if g[0].pruefung not in VEKTOR_PRUEFUNGEN]
    cache = speicher.regel if speicher is not None else {}
    befunde = []
    n = len(df)
    anw_rein, verl_rein = np.zeros((n, len(rein)), dtype=bool), np.zeros((n, len(rein)), dtype=bool)
    anw_ktx, verl_ktx = np.zeros((n, len(kontextabh)), dtype=bool), np.zeros((n, len(kontextabh)), dtype=bool)
    ist_debi = np.zeros(n, dtype=bool)

    def befund(r: Regel, z) -> None:
        befunde.append({"regel": r.id, "schluessel": z.schluessel, "objekt": z.objekt, "nr": z.nr, "name": z.name1,
                        "dimension": r.dimension, "schweregrad": r.schweregrad, "sap_feld": r.sap_feld,
                        "wert": anzeige_wert(r, z), "partner": _partner(r, z, k), "korrektur": r.korrektur})

    inhalte = k.inhalte if speicher is not None else k.zeilen
    for i, (s, z) in enumerate(k.zeilen.items()):  # gleiche Reihenfolge wie df (Kontext aus derselben Iteration)
        ist_debi[i] = z.objekt == "DEBI"
        inhalt = inhalte[s]
        erg = cache.get(inhalt)
        if erg is None:  # rein satzbezogene Regeln je Satzinhalt nur einmal auswerten
            werte = [regel_anwenden(r, z, k) for r in rein]
            erg = cache[inhalt] = (np.array([e is not None for e in werte]), np.array([bool(e) for e in werte]),
                              tuple(j for j, e in enumerate(werte) if e))
        anw_rein[i], verl_rein[i] = erg[0], erg[1]
        for j in erg[2]:
            befund(rein[j], z)
        for j, (r, objekt, fn, param) in skalar:  # nur Kontextprüfungen ohne Vektorfassung (derzeit keine)
            e = None if objekt != "beide" and objekt != z.objekt else fn(z, k, **param)
            if e is not None:
                anw_ktx[i, j] = True
                if e:
                    verl_ktx[i, j] = True
                    befund(r, z)
    if vektor:  # Kontextprüfungen spaltenweise (gleiches Ergebnis wie je Satz, Test test_kontext_vektor_gleich_skalar)
        zl = list(k.zeilen.values())
        for j, (r, _, _, _) in vektor:
            anw_ktx[:, j], verl_ktx[:, j] = kontext_vektor(r, zl, k)
            for i in np.flatnonzero(verl_ktx[:, j]):
                befund(r, zl[i])
    zaehler = {}
    for maske, o in ((ist_debi, "DEBI"), (~ist_debi, "KRED")):
        for liste, anw, verl in ((rein, anw_rein, verl_rein), (kontextabh, anw_ktx, verl_ktx)):
            a_sum, v_sum = anw[maske].sum(axis=0), verl[maske].sum(axis=0)
            for j, r in enumerate(liste):
                zaehler[(r.id, o)] = [int(a_sum[j]), int(v_sum[j])]
    befunde.sort(key=lambda b: (b["schluessel"], b["regel"]))
    zo = pd.DataFrame([{"regel": r.id, "satzobjekt": o, "anwendbar": zaehler[(r.id, o)][0],
                        "verletzt": zaehler[(r.id, o)][1]} for r in regeln for o in ("DEBI", "KRED")])
    zt, score, gesamt = verdichte(zo, regeln)
    spalten = ["regel", "schluessel", "objekt", "nr", "name", "dimension", "schweregrad", "sap_feld", "wert", "partner",
               "korrektur"]
    # object statt Arrow-Strings: schneller aufgebaut und iteriert (zwölf Monatsstände), Inhalt identisch
    return Pruefergebnis(stichtag, pd.DataFrame(befunde, columns=spalten, dtype=object), zt, score, gesamt, k, len(df),
                         zo)


def verdichte(zo: pd.DataFrame, regeln: tuple[Regel, ...] = REGELN, objekt: str = "Alle"):
    """Zähler je Regel, Score je Dimension und Gesamtscore (optional nur für ein Objekt)."""
    summe: dict[str, list[int]] = {r.id: [0, 0] for r in regeln}
    for rid, o, anw, verl in zip(zo.regel, zo.satzobjekt, zo.anwendbar, zo.verletzt, strict=True):
        if objekt in ("Alle", o):
            summe[rid][0] += int(anw)
            summe[rid][1] += int(verl)
    zt = pd.DataFrame([{"regel": r.id, "dimension": r.dimension, "schweregrad": r.schweregrad, "objekt": r.objekt,
                        "beschreibung": r.beschreibung, "anwendbar": summe[r.id][0], "verletzt": summe[r.id][1],
                        "bestanden": summe[r.id][0] - summe[r.id][1]} for r in regeln])
    score = {}
    for d in DIMENSIONEN:
        anw = sum(summe[r.id][0] for r in regeln if r.dimension == d)
        best = sum(summe[r.id][0] - summe[r.id][1] for r in regeln if r.dimension == d)
        score[d] = round(100 * best / anw, 2) if anw else 100.0
    return zt, score, round(sum(score.values()) / len(score), 2)
