"""Validation independante du pipeline de pre-processing.

Chaque controle recalcule une feature avec une implementation DIFFERENTE de celle du
pipeline (pandas pur au lieu de SQL DuckDB), sur un echantillon de matchs, et compare.
Si deux implementations independantes donnent le meme resultat, la feature est juste.

Usage : python -m preprocessing.validate
Sortie : test/paul/resultats/validation_report.json, et un code de sortie non nul si un controle echoue.
"""

from __future__ import annotations

import json
import sys

import duckdb
import numpy as np
import pandas as pd

from . import config as C
from . import model_features as M

CLEAN = f"read_parquet('{C.SHOTS_CLEAN_PATH}')"
MODEL = f"read_parquet('{C.SHOTS_MODEL_PATH}')"
N_GAMES = 400


def _sample_games() -> pd.DataFrame:
    return duckdb.sql(f"""
        WITH g AS (SELECT DISTINCT GAME_ID FROM {CLEAN})
        SELECT s.* FROM {CLEAN} s
        JOIN (SELECT * FROM g USING SAMPLE reservoir({N_GAMES} ROWS) REPEATABLE ({C.SPLIT_SEED})) g
        USING (GAME_ID)
    """).df()


def check_sequence(df: pd.DataFrame) -> dict:
    """tirs_deja_pris et reussite_tirs_precedents, recalcules tir par tir en Python."""
    exp_n, exp_r = [], []
    idx = []
    for _, g in df.groupby(["GAME_ID", "PLAYER_ID"], sort=False):
        t = g["temps_ecoule_match_s"].to_numpy()
        y = g["cible"].to_numpy()
        # egalites de temps : rate avant reussi, puis ACTION_TYPE, LOC_X, LOC_Y
        order = np.lexsort((g["LOC_Y"].to_numpy(), g["LOC_X"].to_numpy(),
                            g["ACTION_TYPE"].to_numpy(), y, t))
        t_o, y_o = t[order], y[order]
        for pos, i in enumerate(order):
            ti = t[i]
            exp_n.append(int((t < ti).sum()))            # strictement avant
            tie = (t == ti).sum() > 1
            prev = y_o[max(0, pos - C.SEQ_WINDOW):pos]
            exp_r.append(np.nan if tie or len(prev) == 0 else prev.mean())
            idx.append(g.index[i])
    e = pd.DataFrame({"n": exp_n, "r": exp_r}, index=idx).loc[df.index]
    n_ok = (e["n"].to_numpy() == df["tirs_deja_pris"].to_numpy()).mean()
    a, b = e["r"].to_numpy(), df["reussite_tirs_precedents"].to_numpy(dtype=float)
    r_ok = (np.isclose(a, b) | (np.isnan(a) & np.isnan(b))).mean()
    return {"tirs": len(df), "tirs_deja_pris_identiques": float(n_ok),
            "reussite_tirs_precedents_identiques": float(r_ok),
            "ok": bool(n_ok == 1.0 and r_ok == 1.0)}


def check_time(df: pd.DataFrame) -> dict:
    left = df.MINS_LEFT * 60 + df.SECS_LEFT
    q = df.QUARTER
    exp = np.where(q <= 4, (q - 1) * 720 + 720 - left, 2880 + (q - 5) * 300 + 300 - left)
    ok = float((exp == df.temps_ecoule_match_s).mean())
    fin = float(((left <= C.END_OF_PERIOD_SECONDS).astype(int) == df.fin_de_periode).mean())
    return {"temps_ecoule_identique": ok, "fin_de_periode_identique": fin,
            "ok": ok == 1.0 and fin == 1.0}


def check_rest_days() -> dict:
    """jours_repos recalcule sur le calendrier complet de 6 equipes-saisons."""
    cal = duckdb.sql(f"""
        SELECT DISTINCT TEAM_ID, SEASON_1, GAME_ID, GAME_DATE, jours_repos, premier_match_saison
        FROM {CLEAN} WHERE (TEAM_ID, SEASON_1) IN (
            SELECT (TEAM_ID, SEASON_1) FROM (SELECT DISTINCT TEAM_ID, SEASON_1 FROM {CLEAN})
            USING SAMPLE reservoir(6 ROWS) REPEATABLE ({C.SPLIT_SEED}))
    """).df().sort_values(["TEAM_ID", "SEASON_1", "GAME_DATE", "GAME_ID"])
    prev = cal.groupby(["TEAM_ID", "SEASON_1"])["GAME_DATE"].shift()
    exp = ((pd.to_datetime(cal.GAME_DATE) - pd.to_datetime(prev)).dt.days - 1).clip(upper=C.REST_DAYS_CAP)
    exp = exp.fillna(C.REST_DAYS_CAP).astype(int)
    ok = float((exp.to_numpy() == cal.jours_repos.to_numpy()).mean())
    return {"matchs_equipe": len(cal), "jours_repos_identiques": ok, "ok": ok == 1.0}


