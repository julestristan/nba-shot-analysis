"""Preprocessing elite : mêmes features que nameless, restreint au top 5 NBA 2025 sur 2020-2025.

Le PLAYER_ID sert uniquement à filtrer : il n'est pas utilisé comme feature, pour que le modèle
apprenne le profil de tir "elite" en général et reste comparable à nameless.
Version complète et justifiée du nettoyage : preprocessing.ipynb (à la racine).
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

# /test/elite/preprocessing.py -> parents[2] pointe vers la racine
ROOT_DIR = Path(__file__).resolve().parents[2]

DATA_GLOB = str(ROOT_DIR / "data" / "NBA_202[0-5]_Shots.csv")
TARGET = "SHOT_MADE"
NUM_FEATURES = ["SHOT_DISTANCE", "X_FT", "Y_FT", "ABS_ANGLE", "IS_3PT", "QUARTER", "SECS_LEFT_PERIOD"]
CAT_FEATURES = ["ACTION_TYPE", "BASIC_ZONE"]

# IDs plutôt que noms : l'orthographe change en 2025 (Doncic -> Dončić, Jokic -> Jokić)
ELITE_IDS = {
    1628369: "Jayson Tatum",
    1628983: "Shai Gilgeous-Alexander",
    1629029: "Luka Dončić",
    203507: "Giannis Antetokounmpo",
    203999: "Nikola Jokić",
}
FIRST_SEASON, LAST_SEASON = 2020, 2025

# Position Y du panier dans chaque système de coordonnées (estimée dans preprocessing.ipynb §3)
HOOP_Y_FEET = 5.819   # saisons en pieds (2022-23 et après)
HOOP_Y_SCALED = 5.832  # saisons à l'échelle x0.1 avec axe X inversé (2019-20 -> 2021-22)


def load(pattern=DATA_GLOB):
    df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(pattern))], ignore_index=True)
    return df[df["PLAYER_ID"].isin(ELITE_IDS) & df["SEASON_1"].between(FIRST_SEASON, LAST_SEASON)].copy()


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
    return df[["SEASON_1"] + NUM_FEATURES + CAT_FEATURES + [TARGET]]  # PLAYER_ID volontairement exclu


def split(df):
    """Split par saison : train <= N-2, validation = N-1, test = N (mis de côté)."""
    last = df["SEASON_1"].max()
    return (df[df["SEASON_1"] <= last - 2],
            df[df["SEASON_1"] == last - 1],
            df[df["SEASON_1"] == last])
