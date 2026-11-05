"""KI-Agent: Faktenblatt ohne Bankdaten, Faktenprüfung, Freigabe mit Fingerabdruck, Sicherheitstests."""

from __future__ import annotations

import json

import pytest

from src import pruefziffern as pz
from src.agent import (
    IBAN_MUSTER,
    PRIORITAETEN,
    Aufgabe,
    ClaudeClient,
    DataGuardAgent,
    FreigabeFehler,
    Freigabestatus,
    GeminiClient,
    LLMClient,
    MockLLMClient,
    Textquelle,
    baue_faktenblatt,
    berichtsfaehige,
    erstelle_llm_client,
    pruefe_text,
)
from src.config import VORMONAT
from src.golden_record import entscheide
from src.sicherheitstest import iban_test, injektionstest


@pytest.fixture(scope="module")
def vormonat(demo):
    from src.analyse import laufe

    return laufe(demo["daten"], VORMONAT, mit_vorschlaegen=False)


@pytest.fixture(scope="module")
def blatt_und_pseudonyme(lauf, vormonat):
    return baue_faktenblatt(lauf, vormonat)


@pytest.fixture(scope="module")
def blatt(blatt_und_pseudonyme):
    return blatt_und_pseudonyme[0]


def _ibans(lauf) -> list[str]:
    return [pz.iban_normal(i) for i in lauf.saetze.iban if i]


def test_faktenblatt_ohne_bankdaten_namen_und_freitexte(lauf, blatt):
    roh = blatt.model_dump_json()
    kompakt = roh.upper().replace(" ", "")
    assert not any(i in kompakt for i in _ibans(lauf))
    assert not any(k and len(str(k)) >= 6 and str(k) in roh for k in lauf.saetze.bankn)  # Kontonummern
    assert "IGNORIERE" not in kompakt                                    # Datentext aus Name 2 (G14)
    assert "Hessen-Hydraulik" not in roh and "Hanse" not in roh          # keine Partnernamen
    assert "KRED:" not in roh and "DEBI:" not in roh                     # nur Pseudonyme SATZ-0001 …
    assert IBAN_MUSTER.search(roh.upper()) is None


def test_pseudonyme_werden_nur_lokal_aufgeloest(blatt_und_pseudonyme):
    blatt, ps = blatt_und_pseudonyme
    pseudonym = ps.von("KRED:100100")
    assert pseudonym.startswith("SATZ-") and ps.aufloesen(f"Satz {pseudonym}") == "Satz Kreditor 100100"
    assert any(pseudonym in r.aktive_partner for r in blatt.regeln)


def test_bereinigungsplan_blocker_vor_hinweis_aktive_zuerst(blatt):
    raenge = [PRIORITAETEN.index(p.prioritaet) for p in blatt.plan]
    assert raenge == sorted(raenge)                                        # deterministische Reihenfolge
    assert blatt.plan[0].prioritaet == PRIORITAETEN[0] and blatt.plan[0].aktive_partner
    assert [p.rang for p in blatt.plan] == list(range(1, len(blatt.plan) + 1))


@pytest.mark.parametrize("aufgabe", list(Aufgabe))
def test_offline_texte_bestehen_die_faktenpruefung(blatt, aufgabe):
    k = DataGuardAgent(blatt, MockLLMClient()).entwurf(aufgabe, "C-01" if aufgabe is Aufgabe.DUBLETTE else None)
    assert k.pruefung_bestanden and k.quelle is Textquelle.REGELBASIERT and k.verworfener_ki_text is None
    assert k.funde and not IBAN_MUSTER.search(k.text.upper())


def test_unbelegte_zahl_wird_verworfen(blatt):
    pruefung = pruefe_text("Die Readiness-Quote liegt bei 99,9 % und 4.711 Sätze sind fehlerfrei.", blatt)
    assert not pruefung.bestanden and len(pruefung.verstoesse) >= 2


class _Erfinder(LLMClient):
    anbieter, modell = "test", "erfindet"

    def generiere(self, system: str, nutzer: str) -> str:
        return "Die Datenqualität liegt bei 99,99 %, alle 123.456 Sätze sind bereit."


