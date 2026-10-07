"""Figures et validations statistiques du rapport de pre-processing.

Chaque fonction `fig_*` renvoie (figure matplotlib, dictionnaire de statistiques)
et enregistre la figure dans test/paul/figures/. Le notebook preprocessing.ipynb les
appelle une par une ; `python -m preprocessing.figures` les regenere toutes.

Palette : bleu / orange de la palette de reference (verifiee daltonisme), gris neutre
pour les elements de contexte. Une seule echelle par graphique.
"""

from __future__ import annotations

import json
import sys

import duckdb
import matplotlib

if "ipykernel" not in sys.modules:   # en script : pas d'ecran ; en notebook : affichage inline
    matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Arc, Circle, Rectangle  # noqa: E402
from scipy import stats  # noqa: E402

from . import config as C  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
GRAY, GRID = "#b5b3ab", "#e6e5e0"
INK, INK2 = "#0b0b0b", "#52514e"
SURFACE = "#fcfcfb"

CLEAN = f"read_parquet('{C.SHOTS_CLEAN_PATH}')"
RAW = f"read_csv('{C.RAW_CSV_GLOB}', union_by_name = true)"
MODEL = f"read_parquet('{C.SHOTS_MODEL_PATH}')"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRAY, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 12.5, "axes.titleweight": "semibold", "axes.titlelocation": "left",
    "axes.labelsize": 10, "xtick.color": INK2, "ytick.color": INK2,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 9,
    "font.family": "DejaVu Sans", "text.color": INK,
})


def fr(v: float, d: int = 1) -> str:
    """Nombre au format francais (virgule decimale)."""
    return f"{v:.{d}f}".replace(".", ",")


def frpct(v: float, d: int = 1) -> str:
    return f"{fr(100 * v, d)} %"


def _save(fig, name: str):
    fig.savefig(C.FIG_DIR / f"{name}.png", dpi=160, bbox_inches="tight")
    return fig


def _q(sql: str):
    return duckdb.sql(sql)


def _season_labels(seasons):
    return [f"{s - 1}-{str(s)[-2:]}" for s in seasons]


def _pct_fmt(ax, axis="y"):
    from matplotlib.ticker import PercentFormatter
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(PercentFormatter(1.0, decimals=0))


