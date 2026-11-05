"""Interaktive Diagramme des Stammdaten-Cockpits (Altair/Vega-Lite) im Designsystem der Suite.

Gleiche Regeln wie VarianceAI (``_thema`` 1:1 übernommen):

* Ruhige Fläche, Farbe trägt nur Bedeutung: günstig/ungünstig aus den validierten Token, immer mit Vorzeichen bzw.
  Wort beschriftet; der Akzent bleibt Bedienung und KI vorbehalten und erscheint nie in Diagrammen.
* Säulen und Balken immer ab 0, keine Doppelachsen. Beschriftungen deutsch formatiert (``94,37 %``, ``−1,27 Pp``).
* Linien ohne Legende, wo möglich direkt beschriftet; Strichart unterscheidet Reihen zusätzlich zur Helligkeit.
"""

from __future__ import annotations

from collections.abc import Mapping

import altair as alt
import pandas as pd

from src import format as fmt
from src.ui_design import FARBEN

MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _thema(chart: alt.TopLevelMixin, hoehe: int) -> alt.TopLevelMixin:
    f = FARBEN
    return (
        chart.properties(height=hoehe, background="transparent",
                         padding={"left": 4, "right": 8, "top": 12, "bottom": 4})
        .configure_view(stroke=None)
        .configure_axis(labelColor=f["text_leise"], titleColor=f["text_leise"], gridColor=f["raster"],
                        domainColor=f["linie_stark"], tickColor=f["linie_stark"], labelFont="Inter", titleFont="Inter",
                        labelFontSize=11, titleFontSize=11, titleFontWeight=500, labelPadding=6)
        .configure_text(font="Inter", fontSize=11)
        .configure_legend(labelColor=f["text_2"], titleColor=f["text_leise"], labelFont="Inter", titleFont="Inter",
                          orient="top", direction="horizontal", symbolSize=90, labelFontSize=11)
    )


# Monatsbeschriftung zweizeilig („Okt“ / „25“), damit 12 Monate auch in schmalen Spalten nicht überlappen
MONATSACHSE = alt.Axis(labelAngle=0, ticks=False, domain=False, labelExpr="split(datum.label, ' ')", labelPadding=4)


def monat_kurz(d) -> str:
    return f"{MONATE[d.month - 1]} {str(d.year)[2:]}"


# ── DAMA-Dimensionen ───────────────────────────────────────────────────────────────────────────────────────────


def dama_balken(score: Mapping[str, float], vormonat: Mapping[str, float], hoehe: int = 220) -> alt.TopLevelMixin:
    """Score je Dimension (0–100 %), Veränderung zum Vormonat in Pp mit Vorzeichen (grün = besser)."""
    f = FARBEN
    df = pd.DataFrame([{"dimension": d, "score": s, "delta": s - vormonat.get(d, s),
                        "label": fmt.prozent(s), "delta_label": fmt.pp(s - vormonat.get(d, s)),
                        "ton": "gut" if s > vormonat.get(d, s) else "schlecht" if s < vormonat.get(d, s) else "leise",
                        "tooltip": f"{d}: {fmt.prozent(s)} ({fmt.pp(s - vormonat.get(d, s))} ggü. Vormonat)"}
                       for d, s in score.items()])
    y = alt.Y("dimension:N", sort=list(score), title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=180))
    x = alt.X("score:Q", scale=alt.Scale(domain=[0, 118]), axis=None)
    hinten = alt.Chart(pd.DataFrame({"dimension": list(score), "voll": [100.0] * len(score)})).mark_bar(
        size=14, color=f["karte_2"], cornerRadius=2).encode(y=y, x=alt.X("voll:Q", scale=alt.Scale(domain=[0, 118]),
                                                                         axis=None))
    balken = alt.Chart(df).mark_bar(size=14, color=f["ac"], cornerRadius=2).encode(
        y=y, x=x, tooltip=alt.Tooltip("tooltip:N", title=None))
    wert = alt.Chart(df).mark_text(align="left", dx=6, color=f["text"], fontWeight=600).encode(
        y=y, x=alt.X("voll:Q", scale=alt.Scale(domain=[0, 118]), axis=None), text="label:N").transform_calculate(
        voll="100")
    delta = alt.Chart(df).mark_text(align="left", dx=62, fontWeight=600).encode(
        y=y, x=alt.X("voll:Q", scale=alt.Scale(domain=[0, 118]), axis=None), text="delta_label:N",
        color=alt.Color("ton:N", legend=None, scale=alt.Scale(domain=["gut", "schlecht", "leise"],
                                                              range=[f["gut_text"], f["schlecht_text"],
                                                                     f["text_leise"]]))
    ).transform_calculate(voll="100")
    return _thema(alt.layer(hinten, balken, wert, delta), hoehe)


