# Methodik – DataGuard-AI 1.0.0

Alle Werte stammen aus `docs/demolauf.json` (erzeugt mit `tools/demolauf_erzeugen.py`, Stichtag 30.09.2026,
synthetische Daten der fiktiven RheinMain Industrietechnik GmbH). Nichts ist geschätzt.

## 1. Datenbasis

| Merkmal | Wert |
|---|---|
| Debitoren / Kreditoren | 896 / 702 (gesamt 1.598) |
| aktive Partner der Suite | 18 (12 Debitoren aus VarianceAI, 6 Kreditoren aus FlowAudit-AI) |
| laufende Kreditoren – „aktiv laut Kreditorenbuchung, nicht Teil der FlowAudit-Stichprobe“ | 203 |
| Altbestand mit letzter Buchung vor 2024 | 1.036 |
| Altbestand nie bebucht | 243 |
| Neuanlagen ohne Buchung | 98 (davon in den letzten 12 Monaten angelegt: 97) |
| Regeln im Katalog | 46 |

**Warum diese Größe?** Ein Mittelständler mit rund 85 Mio. € Umsatz führt nach 15–20 Jahren ERP-Betrieb typisch
einige hundert bis über tausend Debitoren und Kreditoren, der größte Teil davon Altbestand. Rund 1.600 Sätze sind groß
genug, damit Blocking, Clusterbildung und Readiness-Trichter aussagekräftig werden, und klein genug für Laufzeiten unter
einer Sekunde je Gesamtlauf.

**Laufende Kreditoren.** Die Kostenstellenkosten in VarianceAI (rund 37,7 Mio. € im Jahr 2025) werden an weit mehr
Lieferanten gezahlt als an die 6 aus der FlowAudit-Stichprobe. Deshalb trägt ein Teil des Kreditoren-Altbestands
Buchungen 2024–2026 – **nur Datum der letzten Buchung und Anzahl Belege, keine Beträge** (Tabelle ZDG_BUCHUNGSDATEN),
damit nichts den Summen von VarianceAI widerspricht. Oberfläche und Exporte kennzeichnen diese Sätze als „aktiv laut
Kreditorenbuchung, nicht Teil der FlowAudit-Stichprobe“ (Test `test_altbestand_ohne_umsatz_im_suitezeitraum`,
Korridor 25–35 % des Kreditoren-Altbestands). Debitoren außer den 12 Suite-Kunden haben keine Buchung seit 2024.

### Archivierungs- und Readiness-Quote je Objekt

| Objekt | Sätze | archivieren | Archivierungsquote | zu migrieren | bereit | Readiness-Quote |
|---|---:|---:|---:|---:|---:|---:|
| Debitoren | 896 | 822 | 91,7 % | 74 | 42 | 56,76 % |
| Kreditoren | 702 | 466 | 66,4 % | 236 | 161 | 68,22 % |
| **Gesamt** | **1.598** | **1.288** | **80,6 %** | **310** | **203** | **65,48 %** |

Die Archivierungsquote von 80,6 % ist ein **Demo-Effekt der Suite**, kein Befund über „gute“ oder „schlechte“ Stammdaten: Nur die 12 Kunden aus VarianceAI haben Umsatz, und Altkunden dürfen keine Buchungen erhalten, die diesen Umsätzen widersprechen. Deshalb liegt die Debitorenquote bei 91,7 % (822 von 896) – sie folgt aus der Suite-Vorgabe. Die **Kreditorenquote von 66,4 %** ist der realistischere Wert. Im Echtbetrieb entscheidet die Archivierungsregel des Unternehmens (Frist, offene Posten, Aufbewahrungspflichten). Ein Korridor von 50–60 % wäre bei unverändertem Debitorenstamm rechnerisch nicht erreichbar: Die
archivierten Debitoren allein ergeben 51,4 % des Gesamtbestands. Die Quote wird deshalb ausgewiesen,
nicht angepasst; Gewichte und Schwellen sind unverändert.