def _prop_ztest(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    se_diff = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return {"p1": p1, "p2": p2, "diff_pts": 100 * (p1 - p2), "ic95_pts": 100 * 1.96 * se_diff,
            "z": z, "p_value": 2 * stats.norm.sf(abs(z)), "n1": int(n1), "n2": int(n2)}


def draw_court(ax, color=GRAY, lw=1.0):
    """Demi-terrain dans le repere des CSV (pieds, origine ligne de fond, panier a 5.25)."""
    b = C.BASKET_Y
    y_break = b + np.sqrt(C.ARC_THREE_FT ** 2 - C.CORNER_THREE_FT ** 2)
    ang = np.degrees(np.arcsin((y_break - b) / C.ARC_THREE_FT))
    items = [
        Circle((0, b), 0.75, fill=False),
        Rectangle((-3, 4), 6, 0, fill=False),
        Rectangle((-8, 0), 16, 19, fill=False),
        Arc((0, 19), 12, 12, theta1=0, theta2=180),
        Arc((0, b), 8, 8, theta1=0, theta2=180),
        Arc((0, b), 2 * C.ARC_THREE_FT, 2 * C.ARC_THREE_FT, theta1=ang, theta2=180 - ang),
        Rectangle((-25, 0), 50, 47, fill=False),
    ]
    for it in items:
        it.set_edgecolor(color)
        it.set_linewidth(lw)
        ax.add_patch(it)
    for x in (-C.CORNER_THREE_FT, C.CORNER_THREE_FT):
        ax.plot([x, x], [0, y_break], color=color, lw=lw)
    ax.set_xlim(-25.5, 25.5)
    ax.set_ylim(-1, 47.5)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


# --------------------------------------------------------------------------
def fig_rupture_panier():
    """Part des tirs de zone restreinte au point du panier, sur toutes les saisons brutes."""
    df = _q(f"""
        SELECT SEASON_1,
               avg((abs(LOC_X) < 0.05 AND abs(LOC_Y - {C.BASKET_Y}) < 0.3)::INT) AS part,
               count(*) AS n,
               sum((abs(LOC_X) < 0.05 AND abs(LOC_Y - {C.BASKET_Y}) < 0.3)::INT) AS k
        FROM {RAW} WHERE BASIC_ZONE = 'Restricted Area' GROUP BY 1 ORDER BY 1
    """).df()
    avant = df[df.SEASON_1 < C.COORD_FIABLE_FROM_SEASON]
    apres = df[df.SEASON_1 >= C.COORD_FIABLE_FROM_SEASON]
    st = _prop_ztest(avant.k.sum(), avant.n.sum(), apres.k.sum(), apres.n.sum())
    st.update({"part_avant": st["p1"], "part_apres": st["p2"],
               "tirs_concernes_avant": int(avant.k.sum())})

    fig, ax = plt.subplots(figsize=(9, 3.8))
    x = np.arange(len(df))
    i0 = int((df.SEASON_1 < C.FIRST_SEASON).sum())
    ax.axvspan(i0 - 0.5, len(df) - 0.5, color=GRID, alpha=0.6, lw=0)
    ax.plot(x, df.part, color=BLUE, lw=2, marker="o", ms=5)
    ax.set_xticks(x, _season_labels(df.SEASON_1), rotation=60, ha="right")
    _pct_fmt(ax)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Part des tirs de zone restreinte")
    ax.set_title("Avant 2010-11, la majorité des tirs au cercle sont ramenés au point du panier")
    ax.text((i0 + len(df)) / 2 - 0.5, 0.93, "fenêtre retenue (10 saisons)", ha="center",
            color=INK2, fontsize=9)
    fig.tight_layout()
    return _save(fig, "prep_01_rupture_panier"), st


def fig_echelle_distance():
    """Ecart moyen |SHOT_DISTANCE - distance recalculee| par saison, avant et apres correction."""
    audit = json.loads(C.AUDIT_PATH.read_text(encoding="utf-8"))
    av = {int(k): v for k, v in audit["mae_distance_par_saison_avant"].items()}
    ap = {int(k): v for k, v in audit["mae_distance_par_saison_apres"].items()}
    seasons = sorted(av)
    st = {"saisons_corrigees": audit["saisons_echelle_corrompue"],
          "mae_avant_saisons_corrigees": {s: av[s] for s in audit["saisons_echelle_corrompue"]},
          "mae_apres_saisons_corrigees": {s: ap[s] for s in audit["saisons_echelle_corrompue"]},
          "mae_max_apres": max(ap.values()), "lignes_corrigees": audit["lignes_coordonnees_corrigees"]}

    fig, ax = plt.subplots(figsize=(9, 3.8))
    x = np.arange(len(seasons))
    ax.plot(x, [av[s] for s in seasons], color=ORANGE, lw=2, marker="o", ms=5, label="Avant correction")
    ax.plot(x, [ap[s] for s in seasons], color=BLUE, lw=2, marker="o", ms=5, label="Après correction")
    ax.axhline(C.SCALE_MAE_THRESHOLD_FT, color=GRAY, lw=1, ls="--")
    ax.text(0, C.SCALE_MAE_THRESHOLD_FT + 0.3, f"seuil de détection ({C.SCALE_MAE_THRESHOLD_FT:.0f} ft)",
            color=INK2, fontsize=9)
    ax.set_xticks(x, _season_labels(seasons), rotation=60, ha="right")
    ax.set_ylabel("Écart moyen (pieds)")
    ax.set_title("Trois saisons ont des coordonnées à la mauvaise échelle, corrigées par le pipeline")
    i = seasons.index(audit["saisons_echelle_corrompue"][0])
    ax.annotate("2019-20 à 2021-22", (i + 1, av[seasons[i + 1]]), xytext=(i - 5.5, 10),
                color=INK2, fontsize=9, arrowprops=dict(arrowstyle="-", color=GRAY))
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.85))
    fig.tight_layout()
    return _save(fig, "prep_02_echelle_distance"), st