# ── Befunde je Regel ───────────────────────────────────────────────────────────────────────────────────────────


def befunde_balken(zaehler: pd.DataFrame, je_schweregrad: dict[str, int] | None = None,
                   hoehe: int | None = None) -> alt.TopLevelMixin:
    """Verletzte Prüfungen je Regel, Farbe nach Schweregrad (Blocker rot, Fehler gelb, Hinweis grau) + Wort.

    Je Schweregrad die häufigsten Regeln (Standard 8 / 4 / 4), damit Fehler und Hinweise nicht verdrängt werden."""
    f = FARBEN
    df = zaehler[zaehler.verletzt > 0].copy()
    reihenfolge = {"Blocker": 0, "Fehler": 1, "Hinweis": 2}
    df["rang"] = df.schweregrad.map(reihenfolge)
    grenzen = je_schweregrad or {"Blocker": 8, "Fehler": 4, "Hinweis": 4}
    df = df.sort_values(["rang", "verletzt"], ascending=[True, False])
    df = df[df.groupby("schweregrad").cumcount() < df.schweregrad.map(lambda s: grenzen.get(s, 4))]
    df["name"] = df.regel + " · " + df.beschreibung.str.slice(0, 46)
    df["label"] = df.verletzt.map(fmt.zahl) + " · " + df.schweregrad
    df["tooltip"] = df.apply(lambda r: f"{r.regel} {r.beschreibung}: {fmt.zahl(r.verletzt)} von "
                                       f"{fmt.zahl(r.anwendbar)} ({r.schweregrad}, {r.dimension})", axis=1)
    y = alt.Y("name:N", sort=list(df["name"]), title=None, axis=alt.Axis(ticks=False, domain=False, labelLimit=320))
    x = alt.X("verletzt:Q", axis=None, scale=alt.Scale(domain=[0, float(df.verletzt.max() or 1) * 1.35]))
    farbe = alt.Color("schweregrad:N", legend=None, scale=alt.Scale(
        domain=["Blocker", "Fehler", "Hinweis"], range=[f["schlecht"], f["warnung"], f["py"]]))
    balken = alt.Chart(df).mark_bar(size=12, cornerRadius=2).encode(y=y, x=x, color=farbe,
                                                                     tooltip=alt.Tooltip("tooltip:N", title=None))
    text = alt.Chart(df).mark_text(align="left", dx=6, color=f["text_2"]).encode(y=y, x=x, text="label:N")
    return _thema(alt.layer(balken, text), hoehe or max(160, 24 * len(df) + 30))


# ── Verlauf ────────────────────────────────────────────────────────────────────────────────────────────────────