**Gesprächsfrage: „Ist eine Archivierungsquote von 80 % realistisch?“** – Ehrlich: nein, nicht als Aussage über ein echtes Unternehmen. Sie ist ein Demo-Effekt der Suite: Umsatz haben nur die 12 Kunden aus VarianceAI, alle anderen Debitoren sind Altbestand ohne Buchung seit 2024 – dadurch liegt die Debitorenquote bei 91,7 %. Realistischer ist die Kreditorenquote von 66,4 %, weil dort laufend bebuchte Lieferanten im Bestand sind. Im Echtbetrieb hängt die Quote an der Archivierungsregel des Unternehmens – DataGuard macht die Regel sichtbar und zählt, entscheiden muss das Migrationsprojekt.

Datenmodell im Stil eines SAP-ECC-Exports: LFA1/LFB1/LFBK, KNA1/KNB1/KNBK/KNVV, ADRC (Anschrift, Telefon, E-Mail),
CDHDR/CDPOS (Änderungsprotokoll, IBAN nur maskiert), ZDG_VERKEHR (letzte Buchung, offene Posten – im Echtbetrieb aus
BSAD/BSAK bzw. ACDOCA), ZDG_BUCHUNGSDATEN (Buchungsdaten je Satz ohne Beträge).

## 2. Regelwerk und DAMA-Scores

Regeln sind Daten (`src/regeln.py`, Liste `REGELN`): je Regel ID, Objekt, SAP-Feld, DAMA-Dimension, Schweregrad,
Beschreibung, Begründung, Korrekturvorschlag und eine benannte Prüfung. Eine Prüfung liefert je Satz *verletzt*,
*bestanden* oder *nicht anwendbar* (z. B. wird die IBAN-Prüfziffer nur geprüft, wenn eine IBAN mit passender Länge
vorhanden ist – so entstehen keine Folgefehler).

Dimensionen nach DAMA-DMBOK (DAMA International, *DAMA-DMBOK: Data Management Body of Knowledge*, 2. Aufl. 2017,
Kap. 13; Stand prüfen): Vollständigkeit, Gültigkeit, Eindeutigkeit, Konsistenz, Aktualität.

* **Score je Dimension** = bestandene ÷ anwendbare Prüfungen (Satz × Regel) der Dimension × 100.
* **Gesamtscore** = ungewichteter Mittelwert der fünf Dimensionsscores.

| Dimension | Score 30.09.2026 |
|---|---:|
| Vollständigkeit | 99,32 % |
| Gültigkeit | 99,65 % |
| Eindeutigkeit | 95,81 % |
| Konsistenz | 98,82 % |
| Aktualität | 78,23 % |
| **Gesamtscore** (Mittelwert) | **94,37 %** |

Der niedrige Aktualitätsscore ist fachlich gewollt: Er zeigt Altbestand ohne Löschvormerkung (A01/A02). Achtung: Der
Score zählt **Prüfungen** (Satz × Regel), nicht Sätze – ein Satz mit drei Befunden zählt dreimal als „nicht bestanden“.

### Fehlerkatalog (Seed 42): eingebaut = gefunden