def fig_shotchart_correction(season: int = 2021, n: int = 25_000):
    """Positions des tirs d'une saison corrompue : brutes (CSV) puis corrigees."""
    raw = _q(f"""
        SELECT * FROM (SELECT LOC_X, LOC_Y FROM read_csv('{C.RAW_CSV_GLOB}', union_by_name = true) WHERE SEASON_1 = {season})
        USING SAMPLE reservoir({n} ROWS) REPEATABLE ({C.SPLIT_SEED})
    """).df()
    fix = _q(f"""
        SELECT * FROM (SELECT LOC_X, LOC_Y FROM {CLEAN} WHERE SEASON_1 = {season})
        USING SAMPLE reservoir({n} ROWS) REPEATABLE ({C.SPLIT_SEED})
    """).df()
    st = {"saison": _season_labels([season])[0],
          "etendue_y_brute": [float(raw.LOC_Y.min()), float(raw.LOC_Y.max())],
          "etendue_y_corrigee": [float(fix.LOC_Y.min()), float(fix.LOC_Y.max())]}
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.2))
    for ax, d, t in ((axes[0], raw, "Coordonnées brutes du CSV"), (axes[1], fix, "Après correction")):
        draw_court(ax)
        ax.scatter(d.LOC_X, d.LOC_Y, s=1.5, color=BLUE, alpha=0.18, lw=0)
        ax.set_title(t, fontsize=11)
    fig.suptitle(f"Saison {st['saison']} : échantillon de {n:,} tirs".replace(",", " "),
                 x=0.02, ha="left", fontsize=12.5, fontweight="semibold")
    fig.tight_layout()
    return _save(fig, "prep_03_shotchart_correction"), st


def fig_couverture_joueurs():
    """Tirs sur la fenetre des joueurs du top 25 ESPN encore actifs, avec le seuil de selection."""
    audit = json.loads(C.AUDIT_PATH.read_text(encoding="utf-8"))
    import pandas as pd
    d = pd.DataFrame(audit["selection_joueurs"])
    d = d[d.derniere_saison == C.LAST_SEASON_IN_DATA].sort_values("tirs")
    st = {"retenus": d[d.retenu].joueur.tolist(), "exclus": d[~d.retenu].joueur.tolist(),
          "tirs_retenus": int(d[d.retenu].tirs.sum())}
    fig, ax = plt.subplots(figsize=(9, 5))
    y = np.arange(len(d))
    ax.barh(y, d.tirs, color=[BLUE if r else GRAY for r in d.retenu], height=0.7)
    for yi, t, sa in zip(y, d.tirs, d.saisons):
        ax.text(t + 150, yi, f"{t:,}".replace(",", " ") + f"  ·  {sa} saisons", va="center",
                fontsize=8.5, color=INK2)
    ax.axvline(C.MIN_SHOTS, color=ORANGE, lw=1.2, ls="--")
    ax.text(C.MIN_SHOTS + 150, -0.9, f"seuil : {C.MIN_SHOTS:,} tirs".replace(",", " "),
            color=INK2, fontsize=9)
    ax.set_yticks(y, [f"{n}  (n° {r} ESPN)" for n, r in zip(d.joueur, d.rang_espn)])
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-1.3, len(d) - 0.4)
    ax.set_xlim(0, d.tirs.max() * 1.3)
    ax.set_xlabel("Tirs tentés de 2015-16 à 2024-25")
    ax.set_title(f"{len(st['retenus'])} des {len(d)} joueurs du top 25 ESPN encore actifs passent la règle")
    fig.tight_layout()
    return _save(fig, "prep_04_couverture_joueurs"), st


