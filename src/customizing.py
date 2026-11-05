"""Demo-Customizing der RheinMain Industrietechnik GmbH (im Echtbetrieb aus dem System lesen – Bezeichnungen prüfen).

Entspricht inhaltlich den SAP-Einstellungen
* Kontengruppen und Nummernkreise (ECC: T077D Debitoren, T077K Kreditoren),
* Zuordnung Kontengruppe → BP-Gruppierung der Customer-Vendor-Integration (CVI, Synchronisationsrichtung
  Debitor/Kreditor → Geschäftspartner),
* Zahlungsbedingungen (T052), Abstimmkonten, Vertriebsgebiete (KNVV-BZIRK).

Nummernvergabe in S/4HANA: Strategie „gleiche Nummern“ – der Geschäftspartner übernimmt die Debitoren- bzw.
Kreditorennummer. Daraus folgt der Nummernkreiskonflikt (Regel K06): gleiche Nummer bei Debitor und Kreditor, die
*nicht* denselben Partner darstellen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Kontengruppe:
    objekt: str  # "DEBI" | "KRED"
    schluessel: str
    bezeichnung: str
    nummernkreise: tuple[tuple[str, str], ...]  # (von, bis) – alphanumerisch extern oder numerisch intern
    bp_gruppierung: str | None  # None = keine CVI-Zuordnung → Blocker K02


KONTENGRUPPEN: tuple[Kontengruppe, ...] = (
    Kontengruppe("DEBI", "DINL", "Kunde Inland", (("K100", "K999"), ("200000", "289999")), "BP01"),
    Kontengruppe("DEBI", "DAUS", "Kunde Ausland", (("290000", "299999"),), "BP02"),
    Kontengruppe("DEBI", "DCPD", "Einmalkunde (CPD)", (("900000", "900099"),), "CPDA"),
    Kontengruppe("DEBI", "ZINT", "Interessent (Vertrieb)", (("800000", "899999"),), None),
    Kontengruppe("DEBI", "ZALT", "Altkunde Fremdsystem (Übernahme 2009)", (("300000", "349999"),), None),
    Kontengruppe("KRED", "KINL", "Lieferant Inland", (("100000", "189999"),), "BP01"),
    Kontengruppe("KRED", "KAUS", "Lieferant Ausland", (("190000", "199999"),), "BP02"),
    Kontengruppe("KRED", "KCPD", "Einmallieferant (CPD)", (("910000", "910099"),), "CPDA"),
    Kontengruppe("KRED", "ZMIT", "Mitarbeiter (Reisekosten)", (("700000", "799999"),), None),
)
KONTENGRUPPE = {(k.objekt, k.schluessel): k for k in KONTENGRUPPEN}
BP_GRUPPIERUNGEN = {
    "BP01": "Geschäftspartner Inland (interne Nummer = Debitor/Kreditor)",
    "BP02": "Geschäftspartner Ausland",
    "CPDA": "Einmal-Geschäftspartner",
}
#: BP-Rollen je Objekt (S/4HANA-Standard, Stand prüfen): FI-Rolle und Vertriebs-/Einkaufsrolle.
BP_ROLLEN = {"DEBI": ("FLCU00", "FLCU01"), "KRED": ("FLVN00", "FLVN01")}

#: Zahlungsbedingungen (T052-Auszug).
ZAHLUNGSBEDINGUNGEN = {
    "ZB10": "10 Tage netto",
    "ZB14": "14 Tage netto",
    "ZB30": "30 Tage netto",
    "ZB45": "45 Tage netto",
    "ZB60": "60 Tage netto",
    "ZS14": "14 Tage 2 % Skonto, 30 Tage netto",
}
#: Abstimmkonten (Sachkonten Forderungen/Verbindlichkeiten).
ABSTIMMKONTEN = {"DEBI": ("140000", "141000"), "KRED": ("160000", "161000", "167000")}

#: Vertriebsgebiete der Suite (wie VarianceAI) und Zuordnung zur PLZ-Leitzone (erste Ziffer der deutschen PLZ).
#: Demo-Annahme der RheinMain: Leitzonen 0–3 betreut Nord, 4–6 West (inkl. Rhein-Main), 7–9 Süd.
REGION_JE_LEITZONE = {"0": "NORD", "1": "NORD", "2": "NORD", "3": "NORD", "4": "WEST", "5": "WEST", "6": "WEST",
                      "7": "SUED", "8": "SUED", "9": "SUED"}
#: Auslandskunden werden dem nächstgelegenen Gebiet zugeordnet (Demo-Annahme).
REGION_JE_LAND = {"AT": "SUED", "CH": "SUED", "IT": "SUED", "NL": "WEST", "BE": "WEST", "FR": "WEST", "ES": "WEST",
                  "LU": "WEST", "PL": "NORD", "CZ": "NORD", "DK": "NORD", "SE": "NORD"}


def erwartete_region(land: str, plz: str) -> str | None:
    """Vertriebsgebiet, das zu Land und PLZ passt (None = nicht bestimmbar)."""
    if land == "DE":
        return REGION_JE_LEITZONE.get((plz or " ")[0])
    return REGION_JE_LAND.get(land)


def _im_kreis(nr: str, von: str, bis: str) -> bool:
    if von.isdigit() != nr.isdigit():
        return False
    if von.isdigit():
        return len(nr) == len(von) and int(von) <= int(nr) <= int(bis)
    return len(nr) == len(von) and nr[0] == von[0] and von <= nr <= bis


def nummer_im_kreis(objekt: str, kontengruppe: str, nr: str) -> bool | None:
    """True/False, ob die Nummer im Nummernkreis der Kontengruppe liegt; None bei unbekannter Kontengruppe."""
    k = KONTENGRUPPE.get((objekt, kontengruppe))
    if k is None:
        return None
    return any(_im_kreis(nr, von, bis) for von, bis in k.nummernkreise)


def steuernummernkategorie(ust_id: str) -> str | None:
    """BP-Steuernummernkategorie aus der USt-IdNr. (SAP: <Land>0 = USt-IdNr., z. B. DE0; Stand prüfen)."""
    praefix = (ust_id or "").replace(" ", "").upper()[:2]
    return f"{praefix}0" if len(praefix) == 2 and praefix.isalpha() else None
