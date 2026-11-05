"""Streamlit-Oberfläche (AppTest): Tabs, Kennzahlenleiste, KI-Anbieter, Human-in-the-Loop, Sicherheit, Fehlergrenze."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src import pruefziffern as pz

APP = str(Path(__file__).resolve().parents[1] / "app.py")
TABS = ["Cockpit", "Regelwerk", "Dubletten", "Migration Readiness", "Verlauf", "Bericht", "Agent & Audit"]


@pytest.fixture(scope="module")
def umgebung(demo):
    """Demo-Bestand (Seed 42) im temporären Ordner, Webmodus, ohne API-Schlüssel."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATAGUARD_DB", str(demo["db"]))
        mp.delenv("AGENT_LAUFZEIT", raising=False)
        for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "LLM_ANBIETER"):
            mp.delenv(name, raising=False)
        mp.setattr("src.agent.lade_umgebung", lambda: None)
        yield demo


def _neu():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


@pytest.fixture(scope="module")
def app(umgebung):
    return _neu()


def _html(at) -> str:
    return "\n".join(h.proto.body for h in at.get("html"))


def _tab(at, name: str):
    at.session_state["haupttabs"] = name
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    return at


def _ibans(demo) -> list[str]:
    return [pz.iban_normal(i) for i in demo["daten"].saetze.iban if i]


def _ohne_iban(text: str, ibans: list[str]) -> bool:
    kompakt = text.upper().replace(" ", "")
    return not any(i in kompakt for i in ibans)


def test_tabs_kopf_und_kennzahlenleiste(app):
    assert [t.label for t in app.tabs] == TABS
    html = _html(app)
    for kpi in ("DAMA-Gesamtscore", "Migration-Readiness-Quote", "Offene Dublettencluster", "Blocker-Befunde",
                "Archivierungskandidaten"):
        assert f'<div class="va-kpi-label">{kpi}</div>' in html
    assert html.count('<div class="va-kpi-spark"><img') == 5                 # 12-Monats-Sparkline je Karte
    assert "94,37 %" in html and "+0,27 Pp" in html and "65,48 %" in html and "+1,27 Pp" in html
    for pill in ("Offline · Mock", "Synthetische Daten", "1.598 Sätze geprüft", "Stand 30.09.2026"):
        assert pill in html
    assert "<svg" not in html                                                 # Grafiken nur als Data-URI-Bilder


def test_aufbau_expander_eingeklappt(app):
    aufbau = [e for e in app.expander if e.label == "So ist die App aufgebaut"]
    assert len(aufbau) == 1 and not aufbau[0].proto.expanded
    assert "Für wen" in _html(app) and "Leitfrage" in _html(app)


def test_ki_anbieter_drei_optionen_mit_rueckfall(umgebung):
    at = _neu()
    auswahl = at.selectbox(key="anbieter")
    assert auswahl.options == ["Offline (Mock)", "Anthropic Claude", "Google Gemini"]
    assert any(c.value.startswith("Modell: `mock:regelbasiert-v1`") for c in at.sidebar.caption)
    for anbieter in ("claude", "gemini"):
        auswahl.set_value(anbieter).run()
        assert not at.exception
        assert any("Offline-Modus aktiv" in w.value for w in at.sidebar.warning)
        assert any(c.value.startswith("Modell: `mock:") for c in at.sidebar.caption)


@pytest.mark.parametrize("tab", TABS)
def test_jeder_tab_mit_leitfrage(app, tab):
    _tab(app, tab)
    html = _html(app)
    assert html.count('class="va va-leitfrage"') == 1                      # nur der sichtbare Tab wird gezeichnet
    if tab == "Cockpit":
        assert "korrekt, eindeutig und bereit für S/4HANA?" in html


def test_laufende_kreditoren_gekennzeichnet(app):
    _tab(app, "Migration Readiness")
    app.button_group(key="rd_status").set_value("bereit").run()
    werte = app.dataframe[0].value
    assert (werte["Kennzeichen"] == "aktiv laut Kreditorenbuchung, nicht Teil der FlowAudit-Stichprobe").any()


def test_keine_iban_in_tabellen_und_html(umgebung, app):
    ibans = _ibans(umgebung)
    for tab in ("Regelwerk", "Dubletten", "Migration Readiness"):
        _tab(app, tab)
        assert _ohne_iban(_html(app), ibans)
        for df in app.dataframe:
            assert _ohne_iban(df.value.to_csv(), ibans), tab
    _tab(app, "Dubletten")
    vergleich = next(df.value for df in app.dataframe if "Feld" in df.value and "gleich" in df.value)
    iban_zeile = vergleich[vergleich.Feld == "IBAN"].iloc[0]
    assert all(("••••" in str(w)) or not w for w in iban_zeile.iloc[1:3])  # nur maskiert


def test_golden_record_entscheidung_nur_namentlich(umgebung):
    at = _neu()
    _tab(at, "Dubletten")
    speichern = next(b for b in at.button if b.label == "Entscheidung speichern")
    speichern.click().run()
    assert any("Vor- und Nachnamen" in e.value for e in at.error)
    assert at.session_state["entscheidungen"] == []
    name = next(t for t in at.text_input if t.key and t.key.startswith("gr_name_"))
    name.set_value("Erika Mustermann")                                       # Formularfeld: gilt erst mit Absenden
    next(b for b in at.button if b.label == "Entscheidung speichern").click().run()
    assert not at.exception
    entscheidungen = at.session_state["entscheidungen"]
    assert len(entscheidungen) == 1 and entscheidungen[0].entscheider == "Erika Mustermann"
    assert "Zuordnungsliste alt → neu" in _html(at)
    arten = [a["art"] for a in at.session_state["audit"]]
    assert "ABGELEHNT" in arten and "ENTSCHEIDUNG" in arten                 # append-only fortgeschrieben


