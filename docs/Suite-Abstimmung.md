# Suite-Abstimmung · DataGuard-AI 1.0.0 (Abschluss der RheinMain Controlling-Suite)

DataGuard-AI ist der vierte und letzte Agent der Suite. Alle vier Agenten arbeiten mit derselben fiktiven Firma und
denselben Schlüsseln. Zur Laufzeit liest DataGuard nur `src/suite_referenz.json`; die Datei wurde mit
`tools/suite_referenz_erzeugen.py` einmal je Referenzprojekt mit dessen Umgebung erzeugt. Die Referenzagenten wurden
nur gelesen (Abgleich gegen die gelieferten ZIP-Dateien: unverändert, siehe `docs/Endabnahme.md`).

## Kontrolltabelle über alle vier Agenten

| Wert | DataGuard-AI 1.0.0 | FlowAudit-AI 1.2.1 | VarianceAI 1.2 | ControllAI 2.2.1 | Test in DataGuard |
|---|---|---|---|---|---|
| Stichtag | 30.09.2026 | 28.10.2026 (fester Demo-Stichtag, Rechnungseingang im Folgemonat) | 30.09.2026 | 30.09.2026 | `test_stichtag_firma_buchungskreis` |
| Firma | RheinMain Industrietechnik GmbH, Mainzer Straße 120, 65189 Wiesbaden | gleich | gleich | gleich | `test_stichtag_firma_buchungskreis` |
| Buchungskreis | 1000 | 1000 | 1000 | 1000 | `test_stichtag_firma_buchungskreis` |
| 12 Kunden K101–K304 | Stammsätze (Nummer, Name, Region unverändert) | – | Quelle (Umsatz, Faktura) | Umsatz/HK centgleich | `test_zwoelf_kunden_wie_varianceai`, `test_datenbank_traegt_dieselben_schluessel` |
| 6 Lieferanten 100100–100600 | Stammsätze (Name, Bank, USt unverändert) | Quelle | – | – | `test_sechs_lieferanten_wie_flowaudit`, `test_datenbank_traegt_dieselben_schluessel` |
| Summe Umsatz 2025 | 83.873.069,96 € (Kontrollwert) | – | 83.873.069,96 € | 83.873.069,96 € | `test_zwoelf_kunden_wie_varianceai`, `test_referenz_kontrollwerte` |
| EBIT 2025 | nicht genutzt – nur als Referenz zitiert | – | 8.720.441,56 € | 8.720.441,56 € | – (Zitat, siehe unten) |

**EBIT 2025 = 8.720.441,56 €** wird hier nur als Referenz zitiert (Quelle: ControllAI 2.2.1, `docs/Suite-Abstimmung.md`
und `src/suite_referenz.json` → `summen.2025.ebit_cent = 872044156`, dort centgleich mit VarianceAI 1.2 belegt).
DataGuard-AI rechnet nicht mit Beträgen; jeder Wert, den DataGuard selbst nutzt, ist durch einen Test in
`tests/test_suite_kontrolltabelle.py` (feste Konstanten, unabhängig von der JSON-Datei) und
`tests/test_suite_referenz.py` abgesichert.

### 12 Kunden (VarianceAI – führendes Finanzsystem)

| Kunde | Name | Region | Umsatz 2025 (€) | letzte Faktura | Branche (ControllAI) |
|---|---|---|---:|---|---|
| K101 | Hanse Fördertechnik GmbH | NORD | 9.486.714,97 | 03.09.2026 | Maschinenbau |
| K102 | Weser Anlagenbau AG | NORD | 7.585.231,05 | 20.09.2026 | Energie |
| K103 | Elbe Automation KG | NORD | 5.918.340,78 | 25.09.2026 | Chemie |
| K104 | Nordwind Maschinen GmbH | NORD | 4.076.202,58 | 27.09.2026 | Lebensmittelindustrie |
| K201 | Alpen Antriebstechnik GmbH | SUED | 11.355.882,87 | 12.09.2026 | Lebensmittelindustrie |
| K202 | Neckar Werkzeugmaschinen AG | SUED | 9.108.920,62 | 21.09.2026 | Logistik |
| K203 | Isar Robotics GmbH | SUED | 7.157.397,75 | 02.09.2026 | Maschinenbau |
| K204 | Bodensee Verpackungstechnik KG | SUED | 4.860.552,69 | 13.09.2026 | Energie |
| K301 | Rheinland Industrieanlagen GmbH | WEST | 8.527.853,35 | 12.09.2026 | Automobilzulieferer |
| K302 | Ruhr Stahlbau AG | WEST | 6.792.788,58 | 22.09.2026 | Maschinenbau |
| K303 | Mosel Prozesstechnik GmbH | WEST | 5.347.122,98 | 19.09.2026 | Chemie |
| K304 | Eifel Fördersysteme KG | WEST | 3.656.061,74 | 02.09.2026 | Logistik |
| **Summe** | | | **83.873.069,96** | | |

