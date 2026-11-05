"""Normalisierung von Namen und Anschriften vor dem Vergleich (Dublettenerkennung, Kunde=Lieferant, Regeln).

Reihenfolge (fest, dokumentiert in docs/methodik.md):
1. Kleinschreibung, Umlaute (ü→ue, ö→oe, ä→ae, ß→ss), Akzente entfernen.
2. Rechtsformen vereinheitlichen (G.m.b.H. → gmbh, Aktiengesellschaft → ag, …) und für den Namensvergleich entfernen.
3. Satzzeichen durch Leerzeichen ersetzen, Füllwörter („und“, „&“, „co“) entfernen, Mehrfachleerzeichen kürzen.
4. Straße: „Straße/Strasse/Str.“ → „str“, Hausnummer getrennt normalisiert (Ziffern + Buchstabe).
"""

from __future__ import annotations

import re
import unicodedata

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})

#: Rechtsformvarianten → Normalform (Reihenfolge: lange Varianten zuerst). Werte sind Normalformen ohne Leerzeichen.
RECHTSFORMEN: tuple[tuple[str, str], ...] = (
    (r"gesellschaft mit beschraenkter haftung und compagnie kommanditgesellschaft", "gmbhcokg"),
    (r"gmbh\s*(&|und|u\.?)\s*co\.?\s*kg", "gmbhcokg"),
    (r"gesellschaft mit beschraenkter haftung", "gmbh"),
    (r"g\.\s*m\.\s*b\.\s*h\.?", "gmbh"),
    (r"gmbh", "gmbh"),
    (r"unternehmergesellschaft\s*\(?haftungsbeschraenkt\)?", "ug"),
    (r"ug\s*\(haftungsbeschraenkt\)", "ug"),
    (r"aktiengesellschaft", "ag"),
    (r"kommanditgesellschaft", "kg"),
    (r"offene handelsgesellschaft", "ohg"),
    (r"eingetragener kaufmann|eingetragene kauffrau|e\.\s*kfm\.?|e\.\s*k\.", "ek"),
    (r"b\.\s*v\.", "bv"),
    (r"n\.\s*v\.", "nv"),
    (r"s\.\s*r\.\s*l\.", "srl"),
    (r"s\.\s*l\.", "sl"),
    (r"s\.\s*a\.\s*r\.\s*l\.|sarl", "sarl"),
    (r"sp\.\s*z\s*o\.\s*o\.", "spzoo"),
    (r"s\.\s*r\.\s*o\.", "sro"),
    (r"a/s", "as"),
)
#: Normalformen, die eine Kapital- oder Personengesellschaft kennzeichnen (Regel V09: USt-IdNr. erwartet).
GESELLSCHAFTEN = frozenset({"gmbh", "gmbhcokg", "ag", "kg", "ohg", "ug", "se"})
_RECHTSFORM_TOKENS = frozenset({"gmbh", "gmbhcokg", "ag", "kg", "ohg", "ug", "ek", "bv", "nv", "srl", "sl", "sarl",
                                "spzoo", "sro", "as", "se", "sa"})
_FUELLWOERTER = frozenset({"und", "co", "u", "the", "firma", "fa"})
_RECHTSFORM_RE = [(re.compile(rf"(?<![a-z0-9]){m}(?![a-z0-9])"), n) for m, n in RECHTSFORMEN]


def grundform(text: str | None) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Akzente entfernt."""
    s = (text or "").translate(_UMLAUTE).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(z for z in s if not unicodedata.combining(z))


def rechtsformen_vereinheitlichen(text: str) -> str:
    """Rechtsformvarianten in Normalform (Eingabe bereits in Grundform)."""
    for muster, norm in _RECHTSFORM_RE:
        text = muster.sub(f" {norm} ", text)
    return text


#: Zwischenergebnis je Namenstext (Normalform, Rechtsform) – reine Funktion des Textes. Lebt nur innerhalb einer
#: Berechnung: ``memo_leeren()`` zu Beginn jedes Monatsverlaufs (ehrliche Kaltmessung).
_NAME_MEMO: dict[str | None, tuple[str, str | None]] = {}


def memo_leeren() -> None:
    _NAME_MEMO.clear()


def _name_analyse(name: str | None) -> tuple[str, str | None]:
    e = _NAME_MEMO.get(name)
    if e is None:
        s = re.sub(r"[^a-z0-9]+", " ", rechtsformen_vereinheitlichen(grundform(name)))
        teile = s.split()
        normal = " ".join(t for t in teile if t not in _RECHTSFORM_TOKENS and t not in _FUELLWOERTER)
        gefunden = [t for t in teile if t in _RECHTSFORM_TOKENS]
        e = _NAME_MEMO[name] = (normal, gefunden[-1] if gefunden else None)
    return e


def name_tokens(name: str | None) -> list[str]:
    """Namensbestandteile nach Normalisierung, Rechtsform und Füllwörter entfernt."""
    return _name_analyse(name)[0].split()


def name_normal(name: str | None) -> str:
    return _name_analyse(name)[0]


def rechtsform(name: str | None) -> str | None:
    """Erkannte Rechtsform in Normalform (z. B. „gmbh“) oder None."""
    return _name_analyse(name)[1]


def ist_gesellschaft(name: str | None) -> bool:
    return rechtsform(name) in GESELLSCHAFTEN


def strasse_normal(strasse: str | None) -> str:
    s = grundform(strasse)
    s = re.sub(r"(strasse|str\.|str\b)", "str", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hausnummer_normal(hausnr: str | None) -> str:
    return re.sub(r"[^0-9a-z]", "", grundform(hausnr))


def adresse_normal(strasse: str | None, hausnr: str | None) -> str:
    return f"{strasse_normal(strasse)} {hausnummer_normal(hausnr)}".strip()


def ort_normal(ort: str | None) -> str:
    s = grundform(ort)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def namensanfang(name: str | None, laenge: int = 5) -> str:
    """Blocking-Schlüssel Pass 3: erste Zeichen des normalisierten Namens (ohne Leerzeichen)."""
    return name_normal(name).replace(" ", "")[:laenge]
