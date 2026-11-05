"""Lesen der Stammdaten aus der SQLite-Datenbank (SAP-ECC-Exportstil) und Rekonstruktion von Monatsständen.

Die Prüf-Engines arbeiten auf einer **flachen Sicht** je Satz (eine Zeile je Debitor bzw. Kreditor), die aus den
Tabellen KNA1/KNB1/KNVV/KNBK bzw. LFA1/LFB1/LFBK, ADRC und ZDG_VERKEHR zusammengesetzt wird. Monatsstände entstehen
aus dem aktuellen Stand, indem alle späteren Änderungen aus CDHDR/CDPOS rückwärts zurückgenommen und später angelegte
Sätze ausgeblendet werden. Bankfelder stehen im Protokoll nur maskiert und werden deshalb nicht zurückgesetzt
(das Protokoll enthält ausschließlich Bankänderungen von gültig nach gültig – Test ``test_protokoll_bank_gueltig``).
"""

from __future__ import annotations

import sqlite3
from bisect import bisect_right
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import db_pfad

#: Flaches Feld → (Tabelle Debitor, Tabelle Kreditor, SAP-Feldname; „A|B“ = Debitor A, Kreditor B)
FELD_SAP: dict[str, tuple[str, str, str]] = {
    "name1": ("KNA1", "LFA1", "NAME1"), "name2": ("KNA1", "LFA1", "NAME2"), "sortl": ("KNA1", "LFA1", "SORTL"),
    "land": ("KNA1", "LFA1", "LAND1"), "sprache": ("KNA1", "LFA1", "SPRAS"), "ust_id": ("KNA1", "LFA1", "STCEG"),
    "verknuepft": ("KNA1", "LFA1", "LIFNR|KUNNR"), "loevm": ("KNA1", "LFA1", "LOEVM"),
    "sperr": ("KNA1", "LFA1", "SPERR"), "ktogr": ("KNA1", "LFA1", "KTOKD|KTOKK"), "strasse": ("ADRC", "ADRC", "STREET"),
    "hausnr": ("ADRC", "ADRC", "HOUSE_NUM1"), "plz": ("ADRC", "ADRC", "POST_CODE1"), "ort": ("ADRC", "ADRC", "CITY1"),
    "telefon": ("ADRC", "ADRC", "TEL_NUMBER"), "email": ("ADRC", "ADRC", "SMTP_ADDR"),
    "zterm": ("KNB1", "LFB1", "ZTERM"), "akont": ("KNB1", "LFB1", "AKONT"), "bzirk": ("KNVV", "KNVV", "BZIRK"),
    "iban": ("KNBK", "LFBK", "IBAN"), "bankl": ("KNBK", "LFBK", "BANKL"), "bankn": ("KNBK", "LFBK", "BANKN"),
    "banks": ("KNBK", "LFBK", "BANKS"), "swift": ("KNBK", "LFBK", "SWIFT"),
}
#: Felder, die im Änderungsprotokoll nur maskiert stehen (Datenminimierung) – werden nicht zurückgesetzt.
MASKIERTE_FELDER = frozenset({"iban", "bankn"})
SPALTEN = ["schluessel", "objekt", "nr", "ktogr", "name1", "name2", "sortl", "strasse", "hausnr", "plz", "ort", "land",
           "sprache", "telefon", "email", "ust_id", "akont", "zterm", "bzirk", "banks", "bankl", "bankn", "iban",
           "swift", "loevm", "sperr", "erdat", "ernam", "letzte_buchung", "op", "verknuepft", "branche", "anz_belege",
           "quelle"]


def sap_feld(objekt: str, feld: str) -> tuple[str, str]:
    """(Tabelle, Feld) im SAP-Stil für ein flaches Feld."""
    deb, kred, name = FELD_SAP[feld]
    if "|" in name:
        name = name.split("|")[0 if objekt == "DEBI" else 1]
    return (deb if objekt == "DEBI" else kred), name


_SAP_ZU_FELD = {(sap_feld(o, f)[0], sap_feld(o, f)[1]): f for f in FELD_SAP for o in ("DEBI", "KRED")}


