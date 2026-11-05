# Daten

Ausschließlich **synthetische Daten** der fiktiven *RheinMain Industrietechnik GmbH*.

```bash
uv run python run_agent.py daten               # Seed 42  → data/sample/dataguard.db + wahrheit.json
uv run python run_agent.py daten --seed 4242   # Prüf-Seed → data/pruefseed/
```

Datenbanken sind per `.gitignore` ausgeschlossen und werden reproduzierbar erzeugt. `sample/wahrheit.json` listet alle
absichtlich eingebauten Fehler, Dublettencluster und Sonderfälle – **nur für Tests und Messung**; die Prüf-Engines
lesen sie nie.

| Tabelle | Inhalt (SAP-ECC-Exportstil) |
|---|---|
| `KNA1`, `KNB1`, `KNVV`, `KNBK` | Debitoren: allgemein, Buchungskreis 1000, Vertriebsgebiet, Bank (IBAN nur intern) |
| `LFA1`, `LFB1`, `LFBK` | Kreditoren: allgemein, Buchungskreis 1000, Bank (IBAN nur intern) |
| `ADRC` | Anschrift, Telefon, E-Mail (ADRC-/ADR6-ähnlich) |
| `CDHDR`, `CDPOS` | Änderungsprotokoll – wer, wann, Feld alt/neu; IBAN und Kontonummer nur maskiert |
| `ZDG_VERKEHR` | letzte Buchung und offene Posten je Satz (Echtbetrieb: BSAD/BSAK/BSID/BSIK bzw. ACDOCA) |
| `ZDG_VERKEHR_MONAT` | letzte Buchung je Monatsende der 18 aktiven Partner (Rekonstruktion der Monatsstände) |
| `ZDG_META` | Seed, Stichtag, Buchungskreis, Kennzeichnung „synthetisch“ |
