# DataGuard-AI · Stammdaten-Copilot

<!-- Live-Demo: nach dem Deploy anpassen (Link wird separat gesetzt) -->
[![Live-Demo](https://img.shields.io/badge/Live--Demo-folgt-lightgrey)](#)
[![Tests](https://img.shields.io/badge/Tests-317%20bestanden-brightgreen)](docs/pytest-python313.txt)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue)](pyproject.toml)
[![Offline](https://img.shields.io/badge/Demo-ohne%20API--Key-0A66C2)](#schnellstart)
[![Version](https://img.shields.io/badge/Version-1.0.0-2EA44F)](docs/Aenderungsprotokoll.md)
[![Agenten-Standard](https://img.shields.io/badge/Agenten--Standard-v1-orange)](docs/STANDARD.md)

> *Sind unsere Kunden- und Lieferantenstammdaten korrekt, eindeutig und bereit für S/4HANA?*

DataGuard-AI prüft die Debitoren- und Kreditorenstammdaten der fiktiven **RheinMain Industrietechnik GmbH** mit
46 Regeln entlang der DAMA-Dimensionen, findet Dubletten erklärbar, schlägt je Cluster einen Golden Record
vor und misst, welche Sätze als Geschäftspartner (BP) über die Customer-Vendor-Integration (CVI) nach S/4HANA
migriert werden können. Python prüft, misst und schlägt vor; der KI-Agent erklärt nur – jede Zahl in seinem Text wird
gegen ein Faktenblatt geprüft. Entscheidungen trifft ein Mensch mit Namen. Alle Daten sind **synthetisch**.

## Teil der RheinMain Controlling-Suite

Vier Agenten, eine Firma (RheinMain Industrietechnik GmbH, Mainzer Straße 120, 65189 Wiesbaden, Buchungskreis 1000),
ein Zahlenwerk mit Stichtag 30.09.2026 (FlowAudit-AI: laufender Rechnungseingang bis 28.10.2026 auf derselben
Zeitachse):

```
DataGuard-AI  →  FlowAudit-AI  →  VarianceAI  →  ControllAI
Stammdaten-      Prozess-         Abweichungen     Management-
qualität         sicherheit P2P   Plan/Ist         entscheidungen
```

| Agent | Ebene | Was er tut | Leitfrage |
|---|---|---|---|
| **DataGuard-AI** | Stammdatenqualität | Prüft Kunden- und Lieferantenstammdaten, findet Dubletten, schlägt Golden Records vor und misst die S/4HANA-Readiness. | *Sind unsere Kunden- und Lieferantenstammdaten korrekt, eindeutig und bereit für S/4HANA?* |
| **FlowAudit-AI** | Prozesssicherheit P2P | Prüft jede Eingangsrechnung gegen Bestellung und Wareneingang (E-Rechnung, 3-Way-Matching, Prävention) und gibt sie frei oder in die Klärung. | *Darf diese Rechnung bezahlt werden – und wenn nicht, warum?* |
| **VarianceAI** | Abweichungen | Zerlegt Plan-Ist-Abweichungen im Monatsabschluss in Preis-, Mengen-, Mix- und Kostenstelleneffekte und prognostiziert das Jahresende. | *Warum weicht das Ergebnis vom Plan ab – und wo landen wir am Jahresende?* |
| **ControllAI** | Managemententscheidungen | Verdichtet Profitabilität, Szenarien, Balanced Scorecard und Prozessportfolio für die Unternehmenssteuerung. | *Wohin steuert das Unternehmen?* |

Saubere Stammdaten sind die Voraussetzung für alles Weitere: Eine doppelte Lieferantennummer mit gleicher IBAN ist ein
Doppelzahlungsrisiko, das FlowAudit-AI bei der Einzelrechnung abfängt; ein falsches Vertriebsgebiet verfälscht den
Umsatz je Region in VarianceAI und ControllAI. Kontrolltabelle aller gemeinsamen Werte (12 Kunden, 6 Lieferanten,
Umsatz 2025 = 83.873.069,96 €, EBIT 2025 als Referenz): [`docs/Suite-Abstimmung.md`](docs/Suite-Abstimmung.md).

**Abgrenzung:** DataGuard prüft Stammdaten (Kreditoren LFA1/LFB1/LFBK, Debitoren KNA1/KNB1/KNBK), keine Belege.
Materialstammdaten (MARA) sind bewusst nicht im Umfang: Die Suite kennt Material nur als Produktgruppe (ANT/STE/SEN);
die CVI betrifft ausschließlich Debitoren und Kreditoren, und dort liegt der typische Engpass einer S/4HANA-Migration.

### Hintergrund (Stand prüfen)

* Die Mainstream-Wartung für SAP ERP 6.0 (ECC) endet Ende 2027; eine kostenpflichtige erweiterte Wartung ist bis Ende
  2030 möglich ([SAPinsider](https://sapinsider.org/blogs/sap-support-deadlines-2027-2030-2033/)).
* In S/4HANA ist der Geschäftspartner (BP) führend; jeder Debitor und Kreditor wird über die CVI zu einem
  Geschäftspartner ([SAP Community](https://blogs.sap.com/2016/04/29/simplification-item-business-partner-approach-customer-vendor-integration-cvi)).
  Datenbereinigung vor der CVI ist ein typischer Engpass von Migrationsprojekten. Weitere Quellen: [`docs/Quellen.md`](docs/Quellen.md).

## Einblick

![Cockpit (dunkel)](docs/screenshots/01_cockpit_dunkel.png)

| Dubletten (dunkel) | Migration Readiness (hell) |
|---|---|
| ![Dubletten](docs/screenshots/03_dubletten_dunkel.png) | ![Migration Readiness](docs/screenshots/04_readiness_hell.png) |
| **Verlauf (hell)** | **Agent & Audit (hell)** |
| ![Verlauf](docs/screenshots/05_verlauf_hell.png) | ![Agent & Audit](docs/screenshots/07_agent_audit_hell.png) |

Mac-App (Fenster 1480 × 940): [`docs/screenshots/08_desktop_fenster.png`](docs/screenshots/08_desktop_fenster.png) ·
alle sieben Tabs hell und dunkel: [`docs/screenshots/`](docs/screenshots/).

## Ergebnisse der Demo (Stichtag 30.09.2026)

Alle Werte aus [`docs/demolauf.json`](docs/demolauf.json) (Programmlauf, nichts geschätzt).

| Kennzahl | 30.09.2026 | 31.08.2026 | Veränderung |
|---|---:|---:|---:|
| DAMA-Gesamtscore | 94,37 % | 94,10 % | +0,27 Pp |
| Migration-Readiness-Quote | 65,48 % | 64,21 % | +1,27 Pp |
| Offene Dublettencluster | 25 | 26 | −1 |
| Blocker-Befunde | 84 | 81 | +3 |
| Archivierungskandidaten | 1.288 | 1.287 | +1 |

| Objekt | Sätze | archivieren | Archivierungsquote | zu migrieren | bereit | Readiness-Quote |
|---|---:|---:|---:|---:|---:|---:|
| Debitoren | 896 | 822 | 91,7 % | 74 | 42 | 56,76 % |
| Kreditoren | 702 | 466 | 66,4 % | 236 | 161 | 68,22 % |
| **Gesamt** | **1.598** | **1.288** | **80,6 %** | **310** | **203** | **65,48 %** |

Die Archivierungsquote von 80,6 % ist ein **Demo-Effekt der Suite**, kein Befund über „gute“ oder „schlechte“ Stammdaten: Nur die 12 Kunden aus VarianceAI haben Umsatz, und Altkunden dürfen keine Buchungen erhalten, die diesen Umsätzen widersprechen. Deshalb liegt die Debitorenquote bei 91,7 % (822 von 896) – sie folgt aus der Suite-Vorgabe. Die **Kreditorenquote von 66,4 %** ist der realistischere Wert. Im Echtbetrieb entscheidet die Archivierungsregel des Unternehmens (Frist, offene Posten, Aufbewahrungspflichten).

Bestand: 896 Debitoren und 702 Kreditoren (1.598 Sätze). Davon 18 aktive
Partner der Suite und 203 laufende Kreditoren – *aktiv laut Kreditorenbuchung, nicht Teil der
FlowAudit-Stichprobe* (nur Datum der letzten Buchung und Anzahl Belege, keine Beträge). Aktive Partner: 16
„bereit“; blockiert: 100100 (E01, E03), 100300 (E05).

**DAMA steigt, Readiness sinkt** – aus dem Änderungsprotokoll, nicht gesetzt: DAMA-Gesamtscore
91,48 % → 94,37 %, Readiness-Quote 70,49 % →
65,48 % (31.10.2025 → 30.09.2026). Zerlegung:
Neuanlagen bereit +5,62 Pp, bereinigt +4,87 Pp, Alterung/Zeitablauf −0,96 Pp, verschlechtert durch Änderung −3,79 Pp, neue Blocker durch Neuanlagen −10,75 Pp. Daraus die Governance-Empfehlung
**„Data Firewall“**: Pflichtfeld- und Dublettenprüfung bereits bei der Anlage.

### Dublettenerkennung – Precision, Recall, F1 (Paarebene)

| Stichprobe | Schwelle | Precision | Recall | F1 | Blocking-Recall |
|---|---:|---:|---:|---:|---:|
| Seed 42 (Entwicklung) | ≥ 75 | 95,87 % | 96,67 % | 96,27 % | 97,50 % |
| Seed 42 (Entwicklung) | ≥ 90 | 100,00 % | 92,50 % | 96,10 % | 97,50 % |
| Prüf-Seed 4242 | ≥ 75 | 99,02 % | 96,19 % | 97,58 % | 98,10 % |
| Prüf-Seed 4242 | ≥ 90 | 100,00 % | 87,62 % | 93,40 % | 98,10 % |

Schwellen und Gewichte wurden nie angepasst. Blocking reduziert 647.011 mögliche
Vergleiche auf 7.454 (Seed 42). Zwei Fälle sind bewusst so gebaut, dass kein
Blocking-Pass sie findet (Umzug + vertauschte Wortfolge, keine IBAN/USt-IdNr.) – Details und alle FN/FP-Fälle in
[`docs/methodik.md`](docs/methodik.md).

## Kennzahlen und Formeln

| Kennzahl | Formel |
|---|---|
| Score je DAMA-Dimension | bestandene ÷ anwendbare Prüfungen (Satz × Regel) der Dimension × 100 |
| DAMA-Gesamtscore | ungewichteter Mittelwert der fünf Dimensionen (Vollständigkeit, Gültigkeit, Eindeutigkeit, Konsistenz, Aktualität) |
| Dubletten-Score | 0,60 Name + 0,25 Straße/Hausnr. + 0,15 Ort + 15 IBAN + 15 USt-IdNr. + 10 Telefon − 20 bei verschiedener USt-IdNr. |
| Readiness-Quote | bereit ÷ (alle − archivieren) × 100 – gesamt und je Objekt |
| Archivierungsquote | archivieren ÷ alle Sätze × 100 – gesamt und je Objekt |
| Zerlegung der Readiness-Veränderung | Beitrag je Satz = (Δbereit − q₀ · Δbasis) ÷ basis₁; Summe = Veränderung |
| Archivierungskandidat | keine Buchung > 24 Monate · nie bebucht und älter als 24 Monate · Löschvormerkung · gesperrt ohne offene Posten |
| Precision / Recall / F1 | TP ÷ (TP + FP) · TP ÷ (TP + FN) · 2PR ÷ (P + R) |

## Oberfläche, KI-Agent und Exporte

| Tab | Leitfrage |
|---|---|
| Cockpit | Sind unsere Kunden- und Lieferantenstammdaten korrekt, eindeutig und bereit für S/4HANA? |
| Regelwerk | Welche Regel ist wo verletzt – in welchem SAP-Feld und mit welchem Korrekturvorschlag? |
| Dubletten | Welche Sätze sind derselbe Partner – und welcher Golden Record soll überleben? |
| Migration Readiness | Welche Sätze können migriert werden, welche sind blockiert, welche archiviert? |
| Verlauf | Wird die Datenqualität besser – und wer verursacht neue Blocker? |
| Bericht | Welche geprüften Aussagen gehen – namentlich freigegeben – an die Geschäftsführung? |
| Agent & Audit | Wer entscheidet was – und warum? |

* **KI-Agent:** erhält nur ein Faktenblatt (Kennzahlen, Regel-IDs, Pseudonyme `SATZ-0001`, Merkmalswerte) – nie IBAN,
  Bankdaten, Namen oder Freitexte. Unbelegte Zahlen → Text verworfen, regelbasierter Ersatz. Anbieter: Offline (Mock),
  Anthropic Claude, Google Gemini; ohne Schlüssel automatischer Rückfall auf Offline.
* **Human-in-the-Loop:** Golden-Record-Entscheidung und Berichtsfreigabe nur mit Vor- und Nachnamen; Freigaben werden
  ungültig, sobald sich Daten oder Entscheidungen ändern. Append-only Audit mit JSON-Export; zwei Sicherheitstests
  (Datentext-Injection, IBAN-Ausgabe) – beide blockiert.
* **Exporte** (Seitenleiste „Datenexport“, IBAN überall maskiert, Formel-Injection entschärft):
  Excel *Bereinigungsliste* mit Blatt *Gegenprüfung* (DAMA-Scores und Quoten per Formel nachgerechnet, Status
  grün/rot) · Excel *Golden-Record-Entscheidungen* (alt → neu, Entscheider, Zeitpunkt, Begründung) ·
  *Readiness-Bericht* als PowerPoint und PDF (IBCS, nur freigegebene Kommentare) · *Power-BI-Paket* (Sternschema,
  DAX für DAMA-Score und Readiness-Quote, CSV mit Semikolon, Dezimalkomma, TT.MM.JJJJ, UTF-8 mit BOM) ·
  *Übergabe-CSV für das SAP S/4HANA Migration Cockpit* – ausdrücklich **Beispiel**, Feldnamen im System prüfen,
  ohne Bankverbindung.

## Schnellstart

```bash
uv sync
uv run streamlit run app.py                         # Browser (Webmodus, festes Thema)
AGENT_LAUFZEIT=lokal uv run streamlit run app.py    # Browser mit Umschalter hell/dunkel
uv run python -m desktop.launcher                   # Mac-Fenster
uv run python -m desktop.build_app                  # ~/Applications/DataGuard-AI.app
uv run python run_agent.py diagnose                 # Umgebung und Kontrollwerte der Suite
uv run python run_agent.py pruefen | dubletten | readiness | verlauf
uv run pytest && uv run ruff check .
```

Ohne Datenbank erzeugt die Oberfläche den Demo-Bestand beim ersten Start selbst (Seed 42). Alternativ ohne uv:
`pip install -r requirements.txt` in einer frischen Umgebung.

## Konfiguration

| Einstellung | Wirkung |
|---|---|
| `LLM_ANBIETER` | `mock` (Standard, offline) · `claude` · `gemini` – in der Oberfläche auch per Auswahl |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Vorrang Umgebung > `.env` > macOS-Schlüsselbund (`security add-generic-password -s "DataGuard-AI" -a "ANTHROPIC_API_KEY" -w`); Werte werden nie angezeigt oder protokolliert |
| `ANTHROPIC_MODEL` / `GEMINI_MODEL` | Modell-ID (Vorlage in `.env.example`) |
| `UST_ONLINE_PRUEFUNG` | `aus` (Standard). Mit `an` kann `src/ust_online.py` eine USt-IdNr. bei VIES bestätigen lassen – sendet Daten an die EU-Kommission, nur mit Zustimmung |
| `AGENT_LAUFZEIT` | `web` (festes Thema) · `lokal` / `desktop` (Umschalter hell/dunkel, Einstellung gespeichert) |
| `DATAGUARD_DB` | Pfad der SQLite-Datenbank (Standard `data/sample/dataguard.db`) |

## Grundsätze

* **Determinismus vor KI:** Python prüft, misst und schlägt vor; das LLM erklärt nur.
* **Mensch entscheidet:** kein automatisches Zusammenführen, Löschen oder Ändern – Ergebnis ist eine Zuordnungsliste.
* **Bankdaten geschützt:** IBAN nie an das LLM und nie unmaskiert in Oberfläche, Audit oder Export („DE59 •••• 3344“).
* **Offline:** alle Prüfungen ohne Netz; das BZSt bestätigt nach § 18e UStG ausländische USt-IdNrn. (deutsche nur im
  Sonderfall Lagerhalter), VIES auch deutsche (Stand prüfen, [`docs/Quellen.md`](docs/Quellen.md)).

## Tests und Abnahme

317 Tests – Python 3.11.18: 317 bestanden (57,56 s), Python 3.13.18: 317 bestanden
(55,49 s), jeweils in frischer Umgebung aus `uv.lock`. Laufzeiten (Ziel): Monatsverlauf 0,77 s
(≤ 1,5 s), Erstlauf 3,54 s (≤ 12 s), Folgelauf 0,21 s (≤ 1 s) –
Nachweis in [`docs/Endabnahme.md`](docs/Endabnahme.md).

## Projektstruktur

```text
app.py                   Oberfläche (7 Tabs)            src/agent.py            Faktenblatt, Faktenprüfung, LLM-Clients
src/ui_design.py         Designsystem 1:1 VarianceAI    src/sicherheitstest.py  Injection- und IBAN-Test
src/ui_diagramme.py      Diagramme (Altair)             src/zwischenspeicher.py Ergebniscache nach Dateistand
src/exporter.py          Excel, Power BI, Migr.-Cockpit src/bericht_export.py   Readiness-Bericht PPTX/PDF
src/config.py            Stichtag, Pfade, Seeds         src/regeln.py           Regelkatalog (46 Regeln) + Engine
src/suite.py             gemeinsames Zahlenwerk         src/dubletten.py        Blocking, Score, Cluster, Messung
src/suite_referenz.json  Referenz aus den 3 Agenten     src/golden_record.py    Survivorship, Entscheidungen
src/seed_data.py         SAP-ECC-Stil, Seed 42/4242     src/migration.py        CVI-Readiness
src/datenbasis.py        Laden, Monatsstände            src/analyse.py          Gesamtlauf, Kennzahlen, Verlauf
src/pruefziffern.py      IBAN, USt-IdNr., PLZ, E-Mail   src/ust_online.py       VIES (optional, aus)
src/normalisierung.py    Namen, Rechtsformen, Straßen   tools/                  Referenz, Demo-Lauf, Messung, Doku
desktop/                 unverändert aus VarianceAI (nur app.toml und Symbol projektspezifisch)
docs/                    methodik · Suite-Abstimmung · Endabnahme · Änderungsprotokoll · Quellen · SAP-Anbindung.docx ·
                         Kennzahlen_und_Diagramme.docx · STANDARD.md (unverändert aus VarianceAI)
```

## Grenzen

Synthetische Daten; formale Prüfungen bestätigen nicht die Existenz einer IBAN oder die Vergabe einer USt-IdNr.;
Dubletten über zwei PLZ mit vertauschter Wortfolge und ohne IBAN/USt-IdNr. findet das Blocking nicht; Vertriebsgebiet
je PLZ-Leitzone ist eine Demo-Annahme; die Archivierungsquote ist ein Demo-Effekt der Suite; SAP-Tabellen, Feldnamen
und die Migration-Cockpit-Vorlage sind Beispiele (im System prüfen); keine Rechts- oder Steuerberatung.

Lizenz: MIT · © 2026 Sherwan Shweish
