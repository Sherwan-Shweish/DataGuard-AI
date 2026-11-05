"""Deterministische Formal- und Prüfziffernprüfungen – offline, ohne externe Bibliothek.

* IBAN nach ISO 13616 (Prüfziffern Mod 97 nach ISO 7064), Länge je Land laut SWIFT-IBAN-Registry (Stand prüfen),
  für Deutschland zusätzlich Abgleich der Bankleitzahl im IBAN mit dem Stammdatum BLZ.
* USt-IdNr.: Formatprüfung je EU-Land; für DE zusätzlich die Prüfziffer nach ISO 7064 MOD 11,10 – dieselbe Logik
  wie FlowAudit-AI ``src/einvoice_parser.ust_id_de_gueltig`` (nachgebaut, nicht importiert; Gleichheit per Test).
* PLZ je Land, E-Mail-Syntax, BIC-Format, Telefonformat.

Alle Funktionen prüfen nur die *formale* Richtigkeit. Ob eine IBAN existiert oder eine USt-IdNr. vergeben ist,
bestätigen erst Bank bzw. BZSt/VIES (optionaler, standardmäßig ausgeschalteter Online-Schritt).
"""

from __future__ import annotations

import re

# ── IBAN ────────────────────────────────────────────────────────────────────────────────────────────────────────
#: IBAN-Länge je Land (Auszug SWIFT IBAN Registry; Stand prüfen). Länder außerhalb der Liste gelten als unbekannt.
IBAN_LAENGE: dict[str, int] = {
    "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20, "ES": 24, "FI": 18,
    "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21,
    "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24,
}
_IBAN_ZEICHEN = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]+")


def iban_normal(iban: str | None) -> str:
    """Leerzeichen entfernen, Großschreibung."""
    return (iban or "").replace(" ", "").upper()


def iban_mod97(iban: str) -> int:
    """Rest nach ISO 7064 Mod 97-10 (gültig = 1)."""
    s = iban_normal(iban)
    umgestellt = s[4:] + s[:4]
    zahl = "".join(str(int(z, 36)) for z in umgestellt)
    return int(zahl) % 97


def iban_laendercode_bekannt(iban: str) -> bool:
    return iban_normal(iban)[:2] in IBAN_LAENGE


def iban_laenge_gueltig(iban: str) -> bool:
    s = iban_normal(iban)
    return iban_laendercode_bekannt(s) and len(s) == IBAN_LAENGE[s[:2]]


def iban_pruefsumme_gueltig(iban: str) -> bool:
    s = iban_normal(iban)
    return bool(_IBAN_ZEICHEN.fullmatch(s)) and iban_mod97(s) == 1


_IBAN_MEMO: dict[str, bool] = {}


def memo_leeren() -> None:
    """Zwischenergebnisse der IBAN-Prüfung verwerfen (zu Beginn jedes Monatsverlaufs)."""
    _IBAN_MEMO.clear()


def iban_gueltig(iban: str) -> bool:
    """Ländercode bekannt, Länge passend, Prüfziffern korrekt."""
    e = _IBAN_MEMO.get(iban)
    if e is None:
        e = _IBAN_MEMO[iban] = iban_laenge_gueltig(iban) and iban_pruefsumme_gueltig(iban)
    return e


def iban_de_blz(iban: str) -> str | None:
    """Bankleitzahl aus einer deutschen IBAN (Stellen 5–12)."""
    s = iban_normal(iban)
    return s[4:12] if s.startswith("DE") and len(s) == 22 else None


def iban_bilden(land: str, bban: str) -> str:
    """IBAN aus Ländercode und BBAN mit korrekten Prüfziffern (ISO 13616)."""
    land = land.upper()
    zahl = "".join(str(int(z, 36)) for z in bban.upper() + land + "00")
    return f"{land}{98 - int(zahl) % 97:02d}{bban.upper()}"


def iban_maskieren(iban: str | None) -> str:
    """Anzeige für Oberfläche, Audit und Export: Land + Prüfziffern und letzte vier Stellen („DE59 •••• 3344“)."""
    s = iban_normal(iban)
    if not s:
        return ""
    if len(s) < 8:
        return "•••• (ungültig)"
    return f"{s[:4]} •••• {s[-4:]}"


