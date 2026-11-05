// Erklärdokumente DataGuard-AI (docx-js): SAP-Anbindung und Kennzahlen_und_Diagramme, je Deutsch und Arabisch.
// Eine Inhaltsquelle (inhalt.js) für beide Sprachen; alle Werte aus werte.json (tools/erklaerdokumente_werte.py).
// Aufruf: node tools/erklaerdokumente/erzeugen.js <Zielordner Deutsch> <Zielordner Arabisch>
"use strict";
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, LevelFormat, Packer, PageBreak, PageNumber, Paragraph,
  ShadingType, Table, TableCell, TableRow, TextRun, WidthType,
} = require("docx");
const inhalt = require("./inhalt");

const W = JSON.parse(fs.readFileSync(path.join(__dirname, "werte.json"), "utf8"));
const BREITE = 9638; // A4 (11906) − 2 × 1134 DXA Rand
const FARBE = { kopf: "2F3A45", text: "1F2A33", leise: "595959", akzent: "C8643B", rahmen: "BFBFBF",
  kasten: "F3F1EC", warn: "FFF4E5", warnRand: "D9822B", sage: "EAF2EA", sageRand: "2E6B30" };
const SCHRIFT = { ascii: "Arial", hAnsi: "Arial", cs: "Arial", eastAsia: "Arial" };
const ARABISCH = /[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]/;

// ── Läufe: arabische und lateinische Textteile getrennt (RTL nur für arabische Läufe) ─────────────────────
function laeufe(text, ar, opt = {}) {
  const basis = { font: SCHRIFT, size: opt.size || 20, sizeComplexScript: opt.size || 20, bold: !!opt.bold,
    boldComplexScript: !!opt.bold, italics: !!opt.italics, color: opt.color || FARBE.text };
  if (!ar) return [new TextRun({ ...basis, text })];
  return segmente(String(text)).map(([rtl, s]) => new TextRun({ ...basis, text: s, rightToLeft: rtl }));
}

// Zerlegung in Läufe nach starker Richtung: arabische Buchstaben → RTL-Lauf, lateinische Buchstaben/Ziffern → LTR-Lauf.
// Neutrale Zeichen (Leerzeichen, Klammern, Satzzeichen) zwischen zwei lateinischen Teilen bleiben lateinisch
// (z. B. „USt-IdNr.“, „94,37 %“), sonst gehören sie zum arabischen Lauf (Grundrichtung des Absatzes ist RTL).
function segmente(text) {
  const art = (ch) => (ARABISCH.test(ch) ? "A" : /[A-Za-z0-9\u00C0-\u024F€§%]/.test(ch) ? "L" : "N");
  const zeichen = [...text];
  const klassen = zeichen.map(art);
  for (let i = 0; i < klassen.length; i++) {
    if (klassen[i] !== "N") continue;
    let j = i;
    while (j < klassen.length && klassen[j] === "N") j++;
    const vor = i > 0 ? klassen[i - 1] : "A";
    const nach = j < klassen.length ? klassen[j] : "A";
    const r = vor === "L" && nach === "L" ? "L" : "A";
    for (let k = i; k < j; k++) klassen[k] = r;
    i = j - 1;
  }
  const aus = [];
  zeichen.forEach((ch, i) => {
    const rtl = klassen[i] === "A";
    if (aus.length && aus[aus.length - 1][0] === rtl) aus[aus.length - 1][1] += ch;
    else aus.push([rtl, ch]);
  });
  return aus;
}

function absatz(text, ar, opt = {}) {
  // Rein lateinischer Text (Zahlen, Fachbegriffe) in der arabischen Fassung: LTR-Absatz, rechtsbündig – so bleibt
  // „+5,62 Pp“ lesbar statt „Pp 5,62+“
  if (ar && !opt.ltr && !ARABISCH.test(String(text))) {
    opt = { ...opt, ltr: true, align: opt.align || AlignmentType.RIGHT };
  }
  return new Paragraph({
    children: laeufe(text, ar, opt), bidirectional: ar && !opt.ltr,
    // RTL-Absätze ohne Ausrichtung: Standard „Anfang“ = rechts (jc=right würde in bidi-Absätzen „Ende“ = links bedeuten)
    alignment: opt.align || (ar && !opt.ltr ? undefined : AlignmentType.LEFT),
    spacing: { before: opt.before ?? 0, after: opt.after ?? 120, line: 276 },
    keepNext: !!opt.keepNext, heading: opt.heading, border: opt.border,
  });
}