def check_home() -> dict:
    """Chaque match : exactement une equipe a domicile ; ~50 % des tirs a domicile par saison."""
    per_game = duckdb.sql(f"""
        SELECT GAME_ID, count(DISTINCT TEAM_ID) FILTER (WHERE domicile = 1) AS n_home,
               count(DISTINCT TEAM_ID) AS n_teams FROM {CLEAN} GROUP BY 1
    """).df()
    bad = int(((per_game.n_teams == 2) & (per_game.n_home != 1)).sum())
    share = duckdb.sql(f"SELECT SEASON_1, avg(domicile) FROM {CLEAN} GROUP BY 1").df()
    mapping = duckdb.sql(f"""
        SELECT equipe, list(DISTINCT TEAM_NAME ORDER BY TEAM_NAME) AS noms
        FROM {CLEAN} GROUP BY 1 ORDER BY 1
    """).df()
    multi = mapping[mapping.noms.map(len) > 1]
    return {"matchs_sans_exactement_une_equipe_a_domicile": bad,
            "part_domicile_min": float(share.iloc[:, 1].min()),
            "part_domicile_max": float(share.iloc[:, 1].max()),
            "abreviations_avec_plusieurs_noms": {r.equipe: list(r.noms) for r in multi.itertuples()},
            "ok": bool(bad == 0 and 0.47 < share.iloc[:, 1].min() and share.iloc[:, 1].max() < 0.53)}


def check_zone_geometry() -> dict:
    """Coherence zone / coordonnees par saison : la correction d'echelle doit rendre les
    saisons corrigees indiscernables des autres."""
    df = duckdb.sql(f"""
        SELECT SEASON_1, bool_or(coord_corrigee) AS corrigee,
          avg((distance_ft <= 4.5)::INT) FILTER (WHERE BASIC_ZONE = 'Restricted Area') AS ra_ok,
          avg((abs(LOC_X) >= 21.5)::INT) FILTER (WHERE BASIC_ZONE IN ('Left Corner 3', 'Right Corner 3')) AS coin_ok,
          avg((distance_ft >= 22.5)::INT) FILTER (WHERE BASIC_ZONE = 'Above the Break 3') AS arc_ok,
          avg((LOC_X < 0)::INT) FILTER (WHERE BASIC_ZONE = 'Left Corner 3') AS coin_gauche_x_negatif
        FROM {CLEAN} WHERE SEASON_1 >= {C.COORD_FIABLE_FROM_SEASON} GROUP BY 1 ORDER BY 1
    """).df()
    ref = df[~df.corrigee]
    fix = df[df.corrigee]
    cols = ["ra_ok", "coin_ok", "arc_ok"]
    gap = float((fix[cols].mean() - ref[cols].mean()).abs().max())
    # Sens de l'axe X : le corner gauche doit avoir le meme signe de X sur toutes les saisons
    # (controle ajoute apres avoir constate l'inversion de l'axe sur 2019-20 a 2021-22).
    sens = df["coin_gauche_x_negatif"]
    sens_ok = bool((sens < 0.01).all() or (sens > 0.99).all())
    return {"par_saison": df.round(4).to_dict(orient="records"),
            "ecart_max_corrigees_vs_autres": gap, "sens_axe_x_identique": sens_ok,
            "ok": gap < 0.02 and sens_ok and bool((df[cols] > 0.95).all().all())}


def check_experience() -> dict:
    """Experience recalculee directement depuis les CSV bruts (toutes saisons)."""
    first = duckdb.sql(f"""SELECT PLAYER_ID, min(SEASON_1) AS premiere
                           FROM read_csv('{C.RAW_CSV_GLOB}', union_by_name = true) GROUP BY 1""").df()
    d = duckdb.sql(f"""SELECT PLAYER_ID, SEASON_1, saisons_depuis_premiere_apparition AS xp,
                              experience_censuree AS cens FROM {CLEAN}
                       USING SAMPLE reservoir(200000 ROWS) REPEATABLE ({C.SPLIT_SEED})""").df()
    d = d.merge(first, on="PLAYER_ID")
    ok_xp = float((d.xp == d.SEASON_1 - d.premiere).mean())
    ok_c = float((d.cens == (d.premiere == C.FIRST_SEASON_IN_DATA).astype(int)).mean())
    return {"experience_identique": ok_xp, "censure_identique": ok_c, "ok": ok_xp == 1.0 and ok_c == 1.0}


