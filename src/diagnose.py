"""Umgebungsdiagnose: Sind alle Pakete importierbar und in passender Version?

Aufruf: ``python run_agent.py diagnose`` (oder ``python -m src.diagnose``). Zusätzlich: Suite-Referenz vorhanden und
Kontrollwerte stimmen, Datenbank vorhanden.
"""

from __future__ import annotations

import importlib
import platform
from dataclasses import dataclass
from importlib import metadata

# (Importname, Paketname auf PyPI, Mindestversion laut pyproject.toml)
PAKETE: tuple[tuple[str, str, str], ...] = (
    ("streamlit", "streamlit", "1.50"),
    ("altair", "altair", "5.4"),
    ("pyarrow", "pyarrow", "16.0"),   # ältere Builds sind gegen NumPy 1.x kompiliert
    ("pandas", "pandas", "2.2"),
    ("numpy", "numpy", "1.26"),
    ("rapidfuzz", "rapidfuzz", "3.9"),
    ("pydantic", "pydantic", "2.7"),
    ("pptx", "python-pptx", "1.0"),
    ("reportlab", "reportlab", "4.2"),
    ("matplotlib", "matplotlib", "3.8"),
    ("openpyxl", "openpyxl", "3.1"),
)


@dataclass(frozen=True)
class Paketstatus:
    paket: str
    version: str | None
    mindestens: str
    fehler: str | None

    @property
    def ok(self) -> bool:
        return self.fehler is None and self.version is not None and _version(self.version) >= _version(self.mindestens)


def _version(text: str) -> tuple[int, ...]:
    teile = []
    for teil in text.split(".")[:3]:
        ziffern = "".join(z for z in teil if z.isdigit())
        teile.append(int(ziffern) if ziffern else 0)
    return tuple(teile)


def pruefe_umgebung() -> list[Paketstatus]:
    ergebnis = []
    for modul, paket, mindestens in PAKETE:
        try:
            version = metadata.version(paket)
        except metadata.PackageNotFoundError:
            version = None
        try:
            importlib.import_module(modul)
            fehler = None
        except Exception as ausnahme:  # noqa: BLE001 – jede Importausnahme ist ein Befund
            fehler = f"{type(ausnahme).__name__}: {str(ausnahme).splitlines()[0][:160]}"
        ergebnis.append(Paketstatus(paket, version, mindestens, fehler))
    return ergebnis


def pruefe_suite() -> list[tuple[bool, str]]:
    """Kontrollwerte des gemeinsamen Zahlenwerks (feste Konstanten gegen die Referenzdatei)."""
    from src import suite

    try:
        ref = suite.lade_referenz()
    except FileNotFoundError:
        return [(False, "src/suite_referenz.json fehlt – tools/suite_referenz_erzeugen.py ausführen")]
    summe = sum(d["umsatz_2025_cent"] for d in ref["debitoren"])
    k101 = next(d for d in ref["debitoren"] if d["kunnr"] == "K101")
    k100100 = next(k for k in ref["kreditoren"] if k["lifnr"] == "100100")
    return [
        (len(ref["debitoren"]) == 12 and len(ref["kreditoren"]) == 6, "12 aktive Debitoren, 6 aktive Kreditoren"),
        (summe == suite.KONTROLLE_UMSATZ_2025_CENT, "Umsatz 2025 = 83.873.069,96 € (VarianceAI)"),
        (k101["letzte_faktura"] == suite.KONTROLLE_K101_LETZTE_FAKTURA, "K101 letzte Faktura 03.09.2026"),
        (k100100["iban"] == suite.KONTROLLE_IBAN_100100, "IBAN 100100 wie FlowAudit-AI"),
        (ref.get("abgleich_controllai", {}).get("differenz_cent") == 0,
         "Umsatz/HK 2025 je Kunde centgleich ControllAI"),
    ]


def bericht() -> str:
    zeilen = [f"Python {platform.python_version()} · {platform.system()} {platform.machine()}", ""]
    status = pruefe_umgebung()
    for s in status:
        kennz = "OK " if s.ok else "!! "
        hinweis = s.fehler or ("" if s.ok else f"Version zu alt (mind. {s.mindestens})")
        zeilen.append(f"{kennz}{s.paket:<12} {s.version or 'fehlt':<10} {hinweis}")
    zeilen.append("")
    for ok, text in pruefe_suite():
        zeilen.append(f"{'OK ' if ok else '!! '}Suite: {text}")
    from src.config import db_pfad

    zeilen.append(f"{'OK ' if db_pfad().exists() else '!! '}Datenbank: "
                  f"{db_pfad().name if db_pfad().exists() else 'fehlt – python run_agent.py daten'}")
    if not all(s.ok for s in status):
        zeilen += ["", "Lösung (frische Umgebung):  uv sync   bzw.   pip install -r requirements.txt"]
    return "\n".join(zeilen)


if __name__ == "__main__":
    print(bericht())
