"""Normalisierung vor dem Vergleich: Umlaute, Rechtsformen, Satzzeichen, Straße, Hausnummer."""

from __future__ import annotations

import pytest

from src.normalisierung import adresse_normal, ist_gesellschaft, name_normal, namensanfang, rechtsform


@pytest.mark.parametrize("a,b", [
    ("Hanse Fördertechnik GmbH", "Hanse Foerdertechnik G.m.b.H."),
    ("Müller Metallbau GmbH & Co. KG", "MÜLLER METALLBAU GMBH U. CO. KG"),
    ("Weser Anlagenbau AG", "Weser Anlagenbau Aktiengesellschaft"),
    ("Krämer Service UG (haftungsbeschränkt)", "Kraemer Service UG (haftungsbeschraenkt)"),
    ("Jäger Drahtwerk e.K.", "Jaeger Drahtwerk e. Kfm."),
    ("Baumann & Haas GmbH", "Baumann und Haas GmbH"),
])
def test_namensvarianten_gleich(a, b):
    assert name_normal(a) == name_normal(b)


def test_rechtsform_erkennung():
    assert rechtsform("Hessen Hydraulik GmbH") == "gmbh" and ist_gesellschaft("Weser Anlagenbau AG")
    assert rechtsform("Bürowelt Wiesbaden e.K.") == "ek" and not ist_gesellschaft("Bürowelt Wiesbaden e.K.")
    assert rechtsform("Anna Müller") is None


def test_strasse_und_hausnummer():
    assert adresse_normal("Hanauer Landstraße", "211") == adresse_normal("Hanauer Landstr.", "211")
    assert adresse_normal("Billstraße", "112 a") == "billstr 112a"


def test_namensanfang_fuer_blocking():
    assert namensanfang("Hanse Fördertechnik GmbH") == namensanfang("HANSE FOERDERTECHNIK G.M.B.H.") == "hanse"
