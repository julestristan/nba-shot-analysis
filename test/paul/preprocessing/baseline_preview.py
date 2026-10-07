"""Apercu de modelisation : le dataset est-il pret, et ou est l'information ?

Premiers modeles, sans aucun reglage d hyperparametres. Le but est de
verifier que le dataset produit se modelise sans difficulte, et de mesurer l'apport
de chaque groupe de features (ablation) avant de choisir les modeles.

Controles :
  1. Reference naive (taux de base) et regression logistique complete.
  2. Ablation avec un gradient boosting (HistGradientBoosting) : on ajoute les groupes
     de features un par un et on mesure le gain d'AUC en validation.
  3. Apport de l'identite du joueur (encodage par la moyenne hors echantillon).
  4. Robustesse temporelle (split_temps) et resultats par joueur actif (AUC, calibration).

Usage : python -m preprocessing.baseline_preview   (5 a 10 minutes)
"""

from __future__ import annotations

import json
import logging
import time

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline

from . import config as C
from . import model_features as M

log = logging.getLogger(__name__)
N_TRAIN, N_VAL = 500_000, 300_000

GROUPS = {
    "1_geometrie": ["distance_ft", "angle_deg", "LOC_X", "LOC_Y", "tir_3pts", "tir_backcourt",
                    "BASIC_ZONE"],
    "2_geste": ["geste_famille", "ACTION_TYPE", "tir_planche", "en_course", "en_desequilibre",
                "alley_oop"],
    "3_contexte_match": ["temps_restant_periode_s", "temps_ecoule_match_s", "QUARTER",
                         "prolongation", "fin_de_periode", "derniere_minute", "domicile", "jours_repos",
                         "back_to_back", "premier_match_saison", "equipe", "adversaire"],
    "4_joueur_sequence": ["POSITION", "POSITION_GROUP", "saisons_depuis_premiere_apparition",
                          "experience_censuree", "tirs_deja_pris", "premier_tir_match",
                          "reussite_tirs_precedents"],
}
assert sorted(sum(GROUPS.values(), [])) == sorted(M.FEATURES), "les groupes doivent couvrir toutes les features"


def _load(where: str, n: int | None, extra=()) -> pd.DataFrame:
    cols = ", ".join(M.FEATURES + [M.TARGET, "GAME_ID", "PLAYER_ID", "PLAYER_NAME",
                                   "actif_2024_25", "joueur_projet", *extra])
    inner = f"SELECT {cols} FROM read_parquet('{C.SHOTS_MODEL_PATH}') WHERE {where}"
    q = inner if n is None else (
        f"SELECT * FROM ({inner}) USING SAMPLE reservoir({n} ROWS) REPEATABLE ({C.SPLIT_SEED})")
    return duckdb.sql(q).df()


def _metrics(y, p) -> dict:
    return {"auc": float(roc_auc_score(y, p)), "log_loss": float(log_loss(y, p)),
            "brier": float(brier_score_loss(y, p))}


class _HGB:
    """HistGradientBoosting avec categorielles encodees en entiers (codes appris sur le train)."""

    def __init__(self, features):
        self.features = list(features)
        self.cats = [c for c in self.features if c in M.CATEGORICAL]
        self.maps = {}
        self.model = HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.1, max_leaf_nodes=63, early_stopping=True,
            validation_fraction=0.1, n_iter_no_change=20,
            categorical_features=[c in self.cats for c in self.features], random_state=0)

    def _X(self, df):
        X = df[self.features].copy()
        for c in self.cats:
            X[c] = X[c].map(self.maps[c]).fillna(-1).astype(float)
            X.loc[X[c] < 0, c] = np.nan   # categorie inconnue -> valeur manquante
        return X.astype(float)

    def fit(self, df):
        for c in self.cats:
            vc = df[c].value_counts()
            self.maps[c] = {k: i for i, k in enumerate(vc.index[:250])}   # limite HGB : 255
        self.model.fit(self._X(df), df[M.TARGET])
        return self

    def predict(self, df):
        return self.model.predict_proba(self._X(df))[:, 1]


def _player_target_encoding(tr: pd.DataFrame, others: list[pd.DataFrame], m: float = 200.0):
    """Reussite lissee du joueur. Sur le train : hors echantillon (5 plis par match), pour
    que la ligne ne voie jamais son propre resultat. Sur val/test : moyenne du train."""
    prior = tr[M.TARGET].mean()
    fold = (tr["GAME_ID"].astype(np.int64) * 2654435761 % 4294967296) % 5
    te = np.empty(len(tr))
    for k in range(5):
        fit, app = fold != k, fold == k
        s = tr[fit].groupby("PLAYER_ID")[M.TARGET].agg(["sum", "count"])
        enc = (s["sum"] + m * prior) / (s["count"] + m)
        te[app.to_numpy()] = tr.loc[app, "PLAYER_ID"].map(enc).fillna(prior).to_numpy()
    tr = tr.assign(joueur_te=te)
    s = tr.groupby("PLAYER_ID")[M.TARGET].agg(["sum", "count"])
    enc = (s["sum"] + m * prior) / (s["count"] + m)
    return tr, [o.assign(joueur_te=o["PLAYER_ID"].map(enc).fillna(prior)) for o in others]


