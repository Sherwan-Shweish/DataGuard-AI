"""Schreibt README.md, docs/methodik.md, docs/Suite-Abstimmung.md und docs/Endabnahme.md (Version 1.0.0).

Alle Zahlen stammen aus Programmläufen:
  • docs/demolauf.json            – tools/demolauf_erzeugen.py (Kennzahlen, Precision/Recall, Verlauf, Zerlegung)
  • docs/endabnahme_messung.json  – tools/endabnahme_messen.py (Laufzeiten gegen die Zielwerte)
  • docs/endkontrolle.json        – tools/endkontrolle.py (desktop-Diff, Referenzabgleich, ruff, Secrets)
  • docs/pytest-python311.txt / -python313.txt – Testläufe in frischen Umgebungen
  • src/suite_referenz.json       – gemeinsames Zahlenwerk der Suite
Aufruf: ``uv run python tools/doku_erzeugen.py``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

P = Path(__file__).resolve().parents[1]
d = json.loads((P / "docs/demolauf.json").read_text(encoding="utf-8"))
ref = json.loads((P / "src/suite_referenz.json").read_text(encoding="utf-8"))
wahrheit = json.loads((P / "data/sample/wahrheit.json").read_text(encoding="utf-8"))
vier_augen = wahrheit["sonderfaelle"]["vier_augen_bankaenderung"]
bank = {b["lifnr"]: b["datum"] for b in ref["bankaenderungen"]}


def _json(name: str) -> dict:
    datei = P / "docs" / name
    return json.loads(datei.read_text(encoding="utf-8")) if datei.exists() else {}


messung, kontrolle = _json("endabnahme_messung.json"), _json("endkontrolle.json")


def z(x, n=0):
    return f"{x:,.{n}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def pr(x, n=2):
    return f"{z(x, n)} %"


def pp(x):
    return ("+" if x > 0 else "−" if x < 0 else "±") + z(abs(x), 2) + " Pp"


def dt(s):
    j, m, t = str(s)[:10].split("-")
    return f"{t}.{m}.{j}"


def pytest_ergebnis(datei: str) -> tuple[str, str, str]:
    """(Python-Version, Anzahl bestanden, Sekunden) aus einem gespeicherten Testlauf."""
    pfad = P / "docs" / datei
    if not pfad.exists():
        return "?", "?", "?"
    text = pfad.read_text(encoding="utf-8")
    version = re.search(r"Python (\d+\.\d+\.\d+)", text)
    erg = re.search(r"(\d+) passed(?:, (\d+) \w+)*? in ([\d.]+)s", text)
    fehl = re.search(r"(\d+) failed", text)
    if fehl:
        return (version.group(1) if version else "?"), f"{erg.group(1) if erg else '?'} (FEHLER: {fehl.group(1)})", "?"
    return (version.group(1) if version else "?"), (erg.group(1) if erg else "?"), \
        (z(float(erg.group(3)), 2) if erg else "?")


k, kv = d["kennzahlen"], d["kennzahlen_vormonat"]
r = d["readiness"]
kat, umf = d["kategorien"], d["umfang"]
jo = d["je_objekt"]
alle = umf["DEBI"] + umf["KRED"]
zr = d["zerlegung_readiness"]
untergrenze = 100 * jo["DEBI"]["archivieren"] / alle
d42, d4242 = d["dubletten"]["seed_42"], d["dubletten"]["pruef_seed_4242"]
py311, py313 = pytest_ergebnis("pytest-python311.txt"), pytest_ergebnis("pytest-python313.txt")
tests_anzahl = py313[1] if py313[1].isdigit() else py311[1]
werte = messung.get("werte", {})
v0, v1 = d["verlauf"][0], d["verlauf"][-1]
nb: dict[str, float] = {}
for x in d["zerlegung_je_monat"]:
    if x["ursache"] == "neue Blocker durch Neuanlagen":
        nb[x["benutzer"]] = nb.get(x["benutzer"], 0) + x["beitrag_pp"]
nb_text = ", ".join(f"{b} {pp(w)}" for b, w in sorted(nb.items(), key=lambda x: x[1]))
reduktion42 = 100 * (1 - d42["ab_75"]["vergleiche_mit_blocking"] / d42["ab_75"]["vergleiche_ohne_blocking"])
OBJ = {"DEBI": "Debitoren", "KRED": "Kreditoren"}


def sek(schluessel: str) -> str:
    return f"{z(werte[schluessel], 2)} s" if schluessel in werte else "(Messung ausstehend)"


# ── wiederverwendete Bausteine ──────────────────────────────────────────────────────────────────────────────────

def dubtab(kurz: bool = False) -> str:
    if kurz:
        zeilen = ["| Stichprobe | Schwelle | Precision | Recall | F1 | Blocking-Recall |", "|---|---:|---:|---:|---:|---:|"]
    else:
        zeilen = ["| Stichprobe | Schwelle | Precision | Recall | F1 | TP | FP | FN | wahre Paare | Blocking-Recall |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, x in (("Seed 42 (Entwicklung)", d42), ("Prüf-Seed 4242", d4242)):
        for s in ("ab_75", "ab_90"):
            m = x[s]
            zellen = [name, f"≥ {m['schwelle']}", pr(100 * m["precision"]), pr(100 * m["recall"]), pr(100 * m["f1"])]
            if not kurz:
                zellen += [str(m["tp"]), str(m["fp"]), str(m["fn"]), str(m["wahre_paare"])]
            zellen.append(pr(100 * m["blocking_recall"]))
            zeilen.append("| " + " | ".join(zellen) + " |")
    return "\n".join(zeilen)


def grenzfaelle() -> str:
    """Die zwei bewusst eingebauten Blocking-Grenzfälle (in beiden Seeds nicht erkannt)."""
    faelle = [f for f in d42["fehlerfaelle_ab_75"]["fn"] if f["grund"].startswith("nicht verglichen")
              and any(f["a"]["name"] == g["a"]["name"] and f["b"]["name"] == g["b"]["name"]
                      for g in d4242["fehlerfaelle_ab_75"]["fn"])]
    return "\n".join(f"| {OBJ[f['objekt']][:-2]} | {f['a']['name']}, {f['a']['plz']} {f['a']['ort']} | "
                     f"{f['b']['name']}, {f['b']['plz']} {f['b']['ort']} | andere PLZ, vertauschte Wortfolge, "
                     "keine IBAN/USt-IdNr. → kein Blocking-Pass |" for f in faelle)


def fehlerfaelle_tab(x: dict, name: str) -> str:
    zeilen = []
    for f in x["fehlerfaelle_ab_75"]["fn"]:
        zeilen.append(f"| {name} | FN | {f['a']['name']} ({f['a']['ort']}) ↔ {f['b']['name']} ({f['b']['ort']}) | "
                      f"{'–' if f['score'] is None else z(f['score'], 1)} | {f['grund']} |")
    for f in x["fehlerfaelle_ab_75"]["fp"]:
        zeilen.append(f"| {name} | FP | {f['a']['name']} ↔ {f['b']['name']} | {z(f['score'], 1)} | "
                      "ähnlicher Branchenname, gleiche Rechtsform, gleicher Ort – verschiedene Firmen |")
    return "\n".join(zeilen)


quoten_tab = "\n".join(
    ["| Objekt | Sätze | archivieren | Archivierungsquote | zu migrieren | bereit | Readiness-Quote |",
     "|---|---:|---:|---:|---:|---:|---:|"]
    + [f"| {OBJ[o]} | {z(w['saetze'])} | {z(w['archivieren'])} | {pr(w['archivquote'], 1)} | "
       f"{z(w['nicht_archivieren'])} | {z(w['bereit'])} | {pr(w['readiness_quote'])} |" for o, w in jo.items()]
    + [f"| **Gesamt** | **{z(alle)}** | **{z(r['zaehlung']['archivieren'])}** | **{pr(d['archivquote'], 1)}** | "
       f"**{z(r['trichter']['nicht archivieren'])}** | **{z(r['zaehlung']['bereit'])}** | **{pr(r['quote'])}** |"])

ARCHIV_ERKLAERUNG = (
    f"Die Archivierungsquote von {pr(d['archivquote'], 1)} ist ein **Demo-Effekt der Suite**, kein Befund über "
    f"„gute“ oder „schlechte“ Stammdaten: Nur die 12 Kunden aus VarianceAI haben Umsatz, und Altkunden dürfen keine "
    f"Buchungen erhalten, die diesen Umsätzen widersprechen. Deshalb liegt die Debitorenquote bei "
    f"{pr(jo['DEBI']['archivquote'], 1)} ({z(jo['DEBI']['archivieren'])} von {z(jo['DEBI']['saetze'])}) – sie folgt "
    f"aus der Suite-Vorgabe. Die **Kreditorenquote von {pr(jo['KRED']['archivquote'], 1)}** ist der realistischere "
    "Wert. Im Echtbetrieb entscheidet die Archivierungsregel des Unternehmens (Frist, offene Posten, "
    "Aufbewahrungspflichten).")

GESPRAECH_ARCHIV = (
    "**Gesprächsfrage: „Ist eine Archivierungsquote von 80 % realistisch?“** – Ehrlich: nein, nicht als Aussage über "
    "ein echtes Unternehmen. Sie ist ein Demo-Effekt der Suite: Umsatz haben nur die 12 Kunden aus VarianceAI, alle "
    "anderen Debitoren sind Altbestand ohne Buchung seit 2024 – dadurch liegt die Debitorenquote bei "
    f"{pr(jo['DEBI']['archivquote'], 1)}. Realistischer ist die Kreditorenquote von {pr(jo['KRED']['archivquote'], 1)}, "
    "weil dort laufend bebuchte Lieferanten im Bestand sind. Im Echtbetrieb hängt die Quote an der "
    "Archivierungsregel des Unternehmens – DataGuard macht die Regel sichtbar und zählt, entscheiden muss das "
    "Migrationsprojekt.")

SUITE = [
    ("DataGuard-AI", "Stammdatenqualität", "prüft Kunden- und Lieferantenstammdaten, findet Dubletten, schlägt "
     "Golden Records vor und misst die S/4HANA-Readiness.",
     "Sind unsere Kunden- und Lieferantenstammdaten korrekt, eindeutig und bereit für S/4HANA?"),
    ("FlowAudit-AI", "Prozesssicherheit P2P", "prüft jede Eingangsrechnung gegen Bestellung und Wareneingang "
     "(E-Rechnung, 3-Way-Matching, Prävention) und gibt sie frei oder in die Klärung.",
     "Darf diese Rechnung bezahlt werden – und wenn nicht, warum?"),
    ("VarianceAI", "Abweichungen", "zerlegt Plan-Ist-Abweichungen im Monatsabschluss in Preis-, Mengen-, Mix- und "
     "Kostenstelleneffekte und prognostiziert das Jahresende.",
     "Warum weicht das Ergebnis vom Plan ab – und wo landen wir am Jahresende?"),
    ("ControllAI", "Managemententscheidungen", "verdichtet Profitabilität, Szenarien, Balanced Scorecard und "
     "Prozessportfolio für die Unternehmenssteuerung.", "Wohin steuert das Unternehmen?"),
]

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# methodik.md
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════

katalog = "\n".join(
    ["| Regel | Dimension | Schweregrad | Beschreibung | eingebaut | gefunden | anwendbar |", "|---|---|---|---|---:|---:|---:|"]
    + [f"| {rid} | {x['dimension']} | {x['schweregrad']} | {x['beschreibung']} | "
       f"{'Messung P/R' if rid in ('E01', 'E02') else z(x['eingebaut'])} | {z(x['gefunden'])} | {z(x['anwendbar'])} |"
       for rid, x in d["fehlerkatalog"].items()])
blocking = "\n".join(
    ["| Stichprobe | Objekt | ohne Blocking | mit Blocking | Pass 1 PLZ | Pass 2 IBAN/USt | Pass 3 Namensanfang |",
     "|---|---|---:|---:|---:|---:|---:|"]
    + [f"| {n} | {OBJ[o]} | {z(x['vergleiche_ohne_blocking'][o])} | {z(x['vergleiche_mit_blocking'][o])} | "
       f"{z(x['kandidaten_je_pass'][o]['PLZ'])} | {z(x['kandidaten_je_pass'][o]['IBAN/USt'])} | "
       f"{z(x['kandidaten_je_pass'][o]['Namensanfang'])} |"
       for n, x in (("Seed 42", d42), ("Prüf-Seed 4242", d4242)) for o in ("DEBI", "KRED")])
verlauf_tab = "\n".join(
    ["| Monatsende | DAMA-Gesamtscore | Readiness-Quote | Offene Cluster | Blocker-Befunde | Archivierungskandidaten | "
     "Sätze |", "|---|---:|---:|---:|---:|---:|---:|"]
    + [f"| {dt(v['monatsende'])} | {pr(v['DAMA-Gesamtscore'])} | {pr(v['Migration-Readiness-Quote'])} | "
       f"{v['Offene Dublettencluster']} | {v['Blocker-Befunde']} | {z(v['Archivierungskandidaten'])} | {z(v['Sätze'])} |"
       for v in d["verlauf"]])
dama_tab = "\n".join(["| Dimension | Score 30.09.2026 |", "|---|---:|"]
                     + [f"| {dim} | {pr(s)} |" for dim, s in d["dama"].items()]
                     + [f"| **Gesamtscore** (Mittelwert) | **{pr(d['dama_gesamt'])}** |"])
zerlegung_tab = "\n".join(["| Ursache | Summe 31.10.2025 → 30.09.2026 |", "|---|---:|"]
                          + [f"| {u} | {pp(w)} |" for u, w in sorted(zr.items(), key=lambda x: -x[1])]
                          + [f"| **Veränderung gesamt** | **{pp(sum(zr.values()))}** |"])

methodik = f"""# Methodik – DataGuard-AI 1.0.0