def fig_reussite_geste():
    """Taux de reussite par famille de geste (saisons fiables)."""
    df = _q(f"""
        SELECT geste_famille, count(*) AS n, avg(cible) AS fg, sum(cible) AS k
        FROM {MODEL} GROUP BY 1 ORDER BY fg
    """).df()
    table = np.array([df.k, df.n - df.k])
    chi2, p, dof, _ = stats.chi2_contingency(table)
    n = df.n.sum()
    st = {"chi2": float(chi2), "ddl": int(dof), "p_value": float(p),
          "v_cramer": float(np.sqrt(chi2 / n)),
          "reussite": dict(zip(df.geste_famille, df.fg.round(4))), "n": dict(zip(df.geste_famille, df.n))}
    moy = float((df.k.sum()) / n)
    fig, ax = plt.subplots(figsize=(9, 3.9))
    y = np.arange(len(df))
    ax.barh(y, df.fg, color=BLUE, height=0.65)
    for yi, fg, nn in zip(y, df.fg, df.n):
        ax.text(fg + 0.01, yi, f"{frpct(fg)}  ·  " + f"{nn:,} tirs".replace(",", " "), va="center",
                fontsize=9, color=INK2)
    ax.axvline(moy, color=INK2, lw=1, ls="--")
    ax.text(moy + 0.005, -0.75, f"moyenne {frpct(moy)}", color=INK2, fontsize=9)
    ax.set_ylim(-0.9, len(df) - 0.5)
    ax.set_yticks(y, df.geste_famille)
    ax.grid(axis="y", visible=False)
    _pct_fmt(ax, "x")
    ax.set_xlim(0, 1.12)
    ax.set_xlabel("Taux de réussite")
    ax.set_title(f"Le geste sépare les tirs de {frpct(df.fg.min(), 0)} à {frpct(df.fg.max(), 0)} de réussite")
    fig.tight_layout()
    return _save(fig, "prep_05_reussite_geste"), st


def fig_reussite_distance(max_ft: int = 35):
    """Taux de reussite par pied de distance (distance exacte recalculee)."""
    df = _q(f"""
        SELECT floor(distance_ft)::INT AS d, count(*) AS n, avg(cible) AS fg
        FROM {MODEL} WHERE distance_ft < {max_ft} GROUP BY 1 ORDER BY 1
    """).df()
    smp = _q(f"""SELECT distance_ft, cible FROM {MODEL}
                 USING SAMPLE reservoir(500000 ROWS) REPEATABLE ({C.SPLIT_SEED})""").df()
    r, p = stats.pointbiserialr(smp.cible, smp.distance_ft)
    rho, p_rho = stats.spearmanr(smp.distance_ft, smp.cible)
    st = {"r_point_biserial": float(r), "p_value": float(p), "spearman": float(rho),
          "reussite_0_3ft": float(df[df.d < 3].eval("fg*n").sum() / df[df.d < 3].n.sum()),
          "reussite_10_20ft": float(df[(df.d >= 10) & (df.d < 20)].eval("fg*n").sum()
                                    / df[(df.d >= 10) & (df.d < 20)].n.sum()),
          "reussite_24_27ft": float(df[(df.d >= 24) & (df.d < 27)].eval("fg*n").sum()
                                    / df[(df.d >= 24) & (df.d < 27)].n.sum())}
    fig, ax = plt.subplots(figsize=(9, 3.9))
    ax.plot(df.d + 0.5, df.fg, color=BLUE, lw=2, marker="o", ms=4)
    for xv, t in ((C.CORNER_THREE_FT, "3 pts (coin)"), (C.ARC_THREE_FT, "3 pts (arc)")):
        ax.axvline(xv, color=GRAY, lw=1, ls="--")
    ax.text(C.ARC_THREE_FT + 0.4, 0.70, "ligne à 3 points\n(22 ft coin, 23,75 ft arc)", color=INK2, fontsize=9)
    _pct_fmt(ax)
    ax.set_ylim(0, 0.8)
    ax.set_xlim(0, max_ft)
    ax.set_xlabel("Distance au panier (pieds)")
    ax.set_ylabel("Taux de réussite")
    ax.set_title("La réussite s'effondre sur les 5 premiers pieds, puis reste proche de 40 % jusqu'à 20 pieds")
    fig.tight_layout()
    return _save(fig, "prep_06_reussite_distance"), st