| Regel | Dimension | Schweregrad | Beschreibung | eingebaut | gefunden | anwendbar |
|---|---|---|---|---:|---:|---:|
| V01 | Vollständigkeit | Blocker | Name 1 fehlt | 2 | 2 | 1.598 |
| V02 | Vollständigkeit | Fehler | Straße fehlt | 8 | 8 | 1.598 |
| V03 | Vollständigkeit | Hinweis | Hausnummer fehlt | 10 | 10 | 1.590 |
| V04 | Vollständigkeit | Blocker | Postleitzahl fehlt | 4 | 4 | 1.598 |
| V05 | Vollständigkeit | Blocker | Ort fehlt | 3 | 3 | 1.598 |
| V06 | Vollständigkeit | Blocker | Land fehlt | 2 | 2 | 1.598 |
| V07 | Vollständigkeit | Fehler | Sprache fehlt | 12 | 12 | 1.598 |
| V08 | Vollständigkeit | Fehler | USt-IdNr. fehlt (EU-Ausland) | 6 | 6 | 197 |
| V09 | Vollständigkeit | Hinweis | USt-IdNr. fehlt (Inland, Gesellschaft) | 20 | 20 | 1.186 |
| V10 | Vollständigkeit | Fehler | Kreditor ohne Bankverbindung | 10 | 10 | 701 |
| V11 | Vollständigkeit | Hinweis | E-Mail fehlt | 27 | 27 | 1.598 |
| V12 | Vollständigkeit | Hinweis | Telefonnummer fehlt | 30 | 30 | 1.598 |
| V13 | Vollständigkeit | Fehler | Zahlungsbedingung fehlt | 6 | 6 | 1.598 |
| V14 | Vollständigkeit | Blocker | Abstimmkonto fehlt | 3 | 3 | 1.598 |
| V15 | Vollständigkeit | Blocker | Kontengruppe fehlt | 2 | 2 | 1.598 |
| G01 | Gültigkeit | Blocker | IBAN-Prüfziffer falsch (ISO 13616, Mod 97) | 6 | 6 | 934 |
| G02 | Gültigkeit | Blocker | IBAN-Länge passt nicht zum Land | 3 | 3 | 937 |
| G03 | Gültigkeit | Blocker | IBAN-Ländercode unbekannt | 2 | 2 | 939 |
| G04 | Gültigkeit | Fehler | Bankleitzahl im IBAN ≠ Stammdatum BLZ | 4 | 4 | 800 |
| G05 | Gültigkeit | Fehler | USt-IdNr.-Format ungültig | 6 | 6 | 1.443 |
| G06 | Gültigkeit | Fehler | USt-IdNr. (DE) Prüfziffer falsch | 5 | 5 | 1.249 |
| G07 | Gültigkeit | Blocker | PLZ-Format ungültig für das Land | 6 | 6 | 1.590 |
| G08 | Gültigkeit | Fehler | E-Mail-Syntax ungültig | 8 | 8 | 1.571 |
| G09 | Gültigkeit | Fehler | Sprache nicht zulässig | 3 | 3 | 1.586 |
| G10 | Gültigkeit | Hinweis | Telefon nicht international (+Ländervorwahl) | 13 | 13 | 1.568 |
| G11 | Gültigkeit | Fehler | Zahlungsbedingung unbekannt | 3 | 3 | 1.592 |
| G12 | Gültigkeit | Blocker | Land unbekannt | 2 | 2 | 1.596 |
| G13 | Gültigkeit | Fehler | BIC-Format ungültig | 3 | 3 | 939 |
| G14 | Gültigkeit | Hinweis | Freitext enthält eine Steueranweisung (Datentext-Angriff) | 1 | 1 | 1.598 |
| E01 | Eindeutigkeit | Blocker | Dublette sehr wahrscheinlich (Score ≥ 90) | Messung P/R | 53 | 862 |
| E02 | Eindeutigkeit | Fehler | Mögliche Dublette (Score 75–89) | Messung P/R | 2 | 862 |
| E03 | Eindeutigkeit | Blocker | Gleiche IBAN bei mehreren Kreditoren | 33 | 33 | 431 |
| E04 | Eindeutigkeit | Fehler | Gleiche USt-IdNr. bei mehreren Sätzen | 38 | 38 | 780 |
| E05 | Eindeutigkeit | Blocker | Kunde = Lieferant ohne Verknüpfung | 10 | 10 | 310 |
| K01 | Konsistenz | Fehler | Vertriebsgebiet passt nicht zur PLZ | 6 | 6 | 888 |
| K02 | Konsistenz | Blocker | Kontengruppe ohne BP-Gruppierung (CVI) | 56 | 56 | 1.596 |
| K03 | Konsistenz | Fehler | Land der USt-IdNr. ≠ Land der Anschrift | 3 | 3 | 1.437 |
| K04 | Konsistenz | Fehler | Bankland ≠ Land der IBAN | 2 | 2 | 937 |
| K05 | Konsistenz | Blocker | Nummer außerhalb des Nummernkreises der Kontengruppe | 6 | 6 | 1.540 |
| K06 | Konsistenz | Blocker | Nummernkonflikt Debitor/Kreditor | 8 | 8 | 310 |
| K07 | Konsistenz | Fehler | Verknüpfung Kunde/Lieferant einseitig | 4 | 4 | 24 |
| K08 | Konsistenz | Fehler | Löschvormerkung trotz offener Posten | 3 | 3 | 736 |
| A01 | Aktualität | Hinweis | Keine Buchung seit > 24 Monaten, keine Löschvormerkung | 433 | 433 | 1.257 |
| A02 | Aktualität | Hinweis | Nie bebucht und älter als 24 Monate, keine Löschvormerkung | 116 | 116 | 341 |
| A03 | Aktualität | Hinweis | Gesperrt ohne offene Posten, keine Löschvormerkung | 3 | 3 | 3 |
| A04 | Aktualität | Hinweis | Bankverbindung in den letzten 30 Tagen geändert | 1 | 1 | 939 |