Alle Werte stammen aus `docs/demolauf.json` (erzeugt mit `tools/demolauf_erzeugen.py`, Stichtag {dt(d['stichtag'])},
synthetische Daten der fiktiven RheinMain Industrietechnik GmbH). Nichts ist geschätzt.

## 1. Datenbasis

| Merkmal | Wert |
|---|---|
| Debitoren / Kreditoren | {z(umf['DEBI'])} / {z(umf['KRED'])} (gesamt {z(alle)}) |
| aktive Partner der Suite | {kat['aktiv']} (12 Debitoren aus VarianceAI, 6 Kreditoren aus FlowAudit-AI) |
| laufende Kreditoren – „aktiv laut Kreditorenbuchung, nicht Teil der FlowAudit-Stichprobe“ | {z(kat['laufend'])} |
| Altbestand mit letzter Buchung vor 2024 | {z(kat['alt_gebucht'])} |
| Altbestand nie bebucht | {z(kat['alt_nie'])} |
| Neuanlagen ohne Buchung | {z(kat['neu'])} (davon in den letzten 12 Monaten angelegt: {z(d['neuanlagen_12_monate'])}) |
| Regeln im Katalog | {d['regeln']} |

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

{quoten_tab}

{ARCHIV_ERKLAERUNG} Ein Korridor von 50–60 % wäre bei unverändertem Debitorenstamm rechnerisch nicht erreichbar: Die
archivierten Debitoren allein ergeben {pr(untergrenze, 1)} des Gesamtbestands. Die Quote wird deshalb ausgewiesen,
nicht angepasst; Gewichte und Schwellen sind unverändert.