def fig_effets_contexte():
    """Ecart de reussite (points de %) associe a chaque variable de contexte."""
    conds = [
        ("fin_de_periode", "Fin de période (3 dernières s)"),
        ("premier_tir_match", "Premier tir du joueur dans le match"),
        ("prolongation", "Prolongation"),
        ("back_to_back", "Back-to-back (0 jour de repos)"),
        ("domicile", "À domicile"),
    ]
    st = {}
    for c, _ in conds:
        k1, n1, k2, n2 = _q(f"""
            SELECT sum(cible) FILTER (WHERE {c} = 1), count(*) FILTER (WHERE {c} = 1),
                   sum(cible) FILTER (WHERE {c} = 0), count(*) FILTER (WHERE {c} = 0)
            FROM {MODEL}""").fetchone()
        st[c] = _prop_ztest(k1, n1, k2, n2)
    order = sorted(conds, key=lambda t: st[t[0]]["diff_pts"])
    fig, ax = plt.subplots(figsize=(9, 3.6))
    y = np.arange(len(order))
    d = [st[c]["diff_pts"] for c, _ in order]
    e = [st[c]["ic95_pts"] for c, _ in order]
    ax.barh(y, d, xerr=e, color=BLUE, height=0.6, error_kw=dict(ecolor=INK2, lw=1, capsize=3))
    for yi, (c, _) in zip(y, order):
        v, e_ = st[c]["diff_pts"], st[c]["ic95_pts"]
        lab = ("+" if v >= 0 else "\u2212") + fr(abs(v)) + " pt"
        ax.text(v + (e_ + 0.3 if v >= 0 else -e_ - 0.3), yi, lab, va="center",
                ha="left" if v >= 0 else "right", fontsize=9, color=INK2)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y, [lab for _, lab in order])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(min(d) - 4, max(max(d), 0) + 4)
    ax.set_xlabel("Écart de réussite vs le reste des tirs (points de %), IC 95 %")
    ax.set_title("Seule la fin de période pèse fortement ; le reste est réel mais faible")
    fig.tight_layout()
    return _save(fig, "prep_07_effets_contexte"), st


def fig_auc_univariee():
    """AUC de chaque feature prise seule (controle de fuite)."""
    res = json.loads((C.OUTPUT_DIR / "leakage_check.json").read_text(encoding="utf-8"))
    uni = sorted(res["univariee"], key=lambda r: r["auc"])
    st = {k: res[k] for k in ("lr3_auc_val", "lr_complete_auc_val",
                              "lr_complete_auc_test_temporel", "verdict", "features_suspectes")}
    st["auc_max_univariee"] = max(r["auc"] for r in uni)
    fig, ax = plt.subplots(figsize=(9, 7))
    y = np.arange(len(uni))
    ax.barh(y, [r["auc"] - 0.5 for r in uni], left=0.5, color=BLUE, height=0.65)
    ax.axvline(0.80, color=ORANGE, lw=1.2, ls="--")
    ax.text(0.795, len(uni) - 1, "seuil d'alerte\nfuite (0,80)", ha="right", va="top", color=INK2, fontsize=9)
    ax.set_yticks(y, [r["feature"] for r in uni], fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0.5, 0.85)
    ax.set_xlabel("AUC de la feature seule (0,5 = hasard), jeu de validation")
    ax.set_title("Aucune feature seule n'approche le seuil de fuite")
    fig.tight_layout()
    return _save(fig, "prep_08_auc_univariee"), st


