"""Kommandozeile: alle Befehle laufen offline und geben Kennzahlen im deutschen Format aus."""

from __future__ import annotations

import pytest

import run_agent


@pytest.fixture(autouse=True)
def demo_db(demo, monkeypatch):
    monkeypatch.setenv("DATAGUARD_DB", str(demo["db"]))


@pytest.mark.parametrize("befehl,erwartet", [
    (["diagnose"], "Suite: Umsatz 2025 = 83.873.069,96 €"),
    (["pruefen"], "DAMA-Gesamt"),
    (["pruefen", "--objekt", "KRED"], "Kreditor ohne Bankverbindung"),
    (["dubletten", "--top", "3"], "Precision"),
    (["readiness"], "Readiness-Quote"),
])
def test_befehle(befehl, erwartet, capsys):
    assert run_agent.main(befehl) == 0
    assert erwartet in capsys.readouterr().out


def test_daten(tmp_path, capsys):
    assert run_agent.main(["daten", "--seed", "7", "--ordner", str(tmp_path)]) == 0
    assert (tmp_path / "dataguard.db").exists() and (tmp_path / "wahrheit.json").exists()
    assert "Debitoren" in capsys.readouterr().out