{GESPRAECH_ARCHIV}

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

{dama_tab}

Der niedrige Aktualitätsscore ist fachlich gewollt: Er zeigt Altbestand ohne Löschvormerkung (A01/A02). Achtung: Der
Score zählt **Prüfungen** (Satz × Regel), nicht Sätze – ein Satz mit drei Befunden zählt dreimal als „nicht bestanden“.

### Fehlerkatalog (Seed 42): eingebaut = gefunden

{katalog}

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

{dubtab()}

Blocking-Recall = Anteil der echten Dublettenpaare, die überhaupt verglichen wurden.

**Die zwei bewusst nicht erkannten Fälle** (in beiden Seeds eingebaut, um die Grenze des Blockings sichtbar zu machen):

| Objekt | Satz A | Satz B | Warum nicht gefunden |
|---|---|---|---|
{grenzfaelle()}

Abhilfe im Echtbetrieb: zusätzlicher Pass über Telefonnummer oder sortierte Namenstoken (Kosten: mehr Vergleiche).

**Alle Fehlerfälle ab Schwelle 75** (FN = echte Dublette nicht gemeldet, FP = gemeldet, aber keine Dublette):

| Stichprobe | Art | Paar | Score | Grund |
|---|---|---|---:|---|
{fehlerfaelle_tab(d42, "Seed 42")}
{fehlerfaelle_tab(d4242, "Prüf-Seed 4242")}