@dataclass
class Stammdaten:
    """Aktueller Stand und Änderungsprotokoll."""

    saetze: pd.DataFrame  # flache Sicht, Datumsfelder als datetime.date
    aenderungen: pd.DataFrame  # CDHDR ⋈ CDPOS mit flachem Feldnamen (Spalte „feld“)
    buchungsdaten: pd.DataFrame  # schluessel, objekt, nr, budat – Buchungsdaten ohne Beträge
    meta: dict[str, str]
    stichtag: date

    def index_cache(self) -> dict:
        """Einmalig vorbereitete Hilfsstrukturen für schnelle Monatsstände (Ordinalzahlen statt Datumsobjekten)."""
        if not hasattr(self, "_idx"):
            a = self.aenderungen[self.aenderungen.feld.notna() & ~self.aenderungen.feld.isin(MASKIERTE_FELDER)]
            b: dict[str, tuple[list[int], list[date]]] = {}
            for s, d in zip(self.buchungsdaten.schluessel, self.buchungsdaten.budat, strict=True):
                b.setdefault(s, ([], []))
                b[s][0].append(d.toordinal())
                b[s][1].append(d)
            self._idx = {"erdat": np.array([d.toordinal() for d in self.saetze.erdat]), "aend": a,
                         "aend_datum": np.array([d.toordinal() for d in a.datum]), "buchungen": b}
        return self._idx

    def stand(self, stichtag: date | None = None) -> pd.DataFrame:
        """Flache Sicht zum Monatsende ``stichtag`` (None = aktueller Stand)."""
        if stichtag is None or stichtag >= self.stichtag:
            return self.saetze.copy()
        return rekonstruiere(self, stichtag)


def lade(pfad: Path | str | None = None) -> Stammdaten:
    pfad = Path(pfad or db_pfad())
    if not pfad.exists():
        raise FileNotFoundError(f"Datenbank fehlt: {pfad} – zuerst `python run_agent.py daten` ausführen.")
    with closing(sqlite3.connect(pfad)) as con:
        deb = pd.read_sql(
            """SELECT 'DEBI' AS objekt, k.KUNNR AS nr, k.KTOKD AS ktogr, k.NAME1 AS name1, k.NAME2 AS name2,
                      k.SORTL AS sortl, a.STREET AS strasse, a.HOUSE_NUM1 AS hausnr, a.POST_CODE1 AS plz,
                      a.CITY1 AS ort, k.LAND1 AS land, k.SPRAS AS sprache, a.TEL_NUMBER AS telefon,
                      a.SMTP_ADDR AS email, k.STCEG AS ust_id, b.AKONT AS akont, b.ZTERM AS zterm, v.BZIRK AS bzirk,
                      bk.BANKS AS banks, bk.BANKL AS bankl, bk.BANKN AS bankn, bk.IBAN AS iban, bk.SWIFT AS swift,
                      k.LOEVM AS loevm, k.SPERR AS sperr, k.ERDAT AS erdat, k.ERNAM AS ernam,
                      z.LETZTE_BUCHUNG AS letzte_buchung, z.OP_VORHANDEN AS op, k.LIFNR AS verknuepft,
                      k.BRSCH AS branche, z.ANZ_BELEGE_2024_2026 AS anz_belege, z.QUELLE AS quelle
               FROM KNA1 k JOIN ADRC a ON a.ADDRNUMBER = k.ADRNR
               LEFT JOIN KNB1 b ON b.KUNNR = k.KUNNR LEFT JOIN KNVV v ON v.KUNNR = k.KUNNR
               LEFT JOIN KNBK bk ON bk.KUNNR = k.KUNNR
               LEFT JOIN ZDG_VERKEHR z ON z.OBJEKT = 'DEBI' AND z.NR = k.KUNNR""", con)
        kred = pd.read_sql(
            """SELECT 'KRED' AS objekt, l.LIFNR AS nr, l.KTOKK AS ktogr, l.NAME1 AS name1, l.NAME2 AS name2,
                      l.SORTL AS sortl, a.STREET AS strasse, a.HOUSE_NUM1 AS hausnr, a.POST_CODE1 AS plz,
                      a.CITY1 AS ort, l.LAND1 AS land, l.SPRAS AS sprache, a.TEL_NUMBER AS telefon,
                      a.SMTP_ADDR AS email, l.STCEG AS ust_id, b.AKONT AS akont, b.ZTERM AS zterm, '' AS bzirk,
                      bk.BANKS AS banks, bk.BANKL AS bankl, bk.BANKN AS bankn, bk.IBAN AS iban, bk.SWIFT AS swift,
                      l.LOEVM AS loevm, l.SPERR AS sperr, l.ERDAT AS erdat, l.ERNAM AS ernam,
                      z.LETZTE_BUCHUNG AS letzte_buchung, z.OP_VORHANDEN AS op, l.KUNNR AS verknuepft,
                      '' AS branche, z.ANZ_BELEGE_2024_2026 AS anz_belege, z.QUELLE AS quelle
               FROM LFA1 l JOIN ADRC a ON a.ADDRNUMBER = l.ADRNR
               LEFT JOIN LFB1 b ON b.LIFNR = l.LIFNR LEFT JOIN LFBK bk ON bk.LIFNR = l.LIFNR
               LEFT JOIN ZDG_VERKEHR z ON z.OBJEKT = 'KRED' AND z.NR = l.LIFNR""", con)
        aend = pd.read_sql(
            """SELECT h.OBJECTCLAS AS objekt, h.OBJECTID AS nr, h.CHANGENR AS changenr, h.USERNAME AS benutzer,
                      h.UDATE AS datum, h.TCODE AS tcode, h.CHANGE_IND AS kennz, p.TABNAME AS tabelle,
                      p.FNAME AS sap_feld, p.VALUE_OLD AS alt, p.VALUE_NEW AS neu
               FROM CDHDR h LEFT JOIN CDPOS p ON p.OBJECTCLAS = h.OBJECTCLAS AND p.OBJECTID = h.OBJECTID
                    AND p.CHANGENR = h.CHANGENR
               ORDER BY h.UDATE, h.CHANGENR""", con)
        buchungen = pd.read_sql("SELECT OBJEKT AS objekt, NR AS nr, BUDAT AS budat FROM ZDG_BUCHUNGSDATEN", con)
        meta = dict(con.execute("SELECT SCHLUESSEL, WERT FROM ZDG_META").fetchall())
    saetze = pd.concat([deb, kred], ignore_index=True)
    anz = saetze.pop("anz_belege")
    saetze = saetze.fillna("")
    saetze["anz_belege"] = pd.Series([None if pd.isna(x) else int(x) for x in anz], dtype=object)
    saetze.insert(0, "schluessel", saetze.objekt + ":" + saetze.nr)
    saetze["erdat"] = saetze.erdat.map(date.fromisoformat)
    saetze["letzte_buchung"] = saetze.letzte_buchung.map(lambda x: date.fromisoformat(x) if x else None)
    aend["datum"] = aend.datum.map(date.fromisoformat)
    aend["feld"] = [_SAP_ZU_FELD.get((t, f)) if t else None for t, f in zip(aend.tabelle, aend.sap_feld, strict=True)]
    aend.insert(0, "schluessel", aend.objekt + ":" + aend.nr)
    aend = aend.astype(object).where(aend.notna(), None)
    aend["alt"] = aend.alt.fillna("")
    aend["neu"] = aend.neu.fillna("")
    buchungen["budat"] = buchungen.budat.map(date.fromisoformat)
    buchungen.insert(0, "schluessel", buchungen.objekt + ":" + buchungen.nr)
    buchungen = buchungen.astype(object)
    # Objekt-Datentyp statt Arrow-Strings: zeilenweise Prüfungen (itertuples) sind damit um ein Vielfaches schneller
    return Stammdaten(saetze[SPALTEN].astype(object).reset_index(drop=True), aend,
                      buchungen.sort_values(["schluessel", "budat"]), meta,
                      date.fromisoformat(meta.get("STICHTAG", "2026-09-30")))