def fig_derive_temporelle():
    """Evolution du jeu : part des tirs a 3 points et reussite, par saison."""
    df = _q(f"""SELECT SEASON_1, avg((SHOT_TYPE LIKE '3PT%')::INT) AS part3,
                       avg(SHOT_MADE::INT) AS fg, count(*) AS n
                FROM {RAW} WHERE ACTION_TYPE <> 'No Shot' GROUP BY 1 ORDER BY 1""").df()
    rho, p = stats.spearmanr(df.SEASON_1, df.part3)
    st = {"part3_debut": float(df.part3.iloc[0]), "part3_fin": float(df.part3.iloc[-1]),
          "fg_debut": float(df.fg.iloc[0]), "fg_fin": float(df.fg.iloc[-1]),
          "spearman_part3_saison": float(rho), "p_value": float(p)}
    fig, ax = plt.subplots(figsize=(9, 3.9))
    x = np.arange(len(df))
    i0 = int((df.SEASON_1 < C.FIRST_SEASON).sum())
    ax.axvspan(i0 - 0.5, len(df) - 0.5, color=GRID, alpha=0.6, lw=0)
    ax.text((i0 + len(df)) / 2 - 0.5, 0.52, "fenêtre retenue", ha="center", color=INK2, fontsize=9)
    ax.plot(x, df.part3, color=ORANGE, lw=2, marker="o", ms=4)
    ax.plot(x, df.fg, color=BLUE, lw=2, marker="o", ms=4)
    ax.text(x[-1] + 0.4, df.part3.iloc[-1] - 0.04, "Part des tirs\nà 3 points", color=INK2, fontsize=9, va="center")
    ax.text(x[-1] + 0.4, df.fg.iloc[-1] + 0.04, "Taux de\nréussite", color=INK2, fontsize=9, va="center")
    ax.set_xticks(x, _season_labels(df.SEASON_1), rotation=60, ha="right")
    _pct_fmt(ax)
    ax.set_ylim(0, 0.55)
    ax.set_xlim(-0.5, len(df) + 1.8)
    ax.set_title(f"La part des tirs à 3 points passe de {frpct(st['part3_debut'], 0)} à "
                 f"{frpct(st['part3_fin'], 0)} : le jeu n'est pas stationnaire")
    fig.tight_layout()
    return _save(fig, "prep_09_derive_temporelle"), st


def fig_ablation():
    """Gain d'AUC en ajoutant les groupes de features (gradient boosting, validation)."""
    res = json.loads((C.OUTPUT_DIR / "baseline_preview.json").read_text(encoding="utf-8"))
    ab = res["ablation_hgb"]
    labels = {"1_geometrie": "Géométrie (distance, angle, zone)", "2_geste": "+ geste",
              "3_contexte_match": "+ contexte de match", "4_joueur_sequence": "+ joueur et séquence"}
    rows = [(labels[a["groupe"]], a["auc"]) for a in ab]
    rows.append(("+ adresse au-delà de l'attendu", res["hgb_avec_adresse_hors_attente"]["auc"]))
    st = {"auc_par_etape": dict(rows), "auc_regression_logistique": res["regression_logistique"]["auc"],
          "auc_test_temporel": res["hgb_test_temporel"]["auc"]}
    fig, ax = plt.subplots(figsize=(9, 3.6))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [r[1] - 0.5 for r in rows], left=0.5, color=BLUE, height=0.6)
    prev = None
    for yi, (lab, v) in zip(y, rows):
        gain = "" if prev is None else f"  ({'+' if v >= prev else chr(0x2212)}{fr(abs(v - prev), 3)})"
        ax.text(v + 0.002, yi, fr(v, 3) + gain, va="center", fontsize=9, color=INK2)
        prev = v
    lr = st["auc_regression_logistique"]
    ax.axvline(lr, color=ORANGE, lw=1.2, ls="--")
    ax.text(lr - 0.002, y[-1] - 0.5, f"régression logistique ({fr(lr, 3)})", ha="right",
            color=INK2, fontsize=9)
    ax.set_yticks(y, [r[0] for r in rows])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0.5, 0.72)
    ax.set_ylim(-0.8, len(rows) - 0.5)
    ax.set_xlabel("AUC en validation (gradient boosting)")
    ax.set_title("Le geste apporte l'essentiel du gain après la géométrie")
    fig.tight_layout()
    return _save(fig, "prep_10_ablation"), st