Die FP-Fälle sind der Preis eines Namensvergleichs ohne harte Merkmale: gleicher Branchenbegriff und gleiche
Rechtsform am selben Ort. Deshalb meldet DataGuard 75–89 nur als „prüfen“ – die Entscheidung trifft ein Mensch.

### Aufwand durch Blocking

{blocking}

Seed 42: {z(d42['ab_75']['vergleiche_mit_blocking'])} statt {z(d42['ab_75']['vergleiche_ohne_blocking'])} Vergleiche
(−{z(reduktion42, 1)} %); Laufzeit der Dublettenerkennung {z(d42['laufzeit_sekunden'], 2)} s.

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
eine Zuordnungsliste alt → neu; Quelldaten werden nie verändert. Demo: {d['golden_record_vorschlaege']} Vorschläge.

## 5. Migration Readiness (CVI)

| Status | Definition | Anzahl |
|---|---|---:|
| archivieren | keine Buchung seit > 24 Monaten vor Stichtag, nie bebucht und angelegt vor > 24 Monaten, Löschvormerkung oder gesperrt ohne offene Posten | {z(r['zaehlung']['archivieren'])} |
| blockiert | mindestens ein CVI-Blocker (Regel mit `cvi_blocker`) oder Dublettencluster mit ≥ 2 zu migrierenden Sätzen | {z(r['zaehlung']['blockiert'])} |
| bereit nach Bereinigung | kein Blocker, aber Befunde mit Schweregrad „Fehler“ | {z(r['zaehlung']['bereit nach Bereinigung'])} |
| bereit | höchstens Hinweise | {z(r['zaehlung']['bereit'])} |

**Readiness-Quote = bereit ÷ (alle − archivieren)** = {z(r['zaehlung']['bereit'])} ÷
{z(r['trichter']['nicht archivieren'])} = **{pr(r['quote'])}** (inkl. „bereit nach Bereinigung“:
{pr(r['quote_inkl_bereinigung'])}). Archivierungskandidaten zählen nicht in den Nenner – sonst würde die Quote mit
jedem Altsatz sinken, der gar nicht migriert werden soll. Befunde der Eindeutigkeit zählen nur, wenn mindestens ein
beteiligter Partner ebenfalls migriert wird (Beispiel K101: der nie bebuchte Altsatz wird archiviert – K101 ist
„bereit“).

Trichter: {' → '.join(f'{a} {z(b)}' for a, b in r['trichter'].items())}.

## 6. Qualitätsverlauf und Zerlegung

Zwölf Monatsstände (31.10.2025–30.09.2026) werden aus dem aktuellen Stand rekonstruiert: später angelegte Sätze
werden ausgeblendet, spätere Feldänderungen aus CDPOS rückwärts zurückgenommen. Bankfelder stehen im Protokoll nur
maskiert und enthalten ausschließlich Änderungen von gültig nach gültig (Test), daher bleibt ihre Bewertung korrekt.
Jeder Stand wird mit derselben Engine neu bewertet – keine hart codierten Werte.

{verlauf_tab}

Der Effekt „DAMA steigt, Readiness sinkt“ ist nicht gesetzt, sondern ergibt sich aus dem Änderungsprotokoll. Je Monat
wird die Veränderung der Quote q = bereit ÷ basis exakt auf die Sätze verteilt:

Beitrag je Satz = (Δbereit − q₀ · Δbasis) ÷ basis₁ (q₀ ungerundet; Summe der Beiträge = Veränderung der Quote).

Die Ursache eines Satzes folgt aus Protokoll und Status: neu angelegt und bereit („Neuanlagen bereit“), neu angelegt
und blockiert bzw. nach Bereinigung („neue Blocker durch Neuanlagen“, nach Anlagebenutzer ERNAM), durch Änderungen
verbessert („bereinigt“, nach Änderungsbenutzer CDHDR-USERNAME) oder verschlechtert („verschlechtert durch Änderung“),
ohne Änderung durch Zeitablauf („Alterung/Zeitablauf“, z. B. 24-Monats-Grenze).

{zerlegung_tab}

Größte Verursacher neuer Blocker (Anlagebenutzer, 12 Monate): {nb_text}.

**Governance-Empfehlung „Data Firewall“:** Pflichtfeld- und Dublettenprüfung bereits bei der Anlage – dieselbe
Regel- und Dubletten-Engine vor dem Speichern (Schwelle 75), Bankdaten nur mit Vier-Augen-Prüfung, Kennzahl „neue
Blocker durch Neuanlagen“ je Anlagebenutzer monatlich im Governance-Board. Die Bereinigung ({pp(zr['bereinigt'])})
wird sonst von neuen Blockern ({pp(zr['neue Blocker durch Neuanlagen'])}) mehr als aufgezehrt.