### 6 Lieferanten (FlowAudit-AI)

| Lieferant | Name | IBAN (maskiert) | USt-IdNr. | Ort | ZTERM |
|---|---|---|---|---|---|
| 100100 | Hessen Hydraulik GmbH | DE59 •••• 3344 | DE214365872 | 60314 Frankfurt am Main | ZB14 |
| 100200 | Taunus Präzisionsteile KG | DE20 •••• 5667 | DE287654316 | 61352 Bad Homburg v. d. Höhe | ZB30 |
| 100300 | Mainzer Elektrotechnik AG | DE14 •••• 0400 | DE149832767 | 55118 Mainz | ZB10 |
| 100400 | Rheingau Logistik & Verpackung GmbH | DE46 •••• 7654 | DE265437897 | 65343 Eltville am Rhein | ZB30 |
| 100500 | Odenwald Industriebedarf GmbH | DE25 •••• 8990 | DE231987458 | 64283 Darmstadt | ZB30 |
| 100600 | Bürowelt Wiesbaden e.K. | DE07 •••• 6777 | DE298765120 | 65183 Wiesbaden | ZB30 |

Eigene USt-IdNr. der RheinMain: DE812345673 (gültige Prüfziffer, `test_ust_de_wie_flowaudit`).

## Gemeinsame Schlüssel

| Schlüssel | Quelle | Verwendung in DataGuard |
|---|---|---|
| Buchungskreis 1000, Firma, Anschrift | alle Agenten | Kopfzeile, Bericht, Exporte |
| Debitoren K101–K304 (Name, Region) | VarianceAI `seed_data.KUNDEN` | 12 aktive Debitoren, Felder unverändert |
| Umsatz 2025 und letzte Faktura je Kunde | VarianceAI Universal Journal (Ist, 800000, ohne 9099999999) | Kontrollwerte, letzte Buchung |
| Branche je Kunde | ControllAI `kunden` | KNA1-BRSCH der 12 aktiven Debitoren |
| Kreditoren 100100–100600 (Anschrift, USt-IdNr., E-Mail, BLZ/Konto/BIC, ZTERM) | FlowAudit-AI `seed_data.LIEFERANTEN` | 6 aktive Kreditoren, Felder unverändert |
| IBAN | FlowAudit-AI `seed_data._iban` | LFBK-IBAN (nur maskiert sichtbar) |
| Bankänderungen 100100 (01.04.2026) und 100400 (23.10.2026) mit absolutem Datum | FlowAudit-AI `BANKAENDERUNGEN`, Stichtag 28.10.2026 | CDHDR/CDPOS bis 30.09.2026, Regel A04 |
| Kostenstellen 4100–4500, Produktgruppen ANT/STE/SEN, Regionen NORD/SUED/WEST | VarianceAI | nur Bezeichnungen |

## Kontrollwerte

| Kontrolle | Wert | Test |
|---|---|---|
| Summe Umsatz 2025 der 12 Kunden | 83.873.069,96 € | `test_referenz_kontrollwerte`, `test_zwoelf_kunden_wie_varianceai` |
| K101 Hanse Fördertechnik GmbH | 9.486.714,97 €, letzte Faktura 03.09.2026 | `test_referenz_kontrollwerte` |
| IBAN 100100 | DE59 •••• 3344 (Prüfziffer gültig) | `test_kreditoren_iban_und_ust_wie_flowaudit` |
| USt-IdNr. der 6 Lieferanten und der eigenen Firma | gültige Prüfziffer (ISO 7064 MOD 11,10) | `test_ust_de_wie_flowaudit` |
| Umsatz und HK 2025 je Kunde ControllAI = VarianceAI | Differenz 0 Cent (12 Kunden) | Abbruch im Erzeugungsskript, `test_controllai_abgleich_centgleich` |
| aktive Partner nur in Feldern fehlerhaft, die kein anderer Agent nutzt | 18 Sätze | `test_aktive_partner_nur_ergaenzt_nie_fehlerhaft_in_genutzten_feldern` |