*Eingebaut* stammt aus `data/sample/wahrheit.json` (nur für Tests und Messung), *gefunden* aus der Engine. Der Test
`test_eingebaute_fehler_werden_exakt_gefunden` prüft für beide Seeds Satz für Satz Gleichheit (außer E01/E02, die über
Precision/Recall gemessen werden).

## 3. Dublettenerkennung

1. **Normalisierung** (`src/normalisierung.py`): Kleinschreibung, ü→ue, ö→oe, ä→ae, ß→ss, Akzente; Rechtsformen
   vereinheitlicht und für den Namensvergleich entfernt (G.m.b.H. → gmbh, Aktiengesellschaft → ag …); Satzzeichen
   und Füllwörter („und“, „&“, „Co“) entfernt; „Straße/Strasse/Str.“ → „str“; Hausnummer ohne Leerzeichen.
2. **Blocking** – Kandidatenpaare je Objekt: Pass 1 gleiche PLZ, Pass 2 gleiche gültige IBAN oder gleiche USt-IdNr.,
   Pass 3 gleiche fünf ersten Zeichen des normalisierten Namens im selben Land.
3. **Score (0–100)** = 0,60 × Name (`rapidfuzz.token_sort_ratio`) + 0,25 × Straße + Hausnummer (`ratio`) + 0,15 × Ort
   (100 bei gleicher PLZ, sonst 0,6 × Ähnlichkeit des Ortsnamens) + 15 bei gleicher IBAN + 15 bei gleicher
   USt-IdNr. + 10 bei gleicher Telefonnummer − 20, wenn beide Sätze verschiedene USt-IdNrn. tragen; begrenzt auf 0–100.
4. **Schwellen:** ≥ 90 „sehr wahrscheinlich“ (Regel E01, Blocker), 75–89 „prüfen“ (E02, Fehler), darunter keine Meldung.
5. **Cluster** über transitive Paare ab 75 (Union-Find).
6. **Erklärbarkeit:** jedes Paar trägt Namens-, Straßen- und Ortswert, die harten Merkmale und den Beitrag jedes
   Bestandteils zum Score.

Gewichte und Schwellen wurden vor der ersten Messung festgelegt und danach **nicht** verändert – weder auf Seed 42
noch auf dem Prüf-Seed 4242 (gleiche Fehlerlogik, andere Zufallsfolge).

### Messung (Paarebene)