## 7. KI-Agent und Faktenprüfung

Das LLM erhält nur ein Faktenblatt (Kennzahlen, Regel-IDs, pseudonymisierte Satznummern `SATZ-0001`, Merkmalswerte) –
nie IBAN, Bankdaten, Namen oder Freitexte. Jede Zahl, Regel-ID, Cluster-ID, jedes Pseudonym und Datum im Text wird
gegen das Faktenblatt geprüft; IBAN-artige Folgen werden vor der Zahlenprüfung entfernt und führen zum Verwerfen.
Bei Fehlschlag gilt der regelbasierte Text. Freigabe nur namentlich, gebunden an einen Fingerabdruck von Daten und
Entscheidungen.

## 8. Laufzeiten

| Messung | Wert | Ziel |
|---|---:|---:|
| Monatsverlauf 12 Stände ohne Ergebniscache (Median aus 5 frischen Prozessen) | {sek('verlauf_sekunden')} | ≤ 1,5 s |
| Oberfläche Erstlauf (frischer Prozess) | {sek('erstlauf_sekunden')} | ≤ 12 s |
| Oberfläche Folgelauf (Tabwechsel, Median) | {sek('folgelauf_sekunden')} | ≤ 1 s |

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
"""
(P / "docs/methodik.md").write_text(methodik, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Suite-Abstimmung.md
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def maske(iban: str) -> str:
    return f"{iban[:4]} •••• {iban[-4:]}"


summe_cent = sum(x["umsatz_2025_cent"] for x in ref["debitoren"])
kunden = "\n".join(f"| {x['kunnr']} | {x['name']} | {x['region']} | {z(x['umsatz_2025_cent'] / 100, 2)} | "
                   f"{dt(x['letzte_faktura'])} | {x.get('branche', '')} |" for x in ref["debitoren"])
lieferanten = "\n".join(f"| {x['lifnr']} | {x['name']} | {maske(x['iban'])} | {x['ust_id']} | {x['plz']} {x['ort']} | "
                        f"{x['zterm']} |" for x in ref["kreditoren"])
fa = ref["firma"]
suite = f"""# Suite-Abstimmung · DataGuard-AI 1.0.0 (Abschluss der RheinMain Controlling-Suite)

DataGuard-AI ist der vierte und letzte Agent der Suite. Alle vier Agenten arbeiten mit derselben fiktiven Firma und
denselben Schlüsseln. Zur Laufzeit liest DataGuard nur `src/suite_referenz.json`; die Datei wurde mit
`tools/suite_referenz_erzeugen.py` einmal je Referenzprojekt mit dessen Umgebung erzeugt. Die Referenzagenten wurden
nur gelesen (Abgleich gegen die gelieferten ZIP-Dateien: unverändert, siehe `docs/Endabnahme.md`).

## Kontrolltabelle über alle vier Agenten

| Wert | DataGuard-AI 1.0.0 | FlowAudit-AI 1.2.1 | VarianceAI 1.2 | ControllAI 2.2.1 | Test in DataGuard |
|---|---|---|---|---|---|
| Stichtag | {dt(ref['stichtag'])} | {dt(ref['flowaudit_stichtag'])} (fester Demo-Stichtag, Rechnungseingang im Folgemonat) | {dt(ref['stichtag'])} | {dt(ref['stichtag'])} | `test_stichtag_firma_buchungskreis` |
| Firma | {fa['name']}, {fa['strasse']}, {fa['plz']} {fa['ort']} | gleich | gleich | gleich | `test_stichtag_firma_buchungskreis` |
| Buchungskreis | {fa['buchungskreis']} | {fa['buchungskreis']} | {fa['buchungskreis']} | {fa['buchungskreis']} | `test_stichtag_firma_buchungskreis` |
| 12 Kunden K101–K304 | Stammsätze (Nummer, Name, Region unverändert) | – | Quelle (Umsatz, Faktura) | Umsatz/HK centgleich | `test_zwoelf_kunden_wie_varianceai`, `test_datenbank_traegt_dieselben_schluessel` |
| 6 Lieferanten 100100–100600 | Stammsätze (Name, Bank, USt unverändert) | Quelle | – | – | `test_sechs_lieferanten_wie_flowaudit`, `test_datenbank_traegt_dieselben_schluessel` |
| Summe Umsatz 2025 | {z(summe_cent / 100, 2)} € (Kontrollwert) | – | {z(summe_cent / 100, 2)} € | {z(summe_cent / 100, 2)} € | `test_zwoelf_kunden_wie_varianceai`, `test_referenz_kontrollwerte` |
| EBIT 2025 | nicht genutzt – nur als Referenz zitiert | – | 8.720.441,56 € | 8.720.441,56 € | – (Zitat, siehe unten) |

**EBIT 2025 = 8.720.441,56 €** wird hier nur als Referenz zitiert (Quelle: ControllAI 2.2.1, `docs/Suite-Abstimmung.md`
und `src/suite_referenz.json` → `summen.2025.ebit_cent = 872044156`, dort centgleich mit VarianceAI 1.2 belegt).
DataGuard-AI rechnet nicht mit Beträgen; jeder Wert, den DataGuard selbst nutzt, ist durch einen Test in
`tests/test_suite_kontrolltabelle.py` (feste Konstanten, unabhängig von der JSON-Datei) und
`tests/test_suite_referenz.py` abgesichert.

