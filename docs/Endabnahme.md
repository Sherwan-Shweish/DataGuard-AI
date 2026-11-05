# Endabnahme · DataGuard-AI 1.0.0

Lokale Offline-Abnahme im Cloud-Container (Mock, keine kostenpflichtige API). Messrechner:
Linux x86_64 · 2 Kerne, Python 3.12.3, Messung am 04.11.2026 18:16.

| Kriterium | Ziel | Gemessener Wert | Status |
|---|---|---|---|
| Monatsverlauf ohne Ergebniscache | ≤ 1,5 s | 0,77 s (Median aus 5 frischen Prozessen) | erfüllt |
| Oberfläche Erstlauf | ≤ 12 s | 3,54 s (Median) | erfüllt |
| Oberfläche Folgelauf | ≤ 1 s | 0,21 s (Median über alle 7 Tabs) | erfüllt |
| Tests Python 3.11.18 (frische Umgebung aus uv.lock) | alle bestanden | 317 bestanden in 57,56 s | erfüllt |
| Tests Python 3.13.18 (frische Umgebung aus uv.lock) | alle bestanden | 317 bestanden in 55,49 s | erfüllt |
| ruff (F, E9, E501, B, UP, I; Zeilenlänge 120) | sauber | All checks passed! | erfüllt |
| desktop/ gegen VarianceAI | nur app.toml und Symbol verschieden | app.toml, ressourcen/AppIcon.icns, ressourcen/icon.png, ressourcen/icon.svg | erfüllt |
| Referenzagenten unverändert | Abgleich mit den ZIP-Dateien | VarianceAI-v1.2: 0 Unterschiede; FlowAudit-AI-v1.2.1: 0 Unterschiede; ControllAI-v2.2.1: 0 Unterschiede | erfüllt |
| Secrets im Repository | keine | keine gefunden | erfüllt |
| Kontrollwerte Zahlenwerk | per Test | Umsatz 2025 83.873.069,96 €, K101, IBAN 100100, USt-IdNrn., 12 Kunden, 6 Lieferanten | erfüllt |
| Eingebaute Fehler gefunden | eingebaut = gefunden | beide Seeds, Satz für Satz (`test_eingebaute_fehler_werden_exakt_gefunden`) | erfüllt |
| IBAN in Exporten | nie unmaskiert | Excel, PowerPoint, PDF, Power BI, Migration Cockpit (`test_kein_export_enthaelt_eine_unmaskierte_iban`) | erfüllt |
| Sicherheitstests | blockiert | Datentext-Injection und IBAN-Ausgabe (`test_sicherheitstest_*`, AppTest) | erfüllt |

Laufzeit-Einzelwerte (Sekunden): Verlauf 0,77, 0,77, 0,79, 0,75, 0,92;
Erstlauf 3,75, 3,42, 3,54, 3,71, 3,39; Folgelauf höchstens
0,38 s.

Die Testsuite enthält nur großzügige Schutzwerte (Monatsverlauf ≤ 5 s, Erstlauf ≤ 30 s, Folgelauf ≤ 3 s), damit
sie auf anderen Rechnern nicht zufällig scheitert. Die Zielwerte weist dieses Dokument mit
`tools/endabnahme_messen.py` nach (Rohdaten: `docs/endabnahme_messung.json`).

## Kennzahlen der Demo (Stichtag 30.09.2026)

| Kennzahl | Wert |
|---|---|
| DAMA-Gesamtscore | 94,37 % (+0,27 Pp) |
| Readiness-Quote gesamt / Debitoren / Kreditoren | 65,48 % / 56,76 % / 68,22 % |
| Archivierungsquote gesamt / Debitoren / Kreditoren | 80,6 % / 91,7 % / 66,4 % |
| Precision / Recall ab 75 (Seed 42 · Prüf-Seed 4242) | 95,87 % / 96,67 % · 99,02 % / 96,19 % |

## Prüfschritte (reproduzierbar)

```bash
UV_PROJECT_ENVIRONMENT=/tmp/venv3.11 uv sync --python 3.11 && UV_PROJECT_ENVIRONMENT=/tmp/venv3.11 uv run --python 3.11 pytest
UV_PROJECT_ENVIRONMENT=/tmp/venv3.13 uv sync --python 3.13 && UV_PROJECT_ENVIRONMENT=/tmp/venv3.13 uv run --python 3.13 pytest
uv run ruff check .
uv run python tools/demolauf_erzeugen.py       # docs/demolauf.json
uv run python tools/endabnahme_messen.py       # docs/endabnahme_messung.json
uv run python tools/endkontrolle.py <VarianceAI> <ZIP-Ordner> <Referenzordner>   # docs/endkontrolle.json
uv run python tools/doku_erzeugen.py           # README, methodik, Suite-Abstimmung, Endabnahme
```