def verlauf_linien(kennzahlen: pd.DataFrame, spalten: Mapping[str, str], prozent: bool = True,
                   hoehe: int = 260) -> alt.TopLevelMixin:
    """Mehrere Reihen über die 12 Monatsstände; Unterscheidung über Helligkeit und Strichart, Endwert beschriftet."""
    f = FARBEN
    zeilen = []
    for spalte, name in spalten.items():
        for _, z in kennzahlen.iterrows():
            w = float(z[spalte])
            zeilen.append({"monat": monat_kurz(z["monatsende"]), "reihe": name, "wert": w,
                           "label": fmt.prozent(w) if prozent else fmt.zahl(w),
                           "tooltip": f"{name} · {fmt.datum(z['monatsende'])}: "
                                      f"{fmt.prozent(w) if prozent else fmt.zahl(w)}"})
    df = pd.DataFrame(zeilen)
    reihen = list(spalten.values())
    farben = [f["ac"], f["text_2"], f["py"], f["text_leise"], f["linie_stark"]][: len(reihen)]
    striche = [[1, 0], [6, 3], [2, 2], [8, 2, 2, 2], [1, 3]][: len(reihen)]
    monate = list(dict.fromkeys(df.monat))
    lo, hi = float(df.wert.min()), float(df.wert.max())
    rand = (hi - lo) * 0.15 or 1
    basis = alt.Chart(df).encode(
        x=alt.X("monat:N", sort=monate, title=None, axis=MONATSACHSE),
        y=alt.Y("wert:Q", title=None, scale=alt.Scale(domain=[lo - rand, hi + rand], zero=False),
                axis=alt.Axis(tickCount=5, domain=False, ticks=False,
                              labelExpr="replace(format(datum.value, ',.1f'), '.', ',')" if prozent
                              else "replace(format(datum.value, ',.0f'), ',', '.')")),
        color=alt.Color("reihe:N", sort=reihen, scale=alt.Scale(domain=reihen, range=farben),
                        legend=alt.Legend(title=None) if len(reihen) > 1 else None),
        strokeDash=alt.StrokeDash("reihe:N", sort=reihen, scale=alt.Scale(domain=reihen, range=striche), legend=None),
        tooltip=alt.Tooltip("tooltip:N", title=None))
    linien = basis.mark_line(strokeWidth=1.8, point=alt.OverlayMarkDef(size=26, filled=True))
    # Endwerte beschriften; nahe beieinander liegende Werte vertikal auseinanderziehen (keine Überlappung)
    enden = df[df.monat == monate[-1]].sort_values("wert", ascending=False).reset_index(drop=True)
    abstand = (hi - lo + 2 * rand) * 15 / max(hoehe - 30, 60)
    lage = list(enden.wert)
    for i in range(1, len(lage)):
        lage[i] = min(lage[i], lage[i - 1] - abstand)
    enden["lage"] = lage
    ende = alt.Chart(enden).mark_text(align="left", dx=7, fontWeight=600).encode(
        x=alt.X("monat:N", sort=monate), y=alt.Y("lage:Q"), text="label:N",
        color=alt.Color("reihe:N", sort=reihen, scale=alt.Scale(domain=reihen, range=farben), legend=None))
    return _thema(alt.layer(linien, ende), hoehe)


URSACHE_FARBE = {"bereinigt": "gut", "Neuanlagen bereit": "gut_hell", "neue Blocker durch Neuanlagen": "schlecht",
                 "verschlechtert durch Änderung": "schlecht_hell", "Alterung/Zeitablauf": "py"}


def zerlegung_balken(zerlegung: pd.DataFrame, gesamt: pd.Series, hoehe: int = 300) -> alt.TopLevelMixin:
    """Veränderung der Readiness-Quote je Monat in Pp, zerlegt nach Ursache (gestapelt, Basis 0) + Gesamtmarke."""
    f = FARBEN
    df = zerlegung.groupby(["monatsende", "ursache"], as_index=False).beitrag_pp.sum()
    df["monat"] = df.monatsende.map(monat_kurz)
    df["tooltip"] = df.apply(lambda r: f"{r.monat} · {r.ursache}: {fmt.pp(r.beitrag_pp)}", axis=1)
    monate = [monat_kurz(m) for m in sorted(df.monatsende.unique())]
    ursachen = list(URSACHE_FARBE)
    palette = {"gut": f["gut"], "gut_hell": f["gut_text"], "schlecht": f["schlecht"],
               "schlecht_hell": f["schlecht_text"], "py": f["py"]}
    x = alt.X("monat:N", sort=monate, title=None, axis=MONATSACHSE)
    balken = alt.Chart(df).mark_bar(size=22).encode(
        x=x, y=alt.Y("sum(beitrag_pp):Q", title=None, axis=alt.Axis(
            tickCount=6, domain=False, ticks=False,
            labelExpr="replace(format(datum.value, '+.1f'), '.', ',') + ' Pp'")),
        color=alt.Color("ursache:N", sort=ursachen, scale=alt.Scale(
            domain=ursachen, range=[palette[URSACHE_FARBE[u]] for u in ursachen]),
                        legend=alt.Legend(title=None, columns=3, labelLimit=260)),
        order=alt.Order("ursache:N"), tooltip=alt.Tooltip("tooltip:N", title=None))
    g = pd.DataFrame({"monat": [monat_kurz(m) for m in gesamt.index], "delta": gesamt.values})
    g["label"] = g.delta.map(lambda v: fmt.pp(v))
    marke = alt.Chart(g).mark_tick(color=f["text"], thickness=2, size=30).encode(
        x=x, y="delta:Q", tooltip=alt.Tooltip("label:N", title="Δ gesamt"))
    null = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(color=f["linie_stark"]).encode(y="y:Q")
    return _thema(alt.layer(null, balken, marke), hoehe)