### 12 Kunden (VarianceAI – führendes Finanzsystem)

| Kunde | Name | Region | Umsatz 2025 (€) | letzte Faktura | Branche (ControllAI) |
|---|---|---|---:|---|---|
{kunden}
| **Summe** | | | **{z(summe_cent / 100, 2)}** | | |

### 6 Lieferanten (FlowAudit-AI)

| Lieferant | Name | IBAN (maskiert) | USt-IdNr. | Ort | ZTERM |
|---|---|---|---|---|---|
{lieferanten}

Eigene USt-IdNr. der RheinMain: {ref['eigene_ust_id']} (gültige Prüfziffer, `test_ust_de_wie_flowaudit`).

## Gemeinsame Schlüssel

| Schlüssel | Quelle | Verwendung in DataGuard |
|---|---|---|
| Buchungskreis 1000, Firma, Anschrift | alle Agenten | Kopfzeile, Bericht, Exporte |
| Debitoren K101–K304 (Name, Region) | VarianceAI `seed_data.KUNDEN` | 12 aktive Debitoren, Felder unverändert |
| Umsatz 2025 und letzte Faktura je Kunde | VarianceAI Universal Journal (Ist, 800000, ohne 9099999999) | Kontrollwerte, letzte Buchung |
| Branche je Kunde | ControllAI `kunden` | KNA1-BRSCH der 12 aktiven Debitoren |
| Kreditoren 100100–100600 (Anschrift, USt-IdNr., E-Mail, BLZ/Konto/BIC, ZTERM) | FlowAudit-AI `seed_data.LIEFERANTEN` | 6 aktive Kreditoren, Felder unverändert |
| IBAN | FlowAudit-AI `seed_data._iban` | LFBK-IBAN (nur maskiert sichtbar) |
| Bankänderungen 100100 ({dt(bank['100100'])}) und 100400 ({dt(bank['100400'])}) mit absolutem Datum | FlowAudit-AI `BANKAENDERUNGEN`, Stichtag {dt(ref['flowaudit_stichtag'])} | CDHDR/CDPOS bis {dt(ref['stichtag'])}, Regel A04 |
| Kostenstellen 4100–4500, Produktgruppen ANT/STE/SEN, Regionen NORD/SUED/WEST | VarianceAI | nur Bezeichnungen |

## Kontrollwerte

| Kontrolle | Wert | Test |
|---|---|---|
| Summe Umsatz 2025 der 12 Kunden | {z(summe_cent / 100, 2)} € | `test_referenz_kontrollwerte`, `test_zwoelf_kunden_wie_varianceai` |
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
Verknüpfung (E05). Die Bankänderung von 100100 am {dt(bank['100100'])} liegt außerhalb der 30-Tage-Frist (kein Befund).

### Eine Zeitachse für Bankänderungen

DataGuard und FlowAudit-AI verwenden dieselben Kalenderdaten. Die Bankänderung von 100400 am {dt(bank['100400'])} liegt
nach dem Stammdatenstand {dt(ref['stichtag'])}; DataGuard sieht sie deshalb noch nicht – FlowAudit-AI erkennt sie im
laufenden Rechnungseingang (Stichtag {dt(ref['flowaudit_stichtag'])}) und verlangt die Vier-Augen-Prüfung. Genau diese
Arbeitsteilung zeigt die Suite: periodische Stammdatenprüfung plus Kontrolle im laufenden Prozess. Den Vier-Augen-Fall
der Regel A04 zeigt DataGuard an einem laufenden Kreditor des eigenen Bestands ({vier_augen}, Bankänderung am
{dt(ref['stichtag'][:8] + '25')}), nicht an einem FlowAudit-Lieferanten.

## Altbestand, laufende Kreditoren und Archivierung

* **Debitoren:** Außer den 12 Suite-Kunden hat kein Debitor eine Buchung seit 2024 – nur diese Kunden haben Umsatz in
  VarianceAI und ControllAI. Folge: Archivierungsquote Debitoren {pr(jo['DEBI']['archivquote'], 1)}.
* **Kreditoren:** {z(kat['laufend'])} Sätze des Kreditoren-Altbestands tragen Buchungen 2024–2026 – nur Datum der letzten
  Buchung und Anzahl Belege, **keine Beträge**; gekennzeichnet als „aktiv laut Kreditorenbuchung, nicht Teil der
  FlowAudit-Stichprobe“. Archivierungsquote Kreditoren {pr(jo['KRED']['archivquote'], 1)} (realistischerer Wert).
* Neuanlagen der letzten 12 Monate ohne Buchung: {z(d['neuanlagen_12_monate'])} über beide Objekte (Korridor 80–120).
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
dem festen Demo-Stichtag {dt(ref['flowaudit_stichtag'])} aus `data/invoices/manifest.json`; die Bankänderungen liegen
deshalb auf derselben Kalenderachse wie in DataGuard (siehe oben). Optional, falls die Agenten künftig Stammdaten
anzeigen: Anschrift und USt-IdNr. der 12 Kunden aus `src/suite_referenz.json` übernehmen.
"""
(P / "docs/Suite-Abstimmung.md").write_text(suite, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Endabnahme.md
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════

ek = kontrolle


def ja(wert) -> str:
    return "erfüllt" if wert else "OFFEN"


grenzen = messung.get("grenzen", {})
erfuellt = messung.get("erfuellt", {})
endabnahme = f"""# Endabnahme · DataGuard-AI 1.0.0