def rekonstruiere(daten: Stammdaten, stichtag: date) -> pd.DataFrame:
    """Stand zum ``stichtag`` – vektorisiert:

    1. Sätze mit Anlagedatum nach dem Stichtag ausblenden.
    2. Je (Satz, Feld) die *erste* Änderung nach dem Stichtag suchen – ihr Altwert ist der Wert am Stichtag.
    3. Letzte Buchung = jüngstes Buchungsdatum ≤ Stichtag (ZDG_BUCHUNGSDATEN), sonst unverändert bzw. leer.
    """
    idx = daten.index_cache()
    tag = stichtag.toordinal()
    df = daten.saetze[idx["erdat"] <= tag]
    spaeter = idx["aend"][idx["aend_datum"] > tag]
    erste = spaeter.drop_duplicates(["schluessel", "feld"], keep="first")
    werte = {s: {} for s in erste.schluessel}
    for s, f, alt in zip(erste.schluessel, erste.feld, erste.alt, strict=True):
        werte[s][f] = alt
    lb = {}
    for s, (daten_ord, daten_d) in idx["buchungen"].items():
        pos = bisect_right(daten_ord, tag)
        lb[s] = daten_d[pos - 1] if pos else None
    spalten = {c: df[c].tolist() for c in df.columns}
    schl = spalten["schluessel"]
    for i, s in enumerate(schl):
        if s in werte:
            for f, alt in werte[s].items():
                spalten[f][i] = alt
        if s in lb:
            spalten["letzte_buchung"][i] = lb[s]
        elif spalten["letzte_buchung"][i] is not None and spalten["letzte_buchung"][i] > stichtag:
            spalten["letzte_buchung"][i] = None
    return pd.DataFrame(spalten, columns=df.columns, dtype=object)


def letzte_aenderung(daten: Stammdaten, stichtag: date | None = None) -> dict[str, date]:
    """Jüngste Änderung je Satz (CDHDR, inkl. Anlage) bis zum Stichtag; ohne Protokoll = Anlagedatum."""
    a = daten.aenderungen
    if stichtag is not None:
        a = a[a.datum <= stichtag]
    juengste = a.groupby(a.objekt + ":" + a.nr).datum.max().to_dict()
    return {s: juengste.get(s, e) for s, e in zip(daten.saetze.schluessel, daten.saetze.erdat, strict=True)}