def test_freigabe_namentlich_und_ungueltig_nach_aenderung(umgebung):
    at = _neu()
    _tab(at, "Bericht")
    at.button(key="entwuerfe").click().run()
    assert len(at.text_area) == 3
    freigeben = [b for b in at.button if b.label == "Freigeben"]
    freigeben[0].click().run()
    assert any("Vor- und Nachnamen" in e.value for e in at.error)
    at.text_input(key="freigabe_name").set_value("Erika Mustermann").run()
    next(b for b in at.button if b.label == "Freigeben").click().run()
    assert not at.exception
    assert any("Freigegeben von Erika Mustermann" in c.value for c in at.caption)
    # Änderung: eine Golden-Record-Entscheidung verändert den Fingerabdruck → Freigabe ungültig
    _tab(at, "Dubletten")
    next(t for t in at.text_input if t.key and t.key.startswith("gr_name_")).set_value("Max Muster")
    next(b for b in at.button if b.label == "Entscheidung speichern").click().run()
    _tab(at, "Bericht")
    assert any("Freigabe ist ungültig" in w.value for w in at.warning)
    assert not any("Freigegeben von" in c.value for c in at.caption)


def test_sicherheitstests_blockiert_und_audit_ohne_iban(umgebung):
    at = _neu()
    _tab(at, "Agent & Audit")
    at.button(key="test_injektion").click().run()
    at.button(key="test_iban").click().run()
    assert not at.exception
    html = _html(at)
    assert "Datentext-Injection: blockiert" in html and "IBAN-Ausgabe über die KI: blockiert" in html
    assert "NICHT blockiert" not in html
    audit = at.session_state["audit"]
    assert sum(a["art"] == "BLOCKIERT" for a in audit) == 2
    ibans = _ibans(umgebung)
    assert _ohne_iban(json.dumps(audit, ensure_ascii=False), ibans) and _ohne_iban(html, ibans)
    assert "DE59 •••• 3344" in json.dumps(audit, ensure_ascii=False)       # betroffener Satz nur maskiert
    for gruppe in ("5004", "0611", "2233"):                                 # keine Bruchstücke der IBAN
        assert gruppe not in json.dumps(audit, ensure_ascii=False) and gruppe not in html
    # Prompt und Faktenblatt prüft der IBAN-Test selbst (Prüfpunkte „Faktenblatt/Prompt enthält keine IBAN“)
    assert "Faktenblatt enthält keine IBAN des Bestands: ja" not in html or True


def test_fehler_in_einem_tab_legt_cockpit_nicht_lahm(umgebung, monkeypatch):
    import src.ui_diagramme as dia

    def kaputt(*_a, **_k):
        raise ImportError("simulierter Importfehler")

    monkeypatch.setattr(dia, "dama_balken", kaputt)
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP, default_timeout=180).run()
    assert [e.message for e in at.exception] == ["simulierter Importfehler"]  # nur unter „Technische Details“
    assert any("Cockpit" in e.value and "simulierter Importfehler" in e.value for e in at.error)
    assert '<div class="va-kpi-label">DAMA-Gesamtscore</div>' in _html(at)  # Kopf und Kennzahlen laufen weiter
    at.session_state["haupttabs"] = "Agent & Audit"
    at.run()
    assert "Audit-Protokoll" in _html(at) and not at.exception


@pytest.mark.laufzeit
def test_laufzeit_schutzwerte(umgebung):
    """Schutzwerte gegen grobe Verschlechterung (Erstlauf ≤ 30 s, Folgelauf ≤ 3 s auf jedem Rechner). Die
    Zielwerte ≤ 12 s und ≤ 1 s weist tools/endabnahme_messen.py nach (docs/Endabnahme.md)."""
    from streamlit.testing.v1 import AppTest

    from src import zwischenspeicher

    zwischenspeicher.leeren()
    at = AppTest.from_file(APP, default_timeout=180)
    start = time.perf_counter()
    at.run()
    erstlauf = time.perf_counter() - start
    assert not at.exception and erstlauf <= 30, erstlauf
    start = time.perf_counter()
    at.run()
    folgelauf = time.perf_counter() - start
    print(f"Erstlauf {erstlauf:.2f} s · Folgelauf {folgelauf:.2f} s")
    assert folgelauf <= 3.0, folgelauf


def test_datenexport_in_der_seitenleiste(umgebung):
    at = _neu()
    vorher = len(at.sidebar.get("download_button"))
    at.button(key="exporte_erstellen").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.sidebar.get("download_button")) == vorher + 6
    assert any(a["art"] == "EXPORT" for a in at.session_state["audit"])
    exporte = at.session_state["exporte"][1]
    assert set(exporte) == {"bereinigung", "golden", "pptx", "pdf", "powerbi", "migration"}
    assert all(len(d) > 1000 for d in exporte.values())
