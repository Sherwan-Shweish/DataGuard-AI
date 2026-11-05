"""Zentrale Konfiguration von DataGuard-AI (unveränderlich, damit Auswertungen reproduzierbar bleiben)."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

PROJEKT_WURZEL = Path(__file__).resolve().parent.parent
DATEN_VERZEICHNIS = PROJEKT_WURZEL / "data"
SAMPLE_VERZEICHNIS = DATEN_VERZEICHNIS / "sample"
DB_PFAD = SAMPLE_VERZEICHNIS / "dataguard.db"
WAHRHEIT_PFAD = SAMPLE_VERZEICHNIS / "wahrheit.json"
PRUEFSEED_VERZEICHNIS = DATEN_VERZEICHNIS / "pruefseed"
SUITE_REFERENZ_PFAD = PROJEKT_WURZEL / "src" / "suite_referenz.json"

UNTERNEHMEN = "RheinMain Industrietechnik GmbH"
BUCHUNGSKREIS = "1000"
SEED = 42
PRUEF_SEED = 4242  # zweite Stichprobe mit derselben Fehlerlogik – nur zur Messung, Schwellen werden dort nie angepasst

#: Stichtag aller Auswertungen (wie VarianceAI und ControllAI) und Vergleichsstand Vormonat.
STICHTAG = date(2026, 9, 30)
VORMONAT = date(2026, 8, 31)
#: Zwölf Monatsstände des Qualitätsverlaufs (Oktober 2025 bis September 2026).
MONATSENDEN: tuple[date, ...] = (
    date(2025, 10, 31), date(2025, 11, 30), date(2025, 12, 31), date(2026, 1, 31), date(2026, 2, 28),
    date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31), date(2026, 6, 30), date(2026, 7, 31),
    date(2026, 8, 31), date(2026, 9, 30),
)

#: Archivierung statt Migration: keine Buchung seit mehr als so vielen Monaten vor dem Stichtag.
ARCHIV_MONATE = 24
#: Bankverbindung innerhalb so vieler Tage vor dem Stichtag geändert → Vier-Augen-Prüfung (wie FlowAudit-AI).
BANKAENDERUNG_TAGE = 30


def db_pfad() -> Path:
    """Datenbankpfad; für Tests und Desktop über ``DATAGUARD_DB`` überschreibbar."""
    return Path(os.environ.get("DATAGUARD_DB", DB_PFAD))


def monate_zurueck(stichtag: date, monate: int) -> date:
    """Gleicher Kalendertag ``monate`` Monate früher (Monatsende wird gekappt)."""
    jahr, monat = divmod(stichtag.year * 12 + stichtag.month - 1 - monate, 12)
    monat += 1
    tag = min(stichtag.day, _tage_im_monat(jahr, monat))
    return date(jahr, monat, tag)


def _tage_im_monat(jahr: int, monat: int) -> int:
    if monat == 12:
        return 31
    return (date(jahr, monat + 1, 1) - date(jahr, monat, 1)).days