| Stichprobe | Schwelle | Precision | Recall | F1 | TP | FP | FN | wahre Paare | Blocking-Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Seed 42 (Entwicklung) | ≥ 75 | 95,87 % | 96,67 % | 96,27 % | 116 | 5 | 4 | 120 | 97,50 % |
| Seed 42 (Entwicklung) | ≥ 90 | 100,00 % | 92,50 % | 96,10 % | 111 | 0 | 9 | 120 | 97,50 % |
| Prüf-Seed 4242 | ≥ 75 | 99,02 % | 96,19 % | 97,58 % | 101 | 1 | 4 | 105 | 98,10 % |
| Prüf-Seed 4242 | ≥ 90 | 100,00 % | 87,62 % | 93,40 % | 92 | 0 | 13 | 105 | 98,10 % |

Blocking-Recall = Anteil der echten Dublettenpaare, die überhaupt verglichen wurden.

**Die zwei bewusst nicht erkannten Fälle** (in beiden Seeds eingebaut, um die Grenze des Blockings sichtbar zu machen):

| Objekt | Satz A | Satz B | Warum nicht gefunden |
|---|---|---|---|
| Debitor | Brenner Kältetechnik e.K., 34117 Kassel | Kältetechnik Brenner e.K., 37079 Göttingen | andere PLZ, vertauschte Wortfolge, keine IBAN/USt-IdNr. → kein Blocking-Pass |
| Kreditor | Ebert Messtechnik e.K., 64283 Darmstadt | Messtechnik Ebert e.K., 36037 Fulda | andere PLZ, vertauschte Wortfolge, keine IBAN/USt-IdNr. → kein Blocking-Pass |

Abhilfe im Echtbetrieb: zusätzlicher Pass über Telefonnummer oder sortierte Namenstoken (Kosten: mehr Vergleiche).

**Alle Fehlerfälle ab Schwelle 75** (FN = echte Dublette nicht gemeldet, FP = gemeldet, aber keine Dublette):

| Stichprobe | Art | Paar | Score | Grund |
|---|---|---|---:|---|
| Seed 42 | FN | Sommer Werkstofftechnik e.K. (Wuppertal) ↔ Sommer Werkstofftechnik e. Kfm. (Mannheim) | 69,4 | Score unter 75 |
| Seed 42 | FN | Brenner Kältetechnik e.K. (Kassel) ↔ Kältetechnik Brenner e.K. (Göttingen) | – | nicht verglichen (kein Blocking-Pass) |
| Seed 42 | FN | Sommer Werkstofftechnik e. Kfm. (Mannheim) ↔ Werkstofftechnik Sommer e.K. (Wuppertal) | – | nicht verglichen (kein Blocking-Pass) |
| Seed 42 | FN | Ebert Messtechnik e.K. (Darmstadt) ↔ Messtechnik Ebert e.K. (Fulda) | – | nicht verglichen (kein Blocking-Pass) |
| Seed 42 | FP | Frei Messtechnik AG ↔ Gerber Messtechnik AG | 77,4 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |
| Seed 42 | FP | Frei Automation AG ↔ Graf Automation AG | 75,0 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |
| Seed 42 | FP | Larsen Teknik A/S ↔ Nielsen Teknik A/S | 76,9 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |
| Seed 42 | FP | Meier Messtechnik AG ↔ Keller Messtechnik AG | 75,0 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |
| Seed 42 | FP | Nielsen Teknik A/S ↔ Hansen Teknik A/S | 87,0 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |
| Prüf-Seed 4242 | FN | Brenner Kältetechnik e.K. (Kassel) ↔ Kältetechnik Brenner e.K. (Göttingen) | – | nicht verglichen (kein Blocking-Pass) |
| Prüf-Seed 4242 | FN | Ebert Messtechnik e.K. (Darmstadt) ↔ Messtechnik Ebert e.K. (Fulda) | – | nicht verglichen (kein Blocking-Pass) |
| Prüf-Seed 4242 | FN | Nahe Anlagenbau GmbH (Aachen) ↔ Nahe Anlagenbau GmbH (Leipzig) | 68,3 | Score unter 75 |
| Prüf-Seed 4242 | FN | Nahe Anlagenbau GmbH (Chemnitz) ↔ Nahe Anlagenbau GmbH (Leipzig) | 71,0 | Score unter 75 |
| Prüf-Seed 4242 | FP | Widmer Präzision AG ↔ Suter Präzision AG | 82,7 | ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |

Die FP-Fälle sind der Preis eines Namensvergleichs ohne harte Merkmale: gleicher Branchenbegriff und gleiche
Rechtsform am selben Ort. Deshalb meldet DataGuard 75–89 nur als „prüfen“ – die Entscheidung trifft ein Mensch.

### Aufwand durch Blocking

| Stichprobe | Objekt | ohne Blocking | mit Blocking | Pass 1 PLZ | Pass 2 IBAN/USt | Pass 3 Namensanfang |
|---|---|---:|---:|---:|---:|---:|
| Seed 42 | Debitoren | 400.960 | 4.706 | 2.699 | 33 | 2.105 |
| Seed 42 | Kreditoren | 246.051 | 2.748 | 1.730 | 53 | 1.092 |
| Prüf-Seed 4242 | Debitoren | 398.278 | 4.603 | 2.701 | 32 | 1.973 |
| Prüf-Seed 4242 | Kreditoren | 243.253 | 2.859 | 1.660 | 45 | 1.258 |

Seed 42: 7.454 statt 647.011 Vergleiche
(−98,8 %); Laufzeit der Dublettenerkennung 0,15 s.

**Warum kein Machine Learning?** Für Stammdaten ist Nachvollziehbarkeit Pflicht (Prüfer, Datenschutz, Fachbereich):
jede Meldung muss sich Feld für Feld begründen lassen. Regeln + Ähnlichkeitsmaße sind erklärbar, ohne Trainingsdaten
einsetzbar und mit der Wahrheitsdatei messbar. Ein lernendes Verfahren wäre ein möglicher nächster Schritt, sobald
genügend menschliche Entscheidungen (Golden-Record-Protokoll) als Trainingsdaten vorliegen.

## 4. Golden Record (Survivorship)

Je Cluster ein Vorschlag (`src/golden_record.py`). Überlebensregeln je Feld in dieser Reihenfolge:
1. gültig vor ungültig (Formal-/Prüfziffernprüfung), 2. vollständig vor leer, 3. Quelle mit Buchungen vor ungebuchter
Quelle (jüngste letzte Buchung zuerst), 4. jüngste Änderung (CDHDR, sonst Anlagedatum), 5. kleinste Nummer.
Zielnummer: aktiver Suite-Partner > jüngste Buchung > ohne Löschvormerkung > ältestes Anlagedatum > kleinste Nummer.
Reihenfolge der Bearbeitung: Cluster mit aktivem Suite-Partner zuerst, dann offene Cluster, dann nach Score.
Die Entscheidung (übernehmen / ablehnen / zurückstellen) trifft nur ein Mensch mit Vor- und Nachnamen. Ergebnis ist
eine Zuordnungsliste alt → neu; Quelldaten werden nie verändert. Demo: 63 Vorschläge.

## 5. Migration Readiness (CVI)

| Status | Definition | Anzahl |
|---|---|---:|
| archivieren | keine Buchung seit > 24 Monaten vor Stichtag, nie bebucht und angelegt vor > 24 Monaten, Löschvormerkung oder gesperrt ohne offene Posten | 1.288 |
| blockiert | mindestens ein CVI-Blocker (Regel mit `cvi_blocker`) oder Dublettencluster mit ≥ 2 zu migrierenden Sätzen | 66 |
| bereit nach Bereinigung | kein Blocker, aber Befunde mit Schweregrad „Fehler“ | 41 |
| bereit | höchstens Hinweise | 203 |

**Readiness-Quote = bereit ÷ (alle − archivieren)** = 203 ÷
310 = **65,48 %** (inkl. „bereit nach Bereinigung“:
78,71 %). Archivierungskandidaten zählen nicht in den Nenner – sonst würde die Quote mit
jedem Altsatz sinken, der gar nicht migriert werden soll. Befunde der Eindeutigkeit zählen nur, wenn mindestens ein
beteiligter Partner ebenfalls migriert wird (Beispiel K101: der nie bebuchte Altsatz wird archiviert – K101 ist
„bereit“).

