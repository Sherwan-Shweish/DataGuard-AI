"""Messskript der Endabnahme: weist die Zielwerte nach und schreibt docs/endabnahme_messung.json.

Zielwerte (Masterprompt und Freigabe Phase 2):
  • Monatsverlauf (12 Stände) ohne Ergebniscache ≤ 1,5 s – Median aus 5 Läufen, je Lauf ein frischer Prozess
  • Oberfläche Erstlauf ≤ 12 s – erster AppTest-Durchlauf in einem frischen Prozess (Importe, Datenbank, Engines)
  • Oberfläche Folgelauf ≤ 1 s – Tabwechsel in derselben Sitzung (Ergebniscache nach Dateistand), Median
Die Testsuite enthält nur großzügige Schutzwerte (5 s / 30 s / 3 s), damit sie auf langsamen Rechnern nicht zufällig
scheitert. Diese Datei ist der Nachweis der genauen Zielwerte auf dem Messrechner.

Aufruf: ``uv run python tools/endabnahme_messen.py [--laeufe 5]``
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[1]
ZIEL = PROJEKT / "docs" / "endabnahme_messung.json"
GRENZEN = {"verlauf_sekunden": 1.5, "erstlauf_sekunden": 12.0, "folgelauf_sekunden": 1.0}

VERLAUF = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
from src.analyse import laufe, verlauf
from src.config import db_pfad
from src.datenbasis import lade
d = lade(db_pfad())
t = time.perf_counter(); verlauf(d); v = time.perf_counter() - t
d = lade(db_pfad())
t = time.perf_counter(); laufe(d); g = time.perf_counter() - t
print(json.dumps({"verlauf": v, "gesamtlauf": g}))
"""

OBERFLAECHE = r"""
import json, sys, time
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(sys.argv[1], default_timeout=180)
t = time.perf_counter(); at.run(); erst = time.perf_counter() - t
assert not at.exception, [e.message for e in at.exception]
folge = []
for tab in ["Cockpit", "Regelwerk", "Dubletten", "Migration Readiness", "Verlauf", "Bericht", "Agent & Audit"]:
    at.session_state["haupttabs"] = tab
    t = time.perf_counter(); at.run(); folge.append(time.perf_counter() - t)
    assert not at.exception, (tab, [e.message for e in at.exception])
print(json.dumps({"erstlauf": erst, "folgelaeufe": folge}))
"""


def _python(code: str, argument: str) -> dict:
    env = {**os.environ, "AGENT_LAUFZEIT": "web"}
    aus = subprocess.run([sys.executable, "-c", code, argument], cwd=PROJEKT, check=True, capture_output=True,
                         text=True, env=env).stdout.strip().splitlines()[-1]
    return json.loads(aus)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Endabnahme: Laufzeiten messen")
    parser.add_argument("--laeufe", type=int, default=5)
    a = parser.parse_args(argv)
    engine = [_python(VERLAUF, str(PROJEKT)) for _ in range(a.laeufe)]
    ui = [_python(OBERFLAECHE, str(PROJEKT / "app.py")) for _ in range(a.laeufe)]
    verlauf = [e["verlauf"] for e in engine]
    erst = [e["erstlauf"] for e in ui]
    folge = [f for e in ui for f in e["folgelaeufe"]]
    werte = {
        "verlauf_sekunden": round(statistics.median(verlauf), 2),
        "erstlauf_sekunden": round(statistics.median(erst), 2),
        "folgelauf_sekunden": round(statistics.median(folge), 2),
    }
    bericht = {
        "zeitpunkt": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "python": platform.python_version(),
        "rechner": f"{platform.system()} {platform.machine()} · {os.cpu_count()} Kerne",
        "laeufe": a.laeufe,
        "methode": "je Messung ein frischer Python-Prozess; Median; Folgelauf = Tabwechsel über alle 7 Tabs",
        "werte": werte,
        "grenzen": GRENZEN,
        "erfuellt": {k: werte[k] <= GRENZEN[k] for k in GRENZEN},
        "einzelwerte": {
            "verlauf": [round(x, 2) for x in verlauf],
            "gesamtlauf": [round(e["gesamtlauf"], 2) for e in engine],
            "erstlauf": [round(x, 2) for x in erst],
            "folgelauf_max": round(max(folge), 2),
        },
    }
    ZIEL.write_text(json.dumps(bericht, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
    return 0 if all(bericht["erfuellt"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