def fig_calibration_joueurs():
    """Reussite reelle et predite pour les 12 actifs (jeu de validation)."""
    res = json.loads((C.OUTPUT_DIR / "baseline_preview.json").read_text(encoding="utf-8"))
    import pandas as pd
    d = pd.DataFrame(res["par_joueur_actif"]).sort_values("reussite_reelle")
    b0 = 100 * (d.predite_sans_joueur - d.reussite_reelle)
    b1 = 100 * (d.predite_adresse_hors_attente - d.reussite_reelle)
    st = {"biais_abs_moyen_sans_joueur_pts": float(b0.abs().mean()),
          "biais_abs_moyen_avec_adresse_pts": float(b1.abs().mean())}
    fig, ax = plt.subplots(figsize=(9, 5.2))
    y = np.arange(len(d))
    for yi, r in zip(y, d.itertuples()):
        ax.plot([r.predite_sans_joueur, r.reussite_reelle], [yi, yi], color=GRID, lw=3, zorder=1)
    ax.scatter(d.predite_sans_joueur, y, s=60, color=ORANGE, zorder=3, label="Prédite, sans info joueur",
               edgecolor=SURFACE, linewidth=1.5)
    ax.scatter(d.predite_adresse_hors_attente, y, s=60, color=BLUE, zorder=3,
               label="Prédite, avec adresse au-delà de l'attendu", edgecolor=SURFACE, linewidth=1.5)
    ax.scatter(d.reussite_reelle, y, s=70, color=INK, marker="D", zorder=4, label="Réussite réelle",
               edgecolor=SURFACE, linewidth=1.5)
    ax.set_yticks(y, d.joueur)
    ax.grid(axis="y", visible=False)
    _pct_fmt(ax, "x")
    ax.set_xlabel("Taux de réussite moyen sur le jeu de validation")
    ax.set_title(f"Sans info joueur, le niveau de chaque joueur est faux de {fr(st['biais_abs_moyen_sans_joueur_pts'])} points en moyenne")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return _save(fig, "prep_11_calibration_joueurs"), st


def fig_importance():
    """Importance par permutation des 32 features, et features retenues."""
    from . import model_features as M
    res = json.loads((C.OUTPUT_DIR / "feature_selection.json").read_text(encoding="utf-8"))
    imp = res["importance"]
    feats = list(imp)[::-1]
    vals = [max(imp[f], 0) for f in feats]
    keep = set(M.FEATURES_RETENUES)
    st = {"sous_ensembles": {s["k"]: s["auc"] for s in res["sous_ensembles"]},
          "retenues": M.FEATURES_RETENUES}
    fig, ax = plt.subplots(figsize=(9, 8))
    y = np.arange(len(feats))
    ax.barh(y, vals, color=[BLUE if f in keep else GRAY for f in feats], height=0.7)
    ax.set_yticks(y, feats, fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Baisse de l'AUC quand la feature est mélangée au hasard (jeu de validation)")
    ax.set_title(f"{len(keep)} features portent toute l'information utile au modèle")
    ax.text(max(vals) * 0.98, 4, "bleu : les 12 features retenues\ngris : redondantes pour le modèle",
            ha="right", va="center", color=INK2, fontsize=9.5)
    fig.tight_layout()
    return _save(fig, "prep_12_importance_features"), st


ALL = [fig_rupture_panier, fig_echelle_distance, fig_shotchart_correction, fig_couverture_joueurs,
       fig_reussite_geste, fig_reussite_distance, fig_effets_contexte, fig_auc_univariee,
       fig_derive_temporelle, fig_ablation, fig_calibration_joueurs, fig_importance]


def run_all() -> dict:
    out = {}
    for f in ALL:
        fig, st = f()
        plt.close(fig)
        out[f.__name__] = st
    (C.OUTPUT_DIR / "preprocessing_stats.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    return out


if __name__ == "__main__":
    res = run_all()
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))