Trichter: alle Sätze 1.598 → nicht archivieren 310 → ohne Blocker 244 → bereit 203.

## 6. Qualitätsverlauf und Zerlegung

Zwölf Monatsstände (31.10.2025–30.09.2026) werden aus dem aktuellen Stand rekonstruiert: später angelegte Sätze
werden ausgeblendet, spätere Feldänderungen aus CDPOS rückwärts zurückgenommen. Bankfelder stehen im Protokoll nur
maskiert und enthalten ausschließlich Änderungen von gültig nach gültig (Test), daher bleibt ihre Bewertung korrekt.
Jeder Stand wird mit derselben Engine neu bewertet – keine hart codierten Werte.

| Monatsende | DAMA-Gesamtscore | Readiness-Quote | Offene Cluster | Blocker-Befunde | Archivierungskandidaten | Sätze |
|---|---:|---:|---:|---:|---:|---:|
| 31.10.2025 | 91,48 % | 70,49 % | 37 | 51 | 1.261 | 1.505 |
| 30.11.2025 | 91,44 % | 69,55 % | 37 | 52 | 1.267 | 1.510 |
| 31.12.2025 | 91,42 % | 68,02 % | 38 | 54 | 1.273 | 1.520 |
| 31.01.2026 | 91,42 % | 68,40 % | 38 | 54 | 1.275 | 1.525 |
| 28.02.2026 | 91,45 % | 67,57 % | 38 | 58 | 1.275 | 1.534 |
| 31.03.2026 | 91,66 % | 65,53 % | 36 | 62 | 1.277 | 1.541 |
| 30.04.2026 | 91,92 % | 65,67 % | 36 | 62 | 1.278 | 1.546 |
| 31.05.2026 | 92,44 % | 66,55 % | 32 | 64 | 1.280 | 1.555 |
| 30.06.2026 | 93,05 % | 64,44 % | 33 | 74 | 1.283 | 1.567 |
| 31.07.2026 | 93,67 % | 64,01 % | 29 | 80 | 1.284 | 1.573 |
| 31.08.2026 | 94,10 % | 64,21 % | 26 | 81 | 1.287 | 1.586 |
| 30.09.2026 | 94,37 % | 65,48 % | 25 | 84 | 1.288 | 1.598 |

Der Effekt „DAMA steigt, Readiness sinkt“ ist nicht gesetzt, sondern ergibt sich aus dem Änderungsprotokoll. Je Monat
wird die Veränderung der Quote q = bereit ÷ basis exakt auf die Sätze verteilt:

Beitrag je Satz = (Δbereit − q₀ · Δbasis) ÷ basis₁ (q₀ ungerundet; Summe der Beiträge = Veränderung der Quote).

Die Ursache eines Satzes folgt aus Protokoll und Status: neu angelegt und bereit („Neuanlagen bereit“), neu angelegt
und blockiert bzw. nach Bereinigung („neue Blocker durch Neuanlagen“, nach Anlagebenutzer ERNAM), durch Änderungen
verbessert („bereinigt“, nach Änderungsbenutzer CDHDR-USERNAME) oder verschlechtert („verschlechtert durch Änderung“),
ohne Änderung durch Zeitablauf („Alterung/Zeitablauf“, z. B. 24-Monats-Grenze).

| Ursache | Summe 31.10.2025 → 30.09.2026 |
|---|---:|
| Neuanlagen bereit | +5,62 Pp |
| bereinigt | +4,87 Pp |
| Alterung/Zeitablauf | −0,96 Pp |
| verschlechtert durch Änderung | −3,79 Pp |
| neue Blocker durch Neuanlagen | −10,75 Pp |
| **Veränderung gesamt** | **−5,01 Pp** |

