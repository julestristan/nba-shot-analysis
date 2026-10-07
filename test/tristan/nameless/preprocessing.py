"""Preprocessing léger : chargement, nettoyage minimal, quelques features, split temporel.

Version complète et justifiée : preprocessing.ipynb (à la racine).
"""
import glob

import numpy as np
import pandas as pd
from pathlib import Path

if "__file__" in globals():
    # Si exécuté en tant que script Python (.py)
    # /test/nameless/preprocessing.py -> parents[2] pointe vers la racine
    ROOT_DIR = Path(__file__).resolve().parents[2]
else:
    # Si appelé via Jupyter ou un contexte interactif
    # On remonte à partir de l'emplacement du fichier preprocessing.py
    ROOT_DIR = Path(__file__ if "__file__" in locals() else ".").resolve()
    # On recherche le dossier contenant le répertoire 'data' en remontant les parents
    for parent in [ROOT_DIR] + list(ROOT_DIR.parents):
        if (parent / "data").exists():
            ROOT_DIR = parent
            break

# Remplace "data/*.csv" par le dossier exact où se trouvent tes CSV
DATA_GLOB = str(ROOT_DIR / "data" / "*.csv")
TARGET = "SHOT_MADE"
NUM_FEATURES = ["SHOT_DISTANCE", "X_FT", "Y_FT", "ABS_ANGLE", "IS_3PT", "QUARTER", "SECS_LEFT_PERIOD"]
CAT_FEATURES = ["ACTION_TYPE", "BASIC_ZONE"]

# Position Y du panier dans chaque système de coordonnées (estimée dans preprocessing.ipynb §3)
HOOP_Y_FEET = 5.819   # saisons en pieds (2022-23 et après)
HOOP_Y_SCALED = 5.832  # saisons à l'échelle x0.1 avec axe X inversé (2019-20 -> 2021-22)


def load(pattern=DATA_GLOB):
    return pd.concat([pd.read_csv(f) for f in sorted(glob.glob(pattern))], ignore_index=True)


def fix_coordinates(df):
    """Ramène toutes les saisons dans un repère commun en pieds, centré sur le panier."""
    corner = df[df["BASIC_ZONE"].str.contains("Corner 3")]
    scaled = corner.groupby("SEASON_1")["LOC_X"].apply(lambda s: s.abs().median() < 5)
    is_scaled = df["SEASON_1"].map(scaled)

    df["X_FT"] = np.where(is_scaled, -10 * df["LOC_X"], df["LOC_X"])
    df["Y_FT"] = np.where(is_scaled, 10 * (df["LOC_Y"] - HOOP_Y_SCALED), df["LOC_Y"] - HOOP_Y_FEET)
    return df


def build(df):
    df = df.drop_duplicates().drop(columns=["EVENT_TYPE"])  # EVENT_TYPE = cible en texte (fuite)
    df = fix_coordinates(df)

    df["ABS_ANGLE"] = np.degrees(np.arctan2(df["X_FT"], df["Y_FT"])).abs()
    df["IS_3PT"] = (df["SHOT_TYPE"] == "3PT Field Goal").astype(int)
    df["SECS_LEFT_PERIOD"] = df["MINS_LEFT"] * 60 + df["SECS_LEFT"]
    df[TARGET] = df[TARGET].astype(int)
    return df[["SEASON_1"] + NUM_FEATURES + CAT_FEATURES + [TARGET]]


def split(df):
    """Split par saison : train <= N-2, validation = N-1, test = N (mis de côté)."""
    last = df["SEASON_1"].max()
    return (df[df["SEASON_1"] <= last - 2],
            df[df["SEASON_1"] == last - 1],
            df[df["SEASON_1"] == last])
