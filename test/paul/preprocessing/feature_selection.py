"""Selection de features : quelles features servent vraiment au modele ?

Methode (importance par permutation) : on entraine un gradient boosting sur toutes les
features, puis on melange au hasard une colonne a la fois dans le jeu de validation.
La baisse de l'AUC mesure ce que le modele perd sans cette information. Une feature
dont l'information est deja contenue dans une autre (ex. tir_3pts, deduit de la
distance) a une importance proche de 0 : elle est redondante, pas fausse.

On compare ensuite des modeles entraines sur les k features les plus importantes.

Usage : python -m preprocessing.feature_selection   (2 a 3 minutes)
Sortie : test/paul/resultats/feature_selection.json
"""

from __future__ import annotations

import json
import logging

import numpy as np
from sklearn.metrics import log_loss, roc_auc_score

from . import baseline_preview as B
from . import config as C
from . import model_features as M

log = logging.getLogger(__name__)
N_TRAIN, N_VAL, N_REPEATS = 400_000, 150_000, 2
SUBSETS = (12, 6, 2)


def run() -> dict:
    tr = B._load("split = 'train'", N_TRAIN)
    va = B._load("split = 'val'", N_VAL)
    y = va[M.TARGET].to_numpy()
    mdl = B._HGB(M.FEATURES).fit(tr)
    base = roc_auc_score(y, mdl.predict(va))
    rng = np.random.default_rng(C.SPLIT_SEED)
    imp = {}
    for f in M.FEATURES:
        drops = []
        for _ in range(N_REPEATS):
            v = va.copy()
            v[f] = rng.permutation(v[f].to_numpy())
            drops.append(base - roc_auc_score(y, mdl.predict(v)))
        imp[f] = float(np.mean(drops))
    ranking = sorted(imp, key=imp.get, reverse=True)
    log.info("importance calculee")

    subsets = [{"k": len(M.FEATURES), "auc": float(base),
                "log_loss": float(log_loss(y, mdl.predict(va))), "features": M.FEATURES}]
    for k in SUBSETS:
        p = B._HGB(ranking[:k]).fit(tr).predict(va)
        subsets.append({"k": k, "auc": float(roc_auc_score(y, p)),
                        "log_loss": float(log_loss(y, p)), "features": ranking[:k]})
    out = {"auc_reference": float(base), "importance": {f: imp[f] for f in ranking},
           "sous_ensembles": subsets,
           "features_retenues_identiques_a_config": set(ranking[:12]) == set(M.FEATURES_RETENUES)}
    (C.OUTPUT_DIR / "feature_selection.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    r = run()
    for s in r["sous_ensembles"]:
        print(s["k"], "features : AUC", round(s["auc"], 4))
    print("memes 12 features que config :", r["features_retenues_identiques_a_config"])