## Ergänzte Felder (kein anderer Agent nutzt sie)

Straße/Hausnummer, PLZ, Ort, Telefon, E-Mail, USt-IdNr. und Anlagedatum der 12 Debitoren; Telefon, Sprache,
Kontengruppe, Abstimmkonto und Anlagedatum der 6 Kreditoren. PLZ passend zur Vertriebsregion (Leitzone 0–3 Nord,
4–6 West, 7–9 Süd). Befunde an den 18 Sätzen betreffen nur solche Felder bzw. die Eindeutigkeit: K304 ohne
Telefonnummer (V12), 100100 mit doppeltem Kreditor gleicher IBAN (E01/E03/E04), 100300 zugleich neuer Kunde ohne
Verknüpfung (E05). Die Bankänderung von 100100 am 01.04.2026 liegt außerhalb der 30-Tage-Frist (kein Befund).

### Eine Zeitachse für Bankänderungen

DataGuard und FlowAudit-AI verwenden dieselben Kalenderdaten. Die Bankänderung von 100400 am 23.10.2026 liegt
nach dem Stammdatenstand 30.09.2026; DataGuard sieht sie deshalb noch nicht – FlowAudit-AI erkennt sie im
laufenden Rechnungseingang (Stichtag 28.10.2026) und verlangt die Vier-Augen-Prüfung. Genau diese
Arbeitsteilung zeigt die Suite: periodische Stammdatenprüfung plus Kontrolle im laufenden Prozess. Den Vier-Augen-Fall
der Regel A04 zeigt DataGuard an einem laufenden Kreditor des eigenen Bestands (106671, Bankänderung am
25.09.2026), nicht an einem FlowAudit-Lieferanten.

## Altbestand, laufende Kreditoren und Archivierung

* **Debitoren:** Außer den 12 Suite-Kunden hat kein Debitor eine Buchung seit 2024 – nur diese Kunden haben Umsatz in
  VarianceAI und ControllAI. Folge: Archivierungsquote Debitoren 91,7 %.
* **Kreditoren:** 203 Sätze des Kreditoren-Altbestands tragen Buchungen 2024–2026 – nur Datum der letzten
  Buchung und Anzahl Belege, **keine Beträge**; gekennzeichnet als „aktiv laut Kreditorenbuchung, nicht Teil der
  FlowAudit-Stichprobe“. Archivierungsquote Kreditoren 66,4 % (realistischerer Wert).
* Neuanlagen der letzten 12 Monate ohne Buchung: 97 über beide Objekte (Korridor 80–120).
* Tests: `test_altbestand_ohne_umsatz_im_suitezeitraum`, `test_neuanlagen_der_letzten_12_monate_begrenzt`,
  `test_buchungsdaten_ohne_betraege`.

## Querverweise in der Oberfläche

| Befund in DataGuard | weiter in |
|---|---|
| doppelte Kreditoren mit gleicher IBAN (E03) = Doppelzahlungsrisiko | FlowAudit-AI (Einzelrechnung, Prävention) |
| Bankänderung ≤ 30 Tage (A04) | FlowAudit-AI (Vier-Augen-Prüfung, Rückruf) |
| Vertriebsgebiet passt nicht zur PLZ (K01) | VarianceAI / ControllAI (Umsatz je Region) |

## Abweichungen und Rückportierungsvorschläge

Keine Abweichungen im gemeinsamen Zahlenwerk. Bereits in die Referenzagenten übernommen: gültige USt-IdNr.-Prüfziffern
(FlowAudit-AI 1.2.1) und Umsatz/HK je Kunde centgleich mit VarianceAI (ControllAI 2.2.1). FlowAudit-AI arbeitet mit
dem festen Demo-Stichtag 28.10.2026 aus `data/invoices/manifest.json`; die Bankänderungen liegen
deshalb auf derselben Kalenderachse wie in DataGuard (siehe oben). Optional, falls die Agenten künftig Stammdaten
anzeigen: Anschrift und USt-IdNr. der 12 Kunden aus `src/suite_referenz.json` übernehmen.
