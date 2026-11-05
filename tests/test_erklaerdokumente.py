"""Erklärdokumente: Werte stammen aus dem Programmlauf, die deutschen Fassungen liegen im Repository."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest

from src import format as fmt

PROJEKT = Path(__file__).resolve().parents[1]
WERTE = PROJEKT / "tools" / "erklaerdokumente" / "werte.json"
DOKUMENTE = ("SAP-Anbindung.docx", "Kennzahlen_und_Diagramme.docx")


def _text(docx: Path) -> str:
    with zipfile.ZipFile(docx) as z:
        return re.sub(r"<[^>]+>", "", z.read("word/document.xml").decode("utf-8"))


def test_werte_gleich_demolauf():
    w = json.loads(WERTE.read_text(encoding="utf-8"))
    d = json.loads((PROJEKT / "docs" / "demolauf.json").read_text(encoding="utf-8"))
    assert w["dama"] == fmt.prozent(d["dama_gesamt"]) and w["readiness"] == fmt.prozent(d["readiness"]["quote"])
    assert w["archiv_debi"] == fmt.prozent(d["je_objekt"]["DEBI"]["archivquote"], 1)
    assert w["archiv_kred"] == fmt.prozent(d["je_objekt"]["KRED"]["archivquote"], 1)
    assert w["pr"]["s42"]["ab_75"]["p"] == fmt.prozent(100 * d["dubletten"]["seed_42"]["ab_75"]["precision"], 1)
    assert w["zerlegung"]["bereinigt"] == fmt.pp(d["zerlegung_readiness"]["bereinigt"])


@pytest.mark.parametrize("name", DOKUMENTE)
def test_deutsche_fassung_im_repository(name):
    text = _text(PROJEKT / "docs" / name)
    w = json.loads(WERTE.read_text(encoding="utf-8"))
    assert w["saetze"] in text and w["archivieren"] in text
    assert "im System prüfen" in text or "im konkreten System" in text
    assert "So sage ich es auf Deutsch" not in text                     # Sprechkästen nur in der arabischen Fassung


def test_kennzahlen_dokument_enthaelt_pflichtinhalte():
    text = _text(PROJEKT / "docs" / "Kennzahlen_und_Diagramme.docx")
    w = json.loads(WERTE.read_text(encoding="utf-8"))
    for pflicht in ("60-Sekunden-Erklärung", "Warum kein Machine Learning für Dubletten?",
                    "Was passiert bei einer Dublette über zwei PLZ?",
                    "Warum werden alte Sätze archiviert statt migriert?",
                    "Wie passt DataGuard zu den anderen drei Agenten?",
                    "Ist eine Archivierungsquote von 80 % realistisch?", "Data Firewall",
                    w["dama"], w["readiness"], w["archiv_debi"], w["archiv_kred"]):
        assert pflicht in text, pflicht
    assert text.count("„Warum") + text.count("„Was") + text.count("„Wie") + text.count("„Ist") >= 10
