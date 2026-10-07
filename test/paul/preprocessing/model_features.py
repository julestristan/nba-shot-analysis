"""Colonnes du dataset de modelisation et constructeur de pre-processeur scikit-learn.

Le dataset `shots_model.parquet` contient : identifiants, flags de perimetre,
features, decoupages, et la cible `cible` (1 = tir reussi).
Les transformations d'encodage (one-hot, imputation, mise a l'echelle) ne sont PAS
appliquees dans le parquet : elles s'apprennent sur le train uniquement, dans un
Pipeline scikit-learn (build_preprocessor), pour eviter toute fuite vers val/test.
"""

from __future__ import annotations

TARGET = "cible"

ID_COLUMNS = ["GAME_ID", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "SEASON_1", "GAME_DATE"]
FLAG_COLUMNS = ["joueur_projet", "espn_top25", "actif_2024_25", "coord_corrigee",
                "split", "split_temps"]

NUMERIC = [
    "distance_ft", "angle_deg", "LOC_X", "LOC_Y",
    "temps_restant_periode_s", "temps_ecoule_match_s", "QUARTER",
    "tirs_deja_pris", "reussite_tirs_precedents",
    "jours_repos", "saisons_depuis_premiere_apparition",
]
BINARY = [
    "domicile", "fin_de_periode", "derniere_minute", "prolongation", "tir_3pts", "tir_planche",
    "en_course", "en_desequilibre", "alley_oop",
    "tir_backcourt", "premier_tir_match", "back_to_back", "premier_match_saison",
    "experience_censuree",
]
CATEGORICAL = [
    "geste_famille", "ACTION_TYPE", "BASIC_ZONE", "POSITION_GROUP", "POSITION",
    "equipe", "adversaire",
]

FEATURES = NUMERIC + BINARY + CATEGORICAL

# Les 12 features retenues pour le modele, par ordre d'importance (feature_selection.py).
# Avec elles seules, le gradient boosting obtient la meme AUC qu'avec les 32 (0,670).
# Les 20 autres restent dans le dataset : elles servent a l'analyse par situation de jeu
# (objectif 1) et a l'interpretation, mais n'ajoutent rien a la prediction.
FEATURES_RETENUES = [
    "ACTION_TYPE", "distance_ft", "reussite_tirs_precedents", "tirs_deja_pris", "equipe",
    "BASIC_ZONE", "adversaire", "POSITION", "saisons_depuis_premiere_apparition",
    "temps_restant_periode_s", "angle_deg", "LOC_Y",
]
MODEL_COLUMNS = ID_COLUMNS + FLAG_COLUMNS + FEATURES + [TARGET]


def build_preprocessor(numeric=None, binary=None, categorical=None, scale=True):
    """ColumnTransformer : imputation mediane (+ indicateur de NaN), echelle, one-hot.

    A ajuster sur le train uniquement (`fit`), puis appliquer a val/test (`transform`).
    Les categories rares (< 100 tirs) sont regroupees. Pour les modeles a base d'arbres,
    passer scale=False.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric = NUMERIC if numeric is None else numeric
    binary = BINARY if binary is None else binary
    categorical = CATEGORICAL if categorical is None else categorical

    num_steps = [("imp", SimpleImputer(strategy="median", add_indicator=True))]
    if scale:
        num_steps.append(("sc", StandardScaler()))
    return ColumnTransformer(
        [
            ("num", Pipeline(num_steps), numeric),
            ("bin", "passthrough", binary),
            ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=100,
                                  sparse_output=True), categorical),
        ],
        remainder="drop",
    )
