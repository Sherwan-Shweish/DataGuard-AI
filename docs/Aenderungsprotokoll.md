# Änderungsprotokoll · DataGuard-AI

## 1.0.0 · Suite-Nachprüfung (finaler Stand)

- **Eine Zeitachse mit FlowAudit-AI:** Bankänderungen der Lieferanten tragen das absolute Datum aus FlowAudit-AI
  (fester Demo-Stichtag 28.10.2026): 100100 am 01.04.2026, 100400 am 23.10.2026. Die Änderung von 100400 liegt nach
  dem Stammdatenstand 30.09.2026 und ist in DataGuard noch nicht sichtbar – FlowAudit-AI fängt sie im laufenden
  Rechnungseingang ab. Bisher war sie relativ zum Stichtag auf den 25.09.2026 gespiegelt (zwei Daten für dasselbe
  Ereignis). Den Vier-Augen-Fall der Regel A04 zeigt jetzt ein laufender Kreditor des eigenen Bestands, deterministisch
  ohne Zufall gewählt; alle übrigen Daten unverändert (Wahrheitsdatei: nur A04 verschoben).
- Querverweise im Cockpit präzisiert und gekürzt (Vertriebsgebiet ≠ PLZ: „Suite-Umsätze unberührt“, weil nur
  Altsätze ohne Umsatz betroffen sind); neue Gesprächsfrage zur Zeitachse in SAP-Anbindung.
- Suite-Abstimmung: falsche Annahme „FlowAudit-Stichtag = Tagesdatum“ korrigiert; erledigte Rückportierungen
  (FlowAudit-AI 1.2.1, ControllAI 2.2.1) vermerkt. Tests, Messungen, Dokumente und Screenshots neu erzeugt.

## 1.0.0 · Phase 3 – Exporte, Dokumentation, Suite-Abschluss (Abnahmestand)

- **Quoten je Objekt:** Readiness- und Archivierungsquote getrennt nach Debitoren und Kreditoren in Kennzahlenleiste,
  Readiness-Tab, Faktenblatt, Management-Summary und Readiness-Bericht; ein Erklärsatz direkt am Wert
  („Debitorenquote folgt aus der Suite-Vorgabe: Umsatz nur bei 12 Kunden“). Archivierungsquote 80,6 % bleibt –
  bewusste Suite-Vorgabe, keine weitere Datenänderung.
- **Exporte** (`src/exporter.py`, `src/bericht_export.py`, Seitenleiste „Datenexport“): Excel *Bereinigungsliste* mit
  Blatt *Gegenprüfung* (DAMA-Scores, Readiness- und Archivierungsquoten gesamt und je Objekt per Formel, Status
  grün/rot), Excel *Golden-Record-Entscheidungen*, *Readiness-Bericht* PowerPoint/PDF (IBCS, nur gültig freigegebene
  Kommentare), *Power-BI-Paket* (Sternschema, DAX, deutsches CSV), *Übergabe-CSV Migration Cockpit* als Beispiel ohne
  Bankverbindung. Formel-/CSV-Injection wird entschärft. Tests: keine unmaskierte IBAN und keine Kontonummer in
  Excel, PowerPoint, PDF, Power BI und CSV; Gegenprüfung per LibreOffice „alles OK“.
- **Laufzeittests:** In der Testsuite nur großzügige Schutzwerte (Verlauf ≤ 5 s, Erstlauf ≤ 30 s, Folgelauf ≤ 3 s);
  Zielwerte mit `tools/endabnahme_messen.py` nachgewiesen (`docs/Endabnahme.md`).
- **Suite-Abschluss:** Kontrolltabelle über alle vier Agenten in `docs/Suite-Abstimmung.md`, abgesichert durch
  `tests/test_suite_kontrolltabelle.py` (feste Konstanten); README-Abschnitt „Teil der RheinMain Controlling-Suite“.
- **Optionale VIES-Bestätigung** `src/ust_online.py` (standardmäßig aus, Tests nur mit Attrappe).
- **Dokumentation:** README, methodik.md, Suite-Abstimmung.md und Endabnahme.md per Skript (`tools/doku_erzeugen.py`)
  aus den Messdateien; Erklärdokumente `docs/SAP-Anbindung.docx` und `docs/Kennzahlen_und_Diagramme.docx` (docx-js,
  arabische Fassungen separat geliefert); Quellen.md erweitert.
- Golden-Record-Vorschläge: Cluster mit aktivem Suite-Partner zuerst, dann offene Cluster, dann nach Score.

## 1.0.0-Phase2 · Oberfläche, KI-Agent, Human-in-the-Loop

- Sieben Tabs mit Leitfrage, Kennzahlenleiste mit 12-Monats-Sparklines, Expander „So ist die App aufgebaut“,
  Umschalter hell/dunkel nur in `desktop`/`lokal`, Fehlergrenze je Tab, nur der sichtbare Tab wird berechnet.
- KI-Agent mit pseudonymisiertem Faktenblatt, Faktenprüfung, regelbasiertem Ersatz; Anbieter Mock/Claude/Gemini mit
  Rückfall. Freigabe namentlich mit Fingerabdruck (ungültig nach Änderung). Append-only Audit mit JSON-Export.
- Sicherheitstests Datentext-Injection und IBAN-Ausgabe; selbst gefundene Lücke geschlossen: IBAN-Bruchstücke
  gelangten über Verwerfungsgründe („Zahl 0611 ohne Beleg“) ins Audit – IBAN-artige Folgen werden jetzt vor der
  Zahlenprüfung entfernt.
- Readiness-Zerlegung je Monat (bereinigt / neue Blocker durch Neuanlagen / Änderungen / Zeitablauf) aus dem
  Änderungsprotokoll; Governance-Empfehlung „Data Firewall“.
- Laufende Kreditoren (Buchungsdaten ohne Beträge), Neuanlagen auf 97 begrenzt, alles neu gemessen.
- Monatsverlauf beschleunigt: vektorisierte Rekonstruktion, Rechenspeicher, fortgeschriebene Dublettenkandidaten,
  spaltenweise Kontextregeln (8,4 s → rund 1,2 s); Ergebniscache nach Funktion und Dateistand.

## 1.0.0-Phase1 · Fundament, Datenbasis und Prüf-Engines

- Projekt nach Agenten-Standard v1 (uv, ruff, pytest 3.11/3.13, desktop/ aus VarianceAI, eigenes Symbol).
- Datengenerator im SAP-ECC-Stil (Seed 42, Prüf-Seed 4242) mit Wahrheitsdatei; Suite-Referenz aus den drei Agenten.
- 46 Regeln als Daten über fünf DAMA-Dimensionen; Dublettenerkennung mit Blocking, Score und Union-Find;
  Golden Record; CVI-Readiness; 12 Monatsstände aus CDHDR/CDPOS; Kommandozeile.
