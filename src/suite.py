"""Gemeinsames Zahlenwerk der RheinMain Controlling-Suite (nur lesend aus ``src/suite_referenz.json``).

Die Datei wird einmalig mit ``tools/suite_referenz_erzeugen.py`` in den Projektordnern von VarianceAI, FlowAudit-AI
und ControllAI erzeugt. Zur Laufzeit greift DataGuard-AI nie auf die anderen Agenten zu.
"""

from __future__ import annotations

import json
from functools import lru_cache

from src.config import SUITE_REFERENZ_PFAD

#: Kontrollwerte des gemeinsamen Zahlenwerks (feste Konstanten, unabhängig von der JSON-Datei – siehe Tests).
KONTROLLE_UMSATZ_2025_CENT = 8_387_306_996
KONTROLLE_K101_UMSATZ_2025_CENT = 948_671_497
KONTROLLE_K101_LETZTE_FAKTURA = "2026-09-03"
KONTROLLE_IBAN_100100 = "DE59500400000611223344"
KONTROLLE_UST = {
    "100100": "DE214365872", "100200": "DE287654316", "100300": "DE149832767", "100400": "DE265437897",
    "100500": "DE231987458", "100600": "DE298765120", "EIGENE_FIRMA": "DE812345673",
}
#: Querverweise der Suite-Kette DataGuard → FlowAudit → VarianceAI → ControllAI.
SUITE_KETTE = ("DataGuard-AI", "FlowAudit-AI", "VarianceAI", "ControllAI")


@lru_cache(maxsize=1)
def lade_referenz() -> dict:
    return json.loads(SUITE_REFERENZ_PFAD.read_text(encoding="utf-8"))


def aktive_debitoren() -> list[str]:
    return [d["kunnr"] for d in lade_referenz()["debitoren"]]


def aktive_kreditoren() -> list[str]:
    return [k["lifnr"] for k in lade_referenz()["kreditoren"]]


def aktive_schluessel() -> frozenset[str]:
    return frozenset([f"DEBI:{n}" for n in aktive_debitoren()] + [f"KRED:{n}" for n in aktive_kreditoren()])
