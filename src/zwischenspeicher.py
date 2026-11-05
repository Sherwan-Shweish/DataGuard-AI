"""Ergebniscache nach Funktion und Dateistand der Datenbank (Agenten-Standard: Folgelauf ≤ 1 s).

Ein Eintrag gilt nur für denselben Funktionsstand (Modul, Name, SHA-256 des Quelltexts) und denselben Dateistand
(Pfad, Änderungszeit in ns, Größe) aller Pfad-Argumente. Ändert sich die Datenbank (z. B. neuer Demo-Lauf) oder der
Code, wird neu gerechnet. Der Cache liegt im Prozess (Streamlit-Server bzw. Kommandozeile) und pickelt nichts –
Ergebnisse mit DataFrames, Mengen und Zeilenobjekten bleiben unverändert. Ergebnisse gelten als unveränderlich.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from functools import wraps
from hashlib import sha256
from inspect import getsource
from pathlib import Path

MAX_EINTRAEGE = 32
_SPEICHER: OrderedDict[tuple, object] = OrderedDict()
_SPERRE = threading.Lock()
STATISTIK = {"treffer": 0, "berechnet": 0}


def dateistand(pfad: str | Path) -> tuple[str, int, int]:
    p = Path(pfad)
    if not p.exists():
        return (str(p), 0, 0)
    s = p.stat()
    return (str(p.resolve()), s.st_mtime_ns, s.st_size)


def nach_dateistand(funktion):
    kennung = (funktion.__module__, funktion.__qualname__, sha256(getsource(funktion).encode()).hexdigest())

    @wraps(funktion)
    def aufruf(*args, **kwargs):
        dateien = []
        for wert in (*args, *kwargs.values()):
            if isinstance(wert, Path) or (isinstance(wert, str) and len(wert) < 400 and wert.endswith(".db")):
                dateien.append(dateistand(wert))
        schluessel = (kennung, tuple(dateien), tuple(str(a) for a in args), tuple(sorted(kwargs.items())))
        with _SPERRE:
            if schluessel in _SPEICHER:
                _SPEICHER.move_to_end(schluessel)
                STATISTIK["treffer"] += 1
                return _SPEICHER[schluessel]
        ergebnis = funktion(*args, **kwargs)
        with _SPERRE:
            _SPEICHER[schluessel] = ergebnis
            STATISTIK["berechnet"] += 1
            while len(_SPEICHER) > MAX_EINTRAEGE:
                _SPEICHER.popitem(last=False)
        return ergebnis

    aufruf.kennung = kennung
    return aufruf


def leeren() -> None:
    with _SPERRE:
        _SPEICHER.clear()
