"""Deutsches Zahlen- und Datumsformat (wie in der ganzen Suite): 1.234,56 · 94,80 % · +1,2 Pp · TT.MM.JJJJ."""

from __future__ import annotations

from datetime import date


def zahl(wert: float | int, stellen: int = 0) -> str:
    text = f"{wert:,.{stellen}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def prozent(wert: float, stellen: int = 2) -> str:
    return f"{zahl(wert, stellen)} %"


def pp(delta: float, stellen: int = 2) -> str:
    """Veränderung einer Quote in Prozentpunkten, immer mit Vorzeichen (−0,40 Pp)."""
    vorzeichen = "+" if delta > 0 else "−" if delta < 0 else "±"
    return f"{vorzeichen}{zahl(abs(delta), stellen)} Pp"


def delta(wert: float, stellen: int = 0) -> str:
    vorzeichen = "+" if wert > 0 else "−" if wert < 0 else "±"
    return f"{vorzeichen}{zahl(abs(wert), stellen)}"


def datum(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "–"
