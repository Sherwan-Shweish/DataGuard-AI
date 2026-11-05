"""Optionale Online-Bestätigung einer USt-IdNr. über VIES (EU-Kommission) – standardmäßig AUS.

DataGuard-AI prüft USt-IdNrn. offline (Format je Land, deutsche Prüfziffer ISO 7064 MOD 11,10). Ob eine Nummer
tatsächlich vergeben und gültig ist, bestätigt nur die Verwaltung:
  • VIES (EU-Kommission): Nummern aller Mitgliedstaaten, auch deutsche (Stand prüfen, docs/Quellen.md).
  • BZSt nach § 18e UStG: bestätigt ausländische USt-IdNrn.; deutsche nur im Sonderfall Lagerhalter (Stand prüfen).
Dieser Schritt sendet die Nummer an einen externen Dienst und läuft deshalb nur, wenn ``UST_ONLINE_PRUEFUNG=an``
gesetzt ist. Kein Teil der Demo, der Tests (nur mit Attrappe) oder der Kennzahlen.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from src import pruefziffern as pz

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"  # Stand prüfen


class OnlinePruefungAus(RuntimeError):
    """Online-Prüfung ist nicht freigeschaltet (UST_ONLINE_PRUEFUNG ≠ an)."""


@dataclass(frozen=True)
class ViesErgebnis:
    ust_id: str
    gueltig: bool
    name: str
    quelle: str = "VIES (EU-Kommission)"


def freigeschaltet() -> bool:
    return os.getenv("UST_ONLINE_PRUEFUNG", "aus").strip().lower() in ("an", "ja", "1", "true")


def vies_pruefen(ust_id: str, *, oeffnen=urllib.request.urlopen, timeout: float = 10.0) -> ViesErgebnis:  # noqa: ANN001
    """Fragt VIES an. Erst Formatprüfung offline; ohne Freischaltung kein Netzzugriff."""
    if not freigeschaltet():
        raise OnlinePruefungAus("Online-Prüfung ist ausgeschaltet (UST_ONLINE_PRUEFUNG=aus).")
    nr = pz.ust_normal(ust_id)
    if not pz.ust_format_gueltig(nr):
        return ViesErgebnis(nr, False, "", "Formatprüfung offline")
    land = "EL" if nr[:2] == "GR" else nr[:2]
    anfrage = urllib.request.Request(VIES_URL, data=json.dumps({"countryCode": land, "vatNumber": nr[2:]}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with oeffnen(anfrage, timeout=timeout) as antwort:
        daten = json.loads(antwort.read().decode("utf-8"))
    return ViesErgebnis(nr, bool(daten.get("valid")), str(daten.get("name") or "").strip())
