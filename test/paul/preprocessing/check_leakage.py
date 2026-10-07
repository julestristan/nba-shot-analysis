"""Detecteur de fuite de donnees sur shots_model.parquet.

Principe : un tir NBA est intrinsequement incertain (plafond realiste d'AUC ~0.65-0.70).
Si une variable seule, ou un modele tres simple, depasse nettement ce plafond, c'est
qu'une information sur le resultat s'est glissee dans les features.

Trois controles :
  1. AUC univariee de chaque feature (categorielles : encodage par la moyenne appris
     sur le train, evalue sur la validation).
  2. Regression logistique a 3 variables (distance, angle, fin de periode) : modele
     jetable, doit rester modeste.
  3. Regression logistique sur toutes les features, split par match puis split temporel.

Usage : python -m preprocessing.check_leakage
"""

from __future__ import annotations

import json
import logging

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from . import config as C
from . import model_features as M

log = logging.getLogger(__name__)

AUC_ALERTE = 0.80        # au-dela, on suspecte une fuite
N_TRAIN = 400_000        # echantillon d'apprentissage (suffisant pour un controle)
N_EVAL = 200_000


def _load(where: str, n: int) -> pd.DataFrame:
    cols = ", ".join(M.FEATURES + [M.TARGET, "split", "split_temps"])
    # Le filtre doit etre applique AVANT l'echantillonnage (sous-requete) : dans DuckDB,
    # USING SAMPLE porte sur la table du FROM, pas sur le resultat du WHERE.
    return duckdb.sql(f"""
        SELECT * FROM (SELECT {cols} FROM read_parquet('{C.SHOTS_MODEL_PATH}') WHERE {where})
        USING SAMPLE reservoir({n} ROWS) REPEATABLE ({C.SPLIT_SEED})
    """).df()


def _univariate(train: pd.DataFrame, val: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = val[M.TARGET].to_numpy()
    for c in M.NUMERIC + M.BINARY:
        x = val[c].astype(float).fillna(train[c].astype(float).median()).to_numpy()
        auc = roc_auc_score(y, x)
        rows.append((c, "numerique" if c in M.NUMERIC else "binaire", max(auc, 1 - auc)))
    for c in M.CATEGORICAL:
        means = train.groupby(c)[M.TARGET].mean()
        x = val[c].map(means).fillna(train[M.TARGET].mean()).to_numpy()
        rows.append((c, "categorielle", roc_auc_score(y, x)))
    return (pd.DataFrame(rows, columns=["feature", "type", "auc"])
              .sort_values("auc", ascending=False).reset_index(drop=True))


def _fit_eval(train: pd.DataFrame, test: pd.DataFrame, numeric, binary, categorical) -> float:
    pipe = Pipeline([
        ("prep", M.build_preprocessor(numeric, binary, categorical)),
        ("lr", LogisticRegression(max_iter=1000)),
    ])
    pipe.fit(train, train[M.TARGET])
    return roc_auc_score(test[M.TARGET], pipe.predict_proba(test)[:, 1])


def run() -> dict:
    tr = _load("split = 'train'", N_TRAIN)
    va = _load("split = 'val'", N_EVAL)
    uni = _univariate(tr, va)
    out = {"univariee": uni.round(4).to_dict(orient="records")}

    out["lr3_auc_val"] = _fit_eval(tr, va, ["distance_ft", "angle_deg"], ["fin_de_periode"], [])
    out["lr_complete_auc_val"] = _fit_eval(tr, va, M.NUMERIC, M.BINARY, M.CATEGORICAL)

    tr_t = _load("split_temps = 'train'", N_TRAIN)
    te_t = _load("split_temps = 'test'", N_EVAL)
    out["lr_complete_auc_test_temporel"] = _fit_eval(tr_t, te_t, M.NUMERIC, M.BINARY,
                                                     M.CATEGORICAL)
    out["taux_base_val"] = float(va[M.TARGET].mean())
    out["tailles_echantillons"] = {"train": len(tr), "val": len(va),
                                   "train_temporel": len(tr_t), "test_temporel": len(te_t)}
    suspects = uni.loc[uni["auc"] > AUC_ALERTE, "feature"].tolist()
    out["features_suspectes"] = suspects
    out["verdict"] = ("ALERTE : fuite probable" if suspects or out["lr3_auc_val"] > AUC_ALERTE
                      else "aucune fuite detectee")

    (C.OUTPUT_DIR / "leakage_check.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    res = run()
    print(pd.DataFrame(res["univariee"]).to_string())
    for k in ("lr3_auc_val", "lr_complete_auc_val", "lr_complete_auc_test_temporel",
              "taux_base_val", "features_suspectes", "verdict"):
        print(k, res[k])