# ── USt-IdNr. ───────────────────────────────────────────────────────────────────────────────────────────────────
#: Format der USt-IdNr. je EU-Mitgliedstaat (ohne Prüfziffern außer DE; Stand prüfen – Quelle: EU-Kommission/VIES-FAQ).
UST_FORMATE: dict[str, str] = {
    "AT": r"ATU\d{8}", "BE": r"BE[01]\d{9}", "BG": r"BG\d{9,10}", "CY": r"CY\d{8}[A-Z]", "CZ": r"CZ\d{8,10}",
    "DE": r"DE\d{9}", "DK": r"DK\d{8}", "EE": r"EE\d{9}", "EL": r"EL\d{9}", "ES": r"ES[A-Z0-9]\d{7}[A-Z0-9]",
    "FI": r"FI\d{8}", "FR": r"FR[A-HJ-NP-Z0-9]{2}\d{9}", "HR": r"HR\d{11}", "HU": r"HU\d{8}",
    "IE": r"IE\d{7}[A-W][A-I]?",
    "IT": r"IT\d{11}", "LT": r"LT(\d{9}|\d{12})", "LU": r"LU\d{8}", "LV": r"LV\d{11}", "MT": r"MT\d{8}",
    "NL": r"NL\d{9}B\d{2}", "PL": r"PL\d{10}", "PT": r"PT\d{9}", "RO": r"RO\d{2,10}", "SE": r"SE\d{12}",
    "SI": r"SI\d{8}", "SK": r"SK\d{10}", "XI": r"XI(\d{9}|\d{12})",
}
#: Präfix der USt-IdNr. ↔ ISO-Land der Anschrift (Griechenland nutzt „EL“, Nordirland „XI“).
UST_PRAEFIX_LAND = {"EL": "GR", "XI": "GB"}
EU_LAENDER = frozenset(
    {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU",
     "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}
)
_UST_ID_DE = re.compile(r"DE\d{9}")


def ust_normal(ust_id: str | None) -> str:
    return (ust_id or "").replace(" ", "").replace(".", "").replace("-", "").upper()


def ust_land(ust_id: str) -> str | None:
    """ISO-Land, das zum Präfix einer USt-IdNr. gehört."""
    p = ust_normal(ust_id)[:2]
    if p in UST_FORMATE:
        return UST_PRAEFIX_LAND.get(p, p)
    return None


def ust_format_gueltig(ust_id: str) -> bool:
    s = ust_normal(ust_id)
    muster = UST_FORMATE.get(s[:2])
    return bool(muster and re.fullmatch(muster, s))


def ust_id_de_gueltig(ust_id: str) -> bool:
    """Deutsche USt-IdNr.: Format DE + 9 Ziffern und Prüfziffer nach ISO 7064 MOD 11,10 (Verfahren des BZSt).

    Nachbau von FlowAudit-AI ``src/einvoice_parser.ust_id_de_gueltig`` – gleiche Ergebnisse (Test
    ``test_ust_de_wie_flowaudit``). Prüft nur die formale Richtigkeit, nicht, ob die Nummer vergeben ist.
    """
    uid = ust_id.replace(" ", "").upper()
    if not _UST_ID_DE.fullmatch(uid) or uid[2] == "0":  # erste Ziffer nach „DE“ ist nie 0
        return False
    produkt = 10
    for ziffer in uid[2:10]:
        summe = (int(ziffer) + produkt) % 10 or 10
        produkt = (2 * summe) % 11
    return (11 - produkt) % 10 == int(uid[10])


def ust_de_pruefziffer(acht_ziffern: str) -> str:
    """Prüfziffer (ISO 7064 MOD 11,10) zu den ersten acht Ziffern einer deutschen USt-IdNr."""
    produkt = 10
    for ziffer in acht_ziffern:
        summe = (int(ziffer) + produkt) % 10 or 10
        produkt = (2 * summe) % 11
    return str((11 - produkt) % 10)


# ── PLZ, E-Mail, BIC, Telefon, Land, Sprache ───────────────────────────────────────────────────────────────────
#: Postleitzahlformat je Land (Auszug, Stand prüfen).
PLZ_FORMATE: dict[str, str] = {
    "DE": r"\d{5}", "AT": r"\d{4}", "CH": r"\d{4}", "BE": r"\d{4}", "DK": r"\d{4}", "NL": r"\d{4} ?[A-Z]{2}",
    "FR": r"\d{5}", "IT": r"\d{5}", "ES": r"\d{5}", "PL": r"\d{2}-\d{3}", "CZ": r"\d{3} ?\d{2}", "LU": r"\d{4}",
    "SE": r"\d{3} ?\d{2}", "GB": r"[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}",
}
#: Zulässige Länder (ISO 3166-1 Alpha-2, Auszug für den Demo-Bestand; Stand prüfen).
LAENDER = frozenset(EU_LAENDER | {"CH", "GB", "NO", "LI", "US", "CN", "TR"})
#: Zulässige Korrespondenzsprachen (SAP-Sprachschlüssel, einstellig intern – hier ISO 639-1 wie im Export).
SPRACHEN = frozenset({"DE", "EN", "FR", "IT", "NL", "PL", "ES", "CS", "DA", "SV", "PT"})

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_BIC = re.compile(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?")
_TELEFON = re.compile(r"\+\d{2,3}( ?\d){6,14}")


def plz_gueltig(plz: str, land: str) -> bool | None:
    """True/False je Format; None, wenn für das Land kein Format hinterlegt ist."""
    muster = PLZ_FORMATE.get((land or "").upper())
    if muster is None:
        return None
    return bool(re.fullmatch(muster, (plz or "").strip()))


def email_gueltig(email: str) -> bool:
    return bool(_EMAIL.fullmatch((email or "").strip()))


def bic_gueltig(bic: str) -> bool:
    return bool(_BIC.fullmatch((bic or "").strip().upper()))


def telefon_gueltig(telefon: str) -> bool:
    """Internationale Schreibweise mit Ländervorwahl (+49 …), wie für den Geschäftspartner empfohlen."""
    return bool(_TELEFON.fullmatch((telefon or "").strip()))


def telefon_ziffern(telefon: str | None) -> str:
    """Vergleichsform für die Dublettenerkennung: nur Ziffern, nationale 0 → Ländervorwahl 49."""
    z = re.sub(r"\D", "", telefon or "")
    if z.startswith("00"):
        z = z[2:]
    elif z.startswith("0"):
        z = "49" + z[1:]
    return z