def bewegungen_balken(bewegungen: pd.DataFrame, hoehe: int = 220) -> alt.TopLevelMixin:
    """Zu- und Abgänge von Befunden je Monat: neu nach oben (ungünstig), erledigt nach unten (günstig)."""
    f = FARBEN
    zeilen = []
    for _, z in bewegungen.iterrows():
        m = monat_kurz(z["monatsende"])
        zeilen.append({"monat": m, "art": "neu", "wert": int(z["neu"]), "label": f"+{z['neu']}"})
        zeilen.append({"monat": m, "art": "erledigt", "wert": -int(z["erledigt"]), "label": f"−{z['erledigt']}"})
    df = pd.DataFrame(zeilen)
    monate = list(dict.fromkeys(df.monat))
    x = alt.X("monat:N", sort=monate, title=None, axis=MONATSACHSE)
    balken = alt.Chart(df).mark_bar(size=18, cornerRadius=1.5).encode(
        x=x, y=alt.Y("wert:Q", title=None, axis=alt.Axis(
            domain=False, ticks=False, tickCount=5,
            labelExpr="replace(format(abs(datum.value), ',.0f'), ',', '.')")),
        color=alt.Color("art:N", scale=alt.Scale(domain=["neu", "erledigt"], range=[f["schlecht"], f["gut"]]),
                        legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("monat:N", title="Monat"), alt.Tooltip("art:N", title="Befunde"),
                 alt.Tooltip("label:N", title="Anzahl")])
    null = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=f["linie_stark"]).encode(y="y:Q")
    return _thema(alt.layer(null, balken), hoehe)


def score_verteilung(paare: pd.DataFrame, hoehe: int = 200) -> alt.TopLevelMixin:
    """Verteilung der Dublettenscores der Kandidatenpaare mit den Schwellen 75 und 90."""
    f = FARBEN
    df = paare.assign(klasse=(paare.score // 5 * 5).clip(upper=95).astype(int))
    zaehl = df.groupby("klasse").size().reindex(range(0, 100, 5), fill_value=0).reset_index(name="anzahl")
    zaehl["stufe"] = zaehl.klasse.map(lambda k: "≥ 90" if k >= 90 else "75–89" if k >= 75 else "< 75")
    zaehl["tooltip"] = zaehl.apply(lambda r: f"Score {r.klasse}–{r.klasse + 4.9:.1f}: {fmt.zahl(r.anzahl)} Paare",
                                   axis=1)
    balken = alt.Chart(zaehl).mark_bar(size=16, cornerRadius=1.5).encode(
        x=alt.X("klasse:O", title="Score", axis=alt.Axis(labelAngle=0, ticks=False, domain=False)),
        y=alt.Y("anzahl:Q", title=None, scale=alt.Scale(type="symlog"), axis=alt.Axis(domain=False, ticks=False)),
        color=alt.Color("stufe:N", scale=alt.Scale(domain=["< 75", "75–89", "≥ 90"],
                                                   range=[f["py"], f["warnung"], f["schlecht"]]),
                        legend=alt.Legend(title=None)),
        tooltip=alt.Tooltip("tooltip:N", title=None))
    return _thema(balken, hoehe)
