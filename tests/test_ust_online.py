"""Optionale VIES-Bestätigung: standardmäßig aus, ohne Freischaltung kein Netzzugriff."""

from __future__ import annotations

import io
import json

import pytest

from src import ust_online


def test_standardmaessig_aus(monkeypatch):
    monkeypatch.delenv("UST_ONLINE_PRUEFUNG", raising=False)
    aufrufe = []
    with pytest.raises(ust_online.OnlinePruefungAus):
        ust_online.vies_pruefen("DE214365872", oeffnen=lambda *a, **k: aufrufe.append(a))
    assert aufrufe == []                                                    # kein Netzzugriff


def test_mit_freischaltung_und_attrappe(monkeypatch):
    monkeypatch.setenv("UST_ONLINE_PRUEFUNG", "an")
    gesendet = {}

    class Antwort(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def oeffnen(anfrage, timeout):
        gesendet.update(json.loads(anfrage.data))
        return Antwort(json.dumps({"valid": True, "name": "Hessen Hydraulik GmbH"}).encode())

    e = ust_online.vies_pruefen("DE 214 365 872", oeffnen=oeffnen)
    assert gesendet == {"countryCode": "DE", "vatNumber": "214365872"}
    assert e.gueltig and e.name == "Hessen Hydraulik GmbH" and e.quelle.startswith("VIES")


def test_formatfehler_ohne_anfrage(monkeypatch):
    monkeypatch.setenv("UST_ONLINE_PRUEFUNG", "an")
    e = ust_online.vies_pruefen("DE12", oeffnen=lambda *a, **k: pytest.fail("keine Anfrage erwartet"))
    assert not e.gueltig and e.quelle == "Formatprüfung offline"