Größte Verursacher neuer Blocker (Anlagebenutzer, 12 Monate): VERTRIEB_03 −6,26 Pp, STAMM_ZENTRAL −2,59 Pp, KRED_SACHB3 −1,25 Pp, EINKAUF_07 −0,66 Pp.

**Governance-Empfehlung „Data Firewall“:** Pflichtfeld- und Dublettenprüfung bereits bei der Anlage – dieselbe
Regel- und Dubletten-Engine vor dem Speichern (Schwelle 75), Bankdaten nur mit Vier-Augen-Prüfung, Kennzahl „neue
Blocker durch Neuanlagen“ je Anlagebenutzer monatlich im Governance-Board. Die Bereinigung (+4,87 Pp)
wird sonst von neuen Blockern (−10,75 Pp) mehr als aufgezehrt.

## 7. KI-Agent und Faktenprüfung

Das LLM erhält nur ein Faktenblatt (Kennzahlen, Regel-IDs, pseudonymisierte Satznummern `SATZ-0001`, Merkmalswerte) –
nie IBAN, Bankdaten, Namen oder Freitexte. Jede Zahl, Regel-ID, Cluster-ID, jedes Pseudonym und Datum im Text wird
gegen das Faktenblatt geprüft; IBAN-artige Folgen werden vor der Zahlenprüfung entfernt und führen zum Verwerfen.
Bei Fehlschlag gilt der regelbasierte Text. Freigabe nur namentlich, gebunden an einen Fingerabdruck von Daten und
Entscheidungen.

## 8. Laufzeiten

| Messung | Wert | Ziel |
|---|---:|---:|
| Monatsverlauf 12 Stände ohne Ergebniscache (Median aus 5 frischen Prozessen) | 0,77 s | ≤ 1,5 s |
| Oberfläche Erstlauf (frischer Prozess) | 3,54 s | ≤ 12 s |
| Oberfläche Folgelauf (Tabwechsel, Median) | 0,21 s | ≤ 1 s |

Nachweis: `tools/endabnahme_messen.py` → `docs/endabnahme_messung.json`. Die Testsuite enthält nur großzügige
Schutzwerte (5 s / 30 s / 3 s), damit sie auf langsameren Rechnern nicht zufällig scheitert.

Technik: Der Verlauf wird vektorisiert rekonstruiert und inkrementell bewertet – unveränderte Sätze, Paare und
Regelergebnisse werden zwischen den Monatsständen aus einem Rechenspeicher übernommen, Dublettenkandidaten
fortgeschrieben, Kontextregeln spaltenweise mit numpy ausgewertet (Tests: inkrementell = vollständig neu berechnet,
spaltenweise = je Satz). Ein Ergebniscache je Funktion und Dateistand der Datenbank (Pfad, Änderungszeit, Größe)
macht Folgeläufe schnell; ändert sich die Datenbank, wird neu gerechnet.

## 9. Grenzen der Methode

* Formale Prüfungen bestätigen nicht, dass eine IBAN existiert oder eine USt-IdNr. vergeben ist (dafür Bank bzw.
  BZSt/VIES – optionaler, standardmäßig ausgeschalteter Online-Schritt `src/ust_online.py`).
* Dubletten mit anderer PLZ, anderem Namensanfang und ohne IBAN/USt-IdNr. findet das Blocking nicht (zwei Fälle oben).
* Namensähnliche, verschiedene Firmen am selben Ort erzeugen Meldungen „prüfen“ (FP) – deshalb entscheidet ein Mensch.
* PLZ-Zuordnung zum Vertriebsgebiet über die Leitzone ist eine Demo-Annahme der RheinMain.
* Die Archivierungsquote ist ein Demo-Effekt der Suite (Abschnitt 1); im Echtbetrieb gilt die Regel des Unternehmens.
* SAP-Tabellen, Feldnamen und Werkzeugbezeichnungen sind Beispiele – im System prüfen. Rechtliche Aussagen: Stand
  prüfen (Quellen in `docs/Quellen.md`).