Lokale Offline-Abnahme im Cloud-Container (Mock, keine kostenpflichtige API). Messrechner:
{messung.get('rechner', '?')}, Python {messung.get('python', '?')}, Messung am {messung.get('zeitpunkt', '?')}.

| Kriterium | Ziel | Gemessener Wert | Status |
|---|---|---|---|
| Monatsverlauf ohne Ergebniscache | ≤ {z(grenzen.get('verlauf_sekunden', 1.5), 1)} s | {sek('verlauf_sekunden')} (Median aus {messung.get('laeufe', '?')} frischen Prozessen) | {ja(erfuellt.get('verlauf_sekunden'))} |
| Oberfläche Erstlauf | ≤ {z(grenzen.get('erstlauf_sekunden', 12), 0)} s | {sek('erstlauf_sekunden')} (Median) | {ja(erfuellt.get('erstlauf_sekunden'))} |
| Oberfläche Folgelauf | ≤ {z(grenzen.get('folgelauf_sekunden', 1), 0)} s | {sek('folgelauf_sekunden')} (Median über alle 7 Tabs) | {ja(erfuellt.get('folgelauf_sekunden'))} |
| Tests Python {py311[0]} (frische Umgebung aus uv.lock) | alle bestanden | {py311[1]} bestanden in {py311[2]} s | {ja(py311[1].isdigit())} |
| Tests Python {py313[0]} (frische Umgebung aus uv.lock) | alle bestanden | {py313[1]} bestanden in {py313[2]} s | {ja(py313[1].isdigit())} |
| ruff (F, E9, E501, B, UP, I; Zeilenlänge 120) | sauber | {ek.get('ruff', '?')} | {ja(ek.get('ruff') == 'All checks passed!')} |
| desktop/ gegen VarianceAI | nur app.toml und Symbol verschieden | {', '.join(ek.get('desktop_unterschiede', ['?']))} | {ja(ek.get('desktop_ok'))} |
| Referenzagenten unverändert | Abgleich mit den ZIP-Dateien | {'; '.join(f"{n}: {u} Unterschiede" for n, u in ek.get('referenzen', {}).items())} | {ja(ek.get('referenzen') and not any(ek['referenzen'].values()))} |
| Secrets im Repository | keine | {ek.get('secrets', '?')} | {ja(ek.get('secrets') == 'keine gefunden')} |
| Kontrollwerte Zahlenwerk | per Test | Umsatz 2025 {z(summe_cent / 100, 2)} €, K101, IBAN 100100, USt-IdNrn., 12 Kunden, 6 Lieferanten | erfüllt |
| Eingebaute Fehler gefunden | eingebaut = gefunden | beide Seeds, Satz für Satz (`test_eingebaute_fehler_werden_exakt_gefunden`) | erfüllt |
| IBAN in Exporten | nie unmaskiert | Excel, PowerPoint, PDF, Power BI, Migration Cockpit (`test_kein_export_enthaelt_eine_unmaskierte_iban`) | erfüllt |
| Sicherheitstests | blockiert | Datentext-Injection und IBAN-Ausgabe (`test_sicherheitstest_*`, AppTest) | erfüllt |

Laufzeit-Einzelwerte (Sekunden): Verlauf {', '.join(z(x, 2) for x in messung.get('einzelwerte', {}).get('verlauf', []))};
Erstlauf {', '.join(z(x, 2) for x in messung.get('einzelwerte', {}).get('erstlauf', []))}; Folgelauf höchstens
{z(messung.get('einzelwerte', {}).get('folgelauf_max', 0), 2)} s.

Die Testsuite enthält nur großzügige Schutzwerte (Monatsverlauf ≤ 5 s, Erstlauf ≤ 30 s, Folgelauf ≤ 3 s), damit
sie auf anderen Rechnern nicht zufällig scheitert. Die Zielwerte weist dieses Dokument mit
`tools/endabnahme_messen.py` nach (Rohdaten: `docs/endabnahme_messung.json`).

## Kennzahlen der Demo (Stichtag 30.09.2026)

| Kennzahl | Wert |
|---|---|
| DAMA-Gesamtscore | {pr(k['DAMA-Gesamtscore'])} ({pp(k['DAMA-Gesamtscore'] - kv['DAMA-Gesamtscore'])}) |
| Readiness-Quote gesamt / Debitoren / Kreditoren | {pr(r['quote'])} / {pr(jo['DEBI']['readiness_quote'])} / {pr(jo['KRED']['readiness_quote'])} |
| Archivierungsquote gesamt / Debitoren / Kreditoren | {pr(d['archivquote'], 1)} / {pr(jo['DEBI']['archivquote'], 1)} / {pr(jo['KRED']['archivquote'], 1)} |
| Precision / Recall ab 75 (Seed 42 · Prüf-Seed 4242) | {pr(100 * d42['ab_75']['precision'])} / {pr(100 * d42['ab_75']['recall'])} · {pr(100 * d4242['ab_75']['precision'])} / {pr(100 * d4242['ab_75']['recall'])} |

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
"""
(P / "docs/Endabnahme.md").write_text(endabnahme, encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# README.md
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════

akt = d["aktive_partner"]
bereit_akt = sum(1 for x in akt.values() if x["status"] == "bereit")
blockiert_akt = ", ".join(f"{s.split(':')[1]} ({x['blocker']})" for s, x in akt.items() if x["status"] == "blockiert")


def kz(name: str, prozent: bool = False) -> str:
    a, b = k[name], kv[name]
    if prozent:
        return f"| {name} | {pr(a)} | {pr(b)} | {pp(a - b)} |"
    diff = a - b
    return f"| {name} | {z(a)} | {z(b)} | {('+' if diff > 0 else '−' if diff < 0 else '±')}{z(abs(diff))} |"


suite_tab = "\n".join(["| Agent | Ebene | Was er tut | Leitfrage |", "|---|---|---|---|"]
                      + [f"| **{n}** | {e} | {t[0].upper() + t[1:]} | *{f}* |" for n, e, t, f in SUITE])
readme = f"""# DataGuard-AI · Stammdaten-Copilot