function zelle(text, ar, breite, opt = {}) {
  const inhalt = (Array.isArray(text) ? text : [text]).map((t) => absatz(t, ar, { ...opt, after: 40 }));
  return new TableCell({
    children: inhalt, width: { size: breite, type: WidthType.DXA },
    shading: opt.fill ? { fill: opt.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
  });
}

const RAND = { style: BorderStyle.SINGLE, size: 4, color: FARBE.rahmen };
function tabelle(kopf, zeilen, anteile, ar) {
  const summe = anteile.reduce((a, b) => a + b, 0);
  const breiten = anteile.map((a) => Math.floor((BREITE * a) / summe));
  breiten[breiten.length - 1] += BREITE - breiten.reduce((a, b) => a + b, 0);
  const reihe = (werte, istKopf) => new TableRow({
    tableHeader: istKopf, cantSplit: true,
    children: werte.map((w, i) => zelle(w, ar, breiten[i], istKopf
      ? { bold: true, color: "FFFFFF", fill: FARBE.kopf, size: 18 } : { size: 18 })),
  });
  return new Table({
    width: { size: BREITE, type: WidthType.DXA }, columnWidths: breiten, visuallyRightToLeft: ar,
    borders: { top: RAND, bottom: RAND, left: RAND, right: RAND, insideHorizontal: RAND, insideVertical: RAND },
    rows: [reihe(kopf, true), ...zeilen.map((z) => reihe(z, false))],
  });
}

function kasten(titel, saetze, ar, art = "kasten") {
  const fuellung = { kasten: FARBE.kasten, warn: FARBE.warn, sage: FARBE.sage }[art];
  const rand = { kasten: FARBE.akzent, warn: FARBE.warnRand, sage: FARBE.sageRand }[art];
  const ltr = art === "sage"; // „So sage ich es auf Deutsch“ immer links-nach-rechts
  const seite = ar && !ltr ? "right" : "left";
  const kinder = [absatz(titel, ar, { bold: true, ltr, after: 80, color: rand === FARBE.akzent ? FARBE.text : rand }),
    ...saetze.map((s) => absatz(s, ar, { ltr, after: 80 }))];
  return new Table({
    width: { size: BREITE, type: WidthType.DXA }, columnWidths: [BREITE], visuallyRightToLeft: ar && !ltr,
    borders: { top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: BorderStyle.NONE, size: 0,
      color: "FFFFFF" }, left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    [seite]: { style: BorderStyle.SINGLE, size: 24, color: rand } },
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({
      children: kinder, width: { size: BREITE, type: WidthType.DXA },
      shading: { fill: fuellung, type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 120, bottom: 80, left: 200, right: 200 },
    })] })],
  });
}

const abstand = () => new Paragraph({ children: [], spacing: { after: 120 } });

// ── Blöcke der Inhaltsquelle rendern ────────────────────────────────────────────────────────────────────────
function rendern(bloecke, sprache) {
  const ar = sprache === "ar";
  const s = (x) => (x && typeof x === "object" && !Array.isArray(x) && ("de" in x) ? x[sprache] : x);
  const aus = [];
  for (const b of bloecke) {
    if (b.nur && b.nur !== sprache) continue;
    switch (b.typ) {
      case "h1": aus.push(absatz(s(b.text), ar, { heading: HeadingLevel.HEADING_1, before: 200, after: 140,
        keepNext: true, size: 30, bold: true })); break;
      case "h2": aus.push(absatz(s(b.text), ar, { heading: HeadingLevel.HEADING_2, before: 160, after: 100,
        keepNext: true, size: 24, bold: true })); break;
      case "p": aus.push(absatz(s(b.text), ar)); break;
      case "liste": for (const x of b.punkte) {
        aus.push(new Paragraph({ children: laeufe(s(x), ar), bidirectional: ar,
          alignment: ar ? undefined : AlignmentType.LEFT, numbering: { reference: "punkte", level: 0 },
          spacing: { after: 60 } }));
      } break;
      case "tabelle": aus.push(tabelle(b.kopf.map(s), b.zeilen.map((z) => z.map(s)), b.anteile, ar), abstand()); break;
      case "kasten": aus.push(kasten(s(b.titel), b.saetze.map(s), ar, b.art || "kasten"), abstand()); break;
      case "sage": if (ar) aus.push(kasten("So sage ich es auf Deutsch", b.saetze, ar, "sage"), abstand()); break;
      case "frage":
        aus.push(absatz(s(b.frage), ar, { bold: true, keepNext: true, before: 120, after: 60 }));
        aus.push(absatz(s(b.antwort), ar));
        if (ar && b.antwort.de) aus.push(kasten("So sage ich es auf Deutsch", [b.antwort.de], ar, "sage"), abstand());
        break;
      case "umbruch": aus.push(new Paragraph({ children: [new PageBreak()] })); break;
      default: throw new Error("unbekannter Block " + b.typ);
    }
  }
  return aus;
}