def _player_residual_encoding(tr: pd.DataFrame, others: list[pd.DataFrame], m: float = 300.0):
    """Adresse du joueur AU-DELA de l'attendu (idee inspiree du xFG / shot-making).

    1. Un modele de qualite de tir (toutes features, sans identite) predit la reussite
       attendue de chaque tir du train, hors echantillon (5 plis par match).
    2. Residu = resultat - attendu. Moyenne lissee par joueur (retrait vers 0 avec m tirs
       fictifs), calculee hors echantillon sur le train, et sur tout le train pour val/test.
    Contrairement a la reussite brute, ce residu ne melange pas talent et selection de tirs.
    """
    fold = ((tr["GAME_ID"].astype(np.int64) * 2654435761 % 4294967296) % 5).to_numpy()
    p_oof = np.empty(len(tr))
    for k in range(5):
        mdl = _HGB(M.FEATURES).fit(tr[fold != k])
        p_oof[fold == k] = mdl.predict(tr[fold == k])
    tr = tr.assign(_res=tr[M.TARGET].to_numpy() - p_oof)
    enc_tr = np.empty(len(tr))
    for k in range(5):
        s = tr[fold != k].groupby("PLAYER_ID")["_res"].agg(["sum", "count"])
        enc = s["sum"] / (s["count"] + m)
        enc_tr[fold == k] = tr.loc[fold == k, "PLAYER_ID"].map(enc).fillna(0.0).to_numpy()
    s = tr.groupby("PLAYER_ID")["_res"].agg(["sum", "count"])
    enc = s["sum"] / (s["count"] + m)
    tr = tr.drop(columns="_res").assign(joueur_residu=enc_tr)
    return tr, [o.assign(joueur_residu=o["PLAYER_ID"].map(enc).fillna(0.0)) for o in others], enc


def run() -> dict:
    t0 = time.time()
    out: dict = {"tailles": {}}
    tr = _load("split = 'train'", N_TRAIN)
    va = _load("split = 'val'", N_VAL)
    va_act = _load("split = 'val' AND joueur_projet", None)
    out["tailles"] = {"train": len(tr), "val": len(va), "val_12_actifs": len(va_act)}

    y = va[M.TARGET].to_numpy()
    out["reference_taux_de_base"] = _metrics(y, np.full(len(y), tr[M.TARGET].mean()))

    lr = Pipeline([("prep", M.build_preprocessor()), ("lr", LogisticRegression(max_iter=1000))])
    lr.fit(tr, tr[M.TARGET])
    out["regression_logistique"] = _metrics(y, lr.predict_proba(va)[:, 1])
    log.info("LR ok (%.0f s)", time.time() - t0)

    # Ablation cumulative
    feats, ablation = [], []
    for name, cols in GROUPS.items():
        feats = feats + cols
        mdl = _HGB(feats).fit(tr)
        met = _metrics(y, mdl.predict(va))
        met.update({"groupe": name, "nb_features": len(feats),
                    "iterations": int(mdl.model.n_iter_)})
        ablation.append(met)
        log.info("ablation %s : AUC %.4f (%.0f s)", name, met["auc"], time.time() - t0)
    out["ablation_hgb"] = ablation
    full = mdl

    # Identite du joueur
    tr_te, (va_te, va_act_te) = _player_target_encoding(tr, [va, va_act])
    mdl_j = _HGB(M.FEATURES + ["joueur_te"]).fit(tr_te)
    out["hgb_avec_identite_joueur"] = _metrics(y, mdl_j.predict(va_te))
    log.info("identite joueur ok (%.0f s)", time.time() - t0)

    # Adresse du joueur au-dela de l'attendu
    tr_r, (va_r, va_act_r), _ = _player_residual_encoding(tr, [va, va_act])
    mdl_r = _HGB(M.FEATURES + ["joueur_residu"]).fit(tr_r)
    out["hgb_avec_adresse_hors_attente"] = _metrics(y, mdl_r.predict(va_r))
    out["calibration_globale_val"] = {"reelle": float(y.mean()),
                                      "predite_hgb": float(full.predict(va).mean())}
    log.info("residu joueur ok (%.0f s)", time.time() - t0)

    # Robustesse temporelle
    tr_t = _load("split_temps = 'train'", N_TRAIN)
    te_t = _load("split_temps = 'test'", N_VAL)
    mdl_t = _HGB(M.FEATURES).fit(tr_t)
    out["hgb_test_temporel"] = _metrics(te_t[M.TARGET].to_numpy(), mdl_t.predict(te_t))
    log.info("temporel ok (%.0f s)", time.time() - t0)

    # Par joueur actif (modele complet, sans identite ; puis avec)
    p = full.predict(va_act)
    pj = mdl_j.predict(va_act_te)
    pr = mdl_r.predict(va_act_r)
    rows = []
    for name, g in va_act.assign(p=p, pj=pj, pr=pr).groupby("PLAYER_NAME"):
        rows.append({"joueur": name, "tirs_val": len(g), "reussite_reelle": g[M.TARGET].mean(),
                     "predite_sans_joueur": g.p.mean(), "predite_identite_brute": g.pj.mean(),
                     "predite_adresse_hors_attente": g.pr.mean(),
                     "auc": roc_auc_score(g[M.TARGET], g.p),
                     "auc_adresse_hors_attente": roc_auc_score(g[M.TARGET], g.pr),
                     "logloss": log_loss(g[M.TARGET], g.p),
                     "logloss_adresse_hors_attente": log_loss(g[M.TARGET], g.pr)})
    out["par_joueur_actif"] = (pd.DataFrame(rows).sort_values("auc", ascending=False)
                               .round(4).to_dict(orient="records"))
    out["duree_s"] = round(time.time() - t0, 1)
    (C.OUTPUT_DIR / "baseline_preview.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "par_joueur_actif"}, indent=1))
    print(pd.DataFrame(r["par_joueur_actif"]).to_string())