<!-- Live-Demo: nach dem Deploy anpassen (Link wird separat gesetzt) -->
[![Live-Demo](https://img.shields.io/badge/Live--Demo-folgt-lightgrey)](#)
[![Tests](https://img.shields.io/badge/Tests-{tests_anzahl}%20bestanden-brightgreen)](docs/pytest-python313.txt)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue)](pyproject.toml)
[![Offline](https://img.shields.io/badge/Demo-ohne%20API--Key-0A66C2)](#schnellstart)
[![Version](https://img.shields.io/badge/Version-1.0.0-2EA44F)](docs/Aenderungsprotokoll.md)
[![Agenten-Standard](https://img.shields.io/badge/Agenten--Standard-v1-orange)](docs/STANDARD.md)

> *Sind unsere Kunden- und Lieferantenstammdaten korrekt, eindeutig und bereit für S/4HANA?*

DataGuard-AI prüft die Debitoren- und Kreditorenstammdaten der fiktiven **RheinMain Industrietechnik GmbH** mit
{d['regeln']} Regeln entlang der DAMA-Dimensionen, findet Dubletten erklärbar, schlägt je Cluster einen Golden Record
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

{suite_tab}

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
{kz("DAMA-Gesamtscore", True)}
{kz("Migration-Readiness-Quote", True)}
{kz("Offene Dublettencluster")}
{kz("Blocker-Befunde")}
{kz("Archivierungskandidaten")}

{quoten_tab}

{ARCHIV_ERKLAERUNG}

Bestand: {z(umf['DEBI'])} Debitoren und {z(umf['KRED'])} Kreditoren ({z(alle)} Sätze). Davon {kat['aktiv']} aktive
Partner der Suite und {z(kat['laufend'])} laufende Kreditoren – *aktiv laut Kreditorenbuchung, nicht Teil der
FlowAudit-Stichprobe* (nur Datum der letzten Buchung und Anzahl Belege, keine Beträge). Aktive Partner: {bereit_akt}
„bereit“; blockiert: {blockiert_akt}.

**DAMA steigt, Readiness sinkt** – aus dem Änderungsprotokoll, nicht gesetzt: DAMA-Gesamtscore
{pr(v0['DAMA-Gesamtscore'])} → {pr(v1['DAMA-Gesamtscore'])}, Readiness-Quote {pr(v0['Migration-Readiness-Quote'])} →
{pr(v1['Migration-Readiness-Quote'])} (31.10.2025 → 30.09.2026). Zerlegung:
{", ".join(f"{u} {pp(w)}" for u, w in sorted(zr.items(), key=lambda x: -x[1]))}. Daraus die Governance-Empfehlung
**„Data Firewall“**: Pflichtfeld- und Dublettenprüfung bereits bei der Anlage.

### Dublettenerkennung – Precision, Recall, F1 (Paarebene)

{dubtab(kurz=True)}

Schwellen und Gewichte wurden nie angepasst. Blocking reduziert {z(d42['ab_75']['vergleiche_ohne_blocking'])} mögliche
Vergleiche auf {z(d42['ab_75']['vergleiche_mit_blocking'])} (Seed 42). Zwei Fälle sind bewusst so gebaut, dass kein
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

{tests_anzahl} Tests – Python {py311[0]}: {py311[1]} bestanden ({py311[2]} s), Python {py313[0]}: {py313[1]} bestanden
({py313[2]} s), jeweils in frischer Umgebung aus `uv.lock`. Laufzeiten (Ziel): Monatsverlauf {sek('verlauf_sekunden')}
(≤ 1,5 s), Erstlauf {sek('erstlauf_sekunden')} (≤ 12 s), Folgelauf {sek('folgelauf_sekunden')} (≤ 1 s) –
Nachweis in [`docs/Endabnahme.md`](docs/Endabnahme.md).

## Projektstruktur

```text
app.py                   Oberfläche (7 Tabs)            src/agent.py            Faktenblatt, Faktenprüfung, LLM-Clients
src/ui_design.py         Designsystem 1:1 VarianceAI    src/sicherheitstest.py  Injection- und IBAN-Test
src/ui_diagramme.py      Diagramme (Altair)             src/zwischenspeicher.py Ergebniscache nach Dateistand
src/exporter.py          Excel, Power BI, Migr.-Cockpit src/bericht_export.py   Readiness-Bericht PPTX/PDF
src/config.py            Stichtag, Pfade, Seeds         src/regeln.py           Regelkatalog ({d['regeln']} Regeln) + Engine
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
"""
(P / "README.md").write_text(readme, encoding="utf-8")
print("README.md, docs/methodik.md, docs/Suite-Abstimmung.md, docs/Endabnahme.md geschrieben")