function titelseite(doku, sprache) {
  const ar = sprache === "ar";
  const s = (x) => x[sprache];
  const kapitel = doku.bloecke.filter((b) => b.typ === "h1" && (!b.nur || b.nur === sprache)).map((b) => s(b.text));
  return [
    new Paragraph({ children: [], spacing: { before: 2400 } }),
    absatz(s(doku.titel), ar, { size: 44, bold: true, after: 200 }),
    absatz(s(doku.untertitel), ar, { size: 24, color: FARBE.leise, after: 120 }),
    absatz(s(doku.zweck), ar, { size: 20, color: FARBE.leise, after: 240 }),
    absatz(s(doku.version), ar, { size: 18, color: FARBE.leise, after: 360,
      border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: FARBE.akzent, space: 6 } } }),
    kasten(s(doku.kernTitel), doku.kern.map(s), ar),
    abstand(),
    absatz(s(doku.fussnote), ar, { size: 16, italics: true, color: FARBE.leise }),
    new Paragraph({ children: [new PageBreak()] }),
    absatz(ar ? "المحتويات" : "Inhalt", ar, { size: 26, bold: true, after: 200 }),
    ...kapitel.map((k) => absatz(k, ar, { size: 20, after: 100 })),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

async function schreiben(doku, sprache, datei) {
  const ar = sprache === "ar";
  const dokument = new Document({
    creator: "DataGuard-AI", title: doku.titel[sprache], description: doku.untertitel[sprache],
    styles: {
      default: { document: { run: { font: SCHRIFT, size: 20 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: SCHRIFT, size: 30, bold: true, color: FARBE.text },
          paragraph: { spacing: { before: 240, after: 140 }, keepNext: true, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: SCHRIFT, size: 24, bold: true, color: FARBE.text },
          paragraph: { spacing: { before: 160, after: 100 }, keepNext: true, outlineLevel: 1 } },
      ],
    },
    numbering: { config: [{ reference: "punkte", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
      alignment: AlignmentType.START,
      style: { paragraph: { indent: { start: 500, hanging: 260 } } } }] }] },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 },
        margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
      footers: { default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER, bidirectional: ar,
        children: [...laeufe(`${doku.fusszeile[sprache]} · ${ar ? "صفحة" : "Seite"} `, ar, { size: 16, color: FARBE.leise }),
          new TextRun({ children: [PageNumber.CURRENT], font: SCHRIFT, size: 16, color: FARBE.leise })],
      })] }) },
      children: [...titelseite(doku, sprache), ...rendern(doku.bloecke, sprache)],
    }],
  });
  fs.writeFileSync(datei, await Packer.toBuffer(dokument));
  console.log("geschrieben:", datei);
}

(async () => {
  const [zielDe, zielAr] = [process.argv[2] || "docs", process.argv[3] || "."];
  for (const [name, doku] of Object.entries(inhalt(W))) {
    await schreiben(doku, "de", path.join(zielDe, `${name}.docx`));
    await schreiben(doku, "ar", path.join(zielAr, `DataGuard-AI_${name}_AR.docx`));
  }
})();
