# Quellen und Prüfhorizont · DataGuard-AI 1.0.0

Recherchiert am 03./04.11.2026. SAP-Tabellen, Feldnamen und Werkzeugbezeichnungen sind Beispiele und im konkreten
System und Release zu prüfen. Rechtliche und regulatorische Angaben: **Stand prüfen**. Keine produktive Anbindung
wurde behauptet oder durchgeführt. Demo-Zahlen stammen ausschließlich aus `docs/demolauf.json`, nicht aus diesen
Quellen.

## SAP – Wartung, Geschäftspartner, Migration

| Nr. | Thema | Aussage in DataGuard-AI | Quelle |
|---|---|---|---|
| S1 | SAP-Wartung | Mainstream-Wartung SAP ERP 6.0 bis Ende 2027, erweiterte Wartung (kostenpflichtig) bis Ende 2030 | [SAPinsider: SAP support deadlines 2027, 2030, 2033](https://sapinsider.org/blogs/sap-support-deadlines-2027-2030-2033/) · [The Register, 28.01.2025](https://www.theregister.com/2025/01/28/sap_extends_support_deadline/) |
| S2 | Geschäftspartner/CVI | BP führend in S/4HANA; Debitoren/Kreditoren werden über die CVI zu Geschäftspartnern | [SAP Community: Simplification Item Business Partner Approach / CVI](https://blogs.sap.com/2016/04/29/simplification-item-business-partner-approach-customer-vendor-integration-cvi) · [SAP Community: Business Partner – CVI in S/4HANA](https://blogs.sap.com/2017/02/22/business-partner-customer-vendor-integration-s4-hana) |
| S3 | CVI-Cockpit | Werkzeug zur Synchronisation Debitor/Kreditor → BP (Bezeichnung im System prüfen) | [SAP Community: Improvements to CVI Cockpit (EHP 8 SP17)](https://blogs.sap.com/2022/02/16/improvements-to-cvi-cockpit-as-of-sap-erp-6.0-ehp-8-sp17/) |
| S4 | Readiness Check | SAP Readiness Check enthält eine Analyse der Customer-Vendor-Integration | [SAP Community: CVI analysis check in SAP Readiness Check](https://blogs.sap.com/2021/03/29/new-customer-vendor-integration-analysis-cvia-check-in-sap-readiness-check-is-now-live/) · [SAP Help: Key Feature Overview SAP Readiness Check (PDF)](https://help.sap.com/doc/bb0e7ba5158c424ab7ce010228bf1de1/latest/en-US/Key%20Feature%20Overview%20SAP%20Readiness%20Check.pdf) |
| S5 | Migration Cockpit | Migrationsobjekte u. a. für Kunde und Lieferant; Vorlagen je Release | [SAP Help: Migration Objects for SAP S/4HANA (PDF, 1909)](https://help.sap.com/doc/69dd0f1ef0034261ab6e617e0b2beb21/1909.000/en-US/MigrationObjects_OP_EN.pdf) · [SAP Learning: Introducing the SAP S/4HANA Migration Cockpit](https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition/introducing-the-sap-s-4hana-migration-cockpit) |
| S6 | Kunde = Lieferant | ein Geschäftspartner mit zwei Rollen statt zwei BP | [SAP Community: Merge customer and vendor into single business partner](https://blogs.sap.com/2020/08/31/sap-s-4hana-business-partner-conversion-merge-customer-and-vendor-into-single-business-partner/) |
| S7 | BP-Tabellen | BUT000 (Zentraldaten), BUT0BK (Bank), DFKKBPTAXNUM (Steuernummern), CVI_CUST_LINK/CVI_VEND_LINK (Verknüpfung) – Beispiele | [SAP Help: Affected Tables in Business Partner](https://help.sap.com/saphelp_470/helpdata/en/98/847339e5013f60e10000000a11402f/content.htm) · [LeanX: DFKKBPTAXNUM](https://leanx.eu/en/sap/table/dfkkbptaxnum.html) · [LeanX: CVI_VEND_LINK](https://leanx.eu/en/sap/table/cvi_vend_link.html) |
| S8 | OData-Schnittstelle | Geschäftspartner lesen über den Service API_BUSINESS_PARTNER (Beispiel) | [SAP Community: How to access Business Partner OData service](https://blogs.sap.com/2020/09/11/how-access-business-partner-odata-service-in-sap-s-4hana-cloud/) |
| S9 | Datasphere | Lesezugriff über einen Datenbankbenutzer (Variante „Datasphere/BW“) | [SAP Help: SAP Datasphere – Create a Database User](https://help.sap.com/docs/SAP_DATASPHERE/be5967d099974c69b77f4549425ca4c0/798e3fd6707940c3bd2219b2d1ebaac2.html) |
| S10 | Änderungsbelege | CDHDR/CDPOS als Quelle des Verlaufs; Data Aging beachten | [SAP Help: Data Aging für Änderungsbelege](https://help.sap.com/docs/ABAP_PLATFORM_NEW/f0944a4717b5464f8d2343f9a44ff65b/0acf6fa9848045b7ad81508c8b1f4f9d.html?locale=de-DE) |

## Prüfregeln und Normen

| Nr. | Thema | Aussage | Quelle |
|---|---|---|---|
| N1 | IBAN | ISO 13616, Prüfziffer Mod 97 (ISO 7064), Länge je Land laut IBAN-Registry | [SWIFT: IBAN Standard und Registry](https://www.swift.com/standards/data-standards/iban) |
| N2 | USt-IdNr. DE Prüfziffer | ISO 7064 MOD 11,10 – gleiche Logik wie FlowAudit-AI 1.2.1 | FlowAudit-AI `src/einvoice_parser.ust_id_de_gueltig`; Gegentest python-stdnum (`stdnum.de.vat`) |
| N3 | BZSt-Bestätigung | BZSt bestätigt nach § 18e UStG ausländische USt-IdNrn.; deutsche nur auf Antrag für Lagerhalter | [IHK Frankfurt am Main: USt-IdNr.-Bestätigungsverfahren](https://www.frankfurt-main.ihk.de/recht/uebersicht-alle-rechtsthemen/steuerrecht/umsatzsteuer-international/umsatzsteuer-identifikationsnummer-bestaetigungsverfahren-5195882) |
| N4 | VIES | Prüfung von USt-IdNrn. aller EU-Mitgliedstaaten (inkl. DE); optionaler Schritt `src/ust_online.py`, standardmäßig aus | [Your Europe: Check a VAT number (VIES)](https://europa.eu/youreurope/vies_en) |
| N5 | DAMA-Dimensionen | Vollständigkeit, Gültigkeit, Eindeutigkeit, Konsistenz, Aktualität | DAMA International: *DAMA-DMBOK*, 2. Aufl. 2017, Kap. 13 · [IBM: Data quality dimensions](https://www.ibm.com/docs/en/DSXDOC/wsj/quality/dq-dimensions.html) |
| N6 | Ähnlichkeitsmaße | token_sort_ratio, ratio | [RapidFuzz (Dokumentation)](https://rapidfuzz.github.io/RapidFuzz/) |
| N7 | CSV-/Formel-Injection | Werte, die mit `=`, `@`, `+`/`-` beginnen, in Exporten entschärfen | [OWASP: CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection) |
| N8 | IBCS | Notation der Berichte (AC, Farben nach Wirkung) | [IBCS: Standards Book](https://www.ibcs.com/resource/ibcs-standards-book) |

## Datenschutz

| Nr. | Thema | Aussage | Quelle |
|---|---|---|---|
| D1 | DSGVO | Einzelkaufleute und Ansprechpartner sind natürliche Personen → personenbezogene Daten (Art. 4 Nr. 1); Grundsätze Zweckbindung und Datenminimierung (Art. 5 Abs. 1 lit. b, c); Löschung/Archivierung nach Zweckfortfall | [EUR-Lex: Verordnung (EU) 2016/679](https://eur-lex.europa.eu/legal-content/DE-EN/TXT/?uri=CELEX%3A32016R0679) |
| D2 | Aufbewahrung | Handels- und steuerrechtliche Aufbewahrungsfristen begrenzen das Löschen archivierter Stammsätze (Stand prüfen) | [§ 257 HGB](https://www.gesetze-im-internet.de/hgb/__257.html) · [§ 147 AO](https://www.gesetze-im-internet.de/ao_1977/__147.html) |