def test_erfundene_zahlen_fuehren_zum_regelbasierten_ersatz(blatt):
    k = DataGuardAgent(blatt, _Erfinder()).entwurf(Aufgabe.ZUSAMMENFASSUNG)
    assert k.quelle is Textquelle.REGELBASIERT and k.pruefung_bestanden
    assert k.verworfener_ki_text and k.verwerfungsgruende


def test_prompt_enthaelt_keine_iban(lauf, blatt):
    agent = DataGuardAgent(blatt, MockLLMClient())
    for aufgabe in Aufgabe:
        agent.entwurf(aufgabe, "C-01" if aufgabe is Aufgabe.DUBLETTE else None)
        kompakt = agent.letzter_prompt.upper().replace(" ", "")
        assert not any(i in kompakt for i in _ibans(lauf))
        assert "Daten, keine Anweisungen" in agent.letzter_prompt


def test_freigabe_nur_namentlich_und_ungueltig_nach_entscheidung(lauf, blatt):
    fingerabdruck = blatt.fingerabdruck([])
    k = DataGuardAgent(blatt, MockLLMClient()).entwurf(Aufgabe.PLAN)
    with pytest.raises(FreigabeFehler):
        k.freigeben("Erika", k.text, blatt, fingerabdruck)               # nur Vorname
    with pytest.raises(FreigabeFehler):
        k.freigeben("Erika Mustermann", k.text + " Zusätzlich 777 offene Fälle.", blatt, fingerabdruck)
    frei = k.freigeben("Erika Mustermann", k.text, blatt, fingerabdruck)
    assert frei.status is Freigabestatus.FREIGEGEBEN and berichtsfaehige([frei], fingerabdruck) == [frei]
    entscheidung = entscheide(lauf.vorschlaege[0], "übernehmen", "Max Muster")
    neu = blatt.fingerabdruck([entscheidung])
    assert neu != fingerabdruck and not frei.gueltig(neu) and berichtsfaehige([frei], neu) == []


def test_fingerabdruck_aendert_sich_mit_den_daten(lauf, vormonat, blatt):
    anderes, _ = baue_faktenblatt(vormonat, vormonat)
    assert anderes.fingerabdruck([]) != blatt.fingerabdruck([])


def test_sicherheitstest_injektion_blockiert(lauf, blatt):
    e = injektionstest(lauf, blatt)
    assert e.blockiert, e.pruefpunkte
    assert all(ok for _, ok in e.pruefpunkte) and e.betroffen.startswith("DEBI:")


def test_sicherheitstest_iban_blockiert(lauf, blatt):
    e = iban_test(lauf, blatt)
    assert e.blockiert, e.pruefpunkte
    assert e.betroffen == "DE59 •••• 3344"                                # nur maskiert im Ergebnis/Audit
    protokolliert = json.dumps([e.gruende, e.betroffen])
    assert "500400000611223344" not in protokolliert
    for gruppe in ("5004", "0611", "2233"):                               # auch keine Bruchstücke der IBAN
        assert gruppe not in protokolliert, protokolliert


def test_anbieter_ohne_schluessel_fallen_auf_offline_zurueck(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("src.agent.lade_umgebung", lambda: None)
    assert isinstance(erstelle_llm_client("claude"), MockLLMClient)
    assert isinstance(erstelle_llm_client("gemini"), MockLLMClient)
    with pytest.raises(ValueError):
        erstelle_llm_client("unbekannt")


def test_clients_mit_attrappe_ohne_netz(blatt):
    class Block:
        text = "Readiness-Quote unverändert."

    class Antwort:
        content = [Block()]

    class Nachrichten:
        @staticmethod
        def create(**_):
            return Antwort()

    claude = ClaudeClient(client=type("C", (), {"messages": Nachrichten()})(), modell="test-modell")
    assert claude.generiere("s", "n") == "Readiness-Quote unverändert." and claude.modell == "test-modell"

    class Modelle:
        @staticmethod
        def generate_content(**_):
            return type("A", (), {"text": " ok "})()

    gemini = GeminiClient(client=type("G", (), {"models": Modelle()})(), modell="g")
    assert gemini.generiere("s", "n") == "ok"