def check_players() -> dict:
    """La selection des joueurs du projet, refaite en pandas a partir de la regle."""
    st = duckdb.sql(f"""SELECT PLAYER_ID, any_value(PLAYER_NAME) AS nom, count(*) AS tirs,
                               count(DISTINCT SEASON_1) AS saisons, max(SEASON_1) AS derniere,
                               bool_or(joueur_projet) AS retenu_pipeline
                        FROM {CLEAN} GROUP BY 1""").df()
    st = st[st.nom.isin(C.ESPN_TOP_25)]
    attendu = (st.derniere == C.LAST_SEASON_IN_DATA) & (st.saisons >= C.MIN_SEASONS) & (st.tirs >= C.MIN_SHOTS)
    return {"joueurs_retenus": sorted(st.loc[attendu, "nom"]),
            "ok": bool((attendu == st.retenu_pipeline).all())}


def check_splits() -> dict:
    df = duckdb.sql(f"""
        SELECT split, count(*) n, count(DISTINCT GAME_ID) g, avg(cible) fg,
               count(DISTINCT SEASON_1) saisons, count(DISTINCT PLAYER_ID) joueurs
        FROM {MODEL} GROUP BY 1 ORDER BY 1
    """).df()
    overlap = duckdb.sql(f"""SELECT count(*) FROM (SELECT GAME_ID FROM {MODEL}
                             GROUP BY 1 HAVING count(DISTINCT split) > 1)""").fetchone()[0]
    # determinisme : on recalcule le hachage en Python sur 1 000 matchs
    g = duckdb.sql(f"""SELECT DISTINCT GAME_ID, split FROM {MODEL}
                       USING SAMPLE reservoir(1000 ROWS) REPEATABLE (1)""").df()
    u = ((g.GAME_ID.astype(np.int64) * 2654435761 + C.SPLIT_SEED) % 4294967296) / 4294967296.0
    tr = C.SPLIT_FRACTIONS["train"]
    va = tr + C.SPLIT_FRACTIONS["val"]
    exp = np.where(u < tr, "train", np.where(u < va, "val", "test"))
    det = float((exp == g.split.to_numpy()).mean())
    fg_spread = float(df.fg.max() - df.fg.min())
    return {"par_split": df.round(4).to_dict(orient="records"), "matchs_partages": int(overlap),
            "hachage_reproduit": det, "ecart_max_taux_reussite": fg_spread,
            "ok": overlap == 0 and det == 1.0 and fg_spread < 0.005}


def check_schema() -> dict:
    cols = duckdb.sql(f"SELECT * FROM {MODEL} LIMIT 0").columns
    forbidden = [c for c in ("EVENT_TYPE", "SHOT_MADE") if c in cols]
    missing = [c for c in M.MODEL_COLUMNS if c not in cols]
    target_in_features = M.TARGET in M.FEATURES
    nulls = duckdb.sql(
        "SELECT " + ", ".join(f"sum(({c} IS NULL)::INT) AS \"{c}\"" for c in M.FEATURES)
        + f" FROM {MODEL}").df().T[0]
    nulls = {k: int(v) for k, v in nulls.items() if v > 0}
    gestes = duckdb.sql(f"SELECT count(DISTINCT geste_famille) FROM {MODEL}").fetchone()[0]
    return {"colonnes_interdites_presentes": forbidden, "colonnes_manquantes": missing,
            "cible_parmi_features": target_in_features, "features_avec_nulls": nulls,
            "familles_geste": gestes,
            "ok": not forbidden and not missing and not target_in_features
                  and set(nulls) <= {"reussite_tirs_precedents"} and gestes == 6}


def run() -> dict:
    sample = _sample_games()
    res = {
        "sequence_intra_match": check_sequence(sample),
        "temps": check_time(sample),
        "jours_repos": check_rest_days(),
        "domicile": check_home(),
        "geometrie_zones": check_zone_geometry(),
        "experience": check_experience(),
        "selection_joueurs": check_players(),
        "decoupages": check_splits(),
        "schema": check_schema(),
    }
    res["tous_ok"] = all(v["ok"] for v in res.values() if isinstance(v, dict))
    (C.OUTPUT_DIR / "validation_report.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run()
    for k, v in r.items():
        if isinstance(v, dict):
            print(f"[{'OK ' if v['ok'] else 'ECHEC'}] {k}")
    print("TOUS LES CONTROLES OK" if r["tous_ok"] else "AU MOINS UN CONTROLE EN ECHEC")
    sys.exit(0 if r["tous_ok"] else 1)
