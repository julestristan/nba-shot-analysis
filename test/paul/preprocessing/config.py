"""Configuration de la preparation des donnees.

Une seule source de verite pour : chemins, perimetre joueurs, seuils et constantes
du terrain. Les autres modules n'ont aucune valeur en dur.

Convention de saison : SEASON_1 est l'annee de FIN de saison (2011 = saison 2010-11).
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Chemins (tout ce qui est volumineux reste dans data/interim/, ignore par Git)
# --------------------------------------------------------------------------
# test/paul/preprocessing/config.py -> parents[1] = test/paul, parents[3] = racine du repo
PAUL_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
RAW_CSV_GLOB = str(ROOT / "data" / "raw" / "shots_csv" / "NBA_*_Shots.csv")
INTERIM_DIR = ROOT / "data" / "interim"          # gros fichiers, ignores par Git
OUTPUT_DIR = PAUL_DIR / "resultats"              # comptes, controles, resultats de modeles
FIG_DIR = PAUL_DIR / "figures"

# Surchargeables par variables d'environnement (utile pour un environnement a faible memoire).
DB_PATH = Path(os.environ.get("NBA_DB_PATH", INTERIM_DIR / "preprocessing.duckdb"))
TMP_DIR = Path(os.environ.get("NBA_TMP_DIR", INTERIM_DIR / "duckdb_tmp"))
SHOTS_CLEAN_PATH = INTERIM_DIR / "shots_clean.parquet"   # toutes saisons, nettoye
SHOTS_MODEL_PATH = INTERIM_DIR / "shots_model.parquet"   # saisons fiables, pret ML
AUDIT_PATH = OUTPUT_DIR / "preprocessing_audit.json"

for _d in (INTERIM_DIR, TMP_DIR, OUTPUT_DIR, FIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Limites de ressources DuckDB (le Docker de Paul est regle a 6 Go).
DUCKDB_MEMORY_LIMIT = os.environ.get("DUCKDB_MEMORY_LIMIT", "3GB")
DUCKDB_THREADS = int(os.environ.get("DUCKDB_THREADS", "4"))

# --------------------------------------------------------------------------
# Terrain (pieds). Dans les CSV, LOC_Y part de la ligne de fond : le panier est a 5.25.
# --------------------------------------------------------------------------
BASKET_Y = 5.25
COURT_HALF_LENGTH = 47.0
CORNER_THREE_FT = 22.0        # ligne a 3 points dans les coins
ARC_THREE_FT = 23.75          # ligne a 3 points a l'arc

# --------------------------------------------------------------------------
# Perimetre temporel : les 10 dernieres saisons
# --------------------------------------------------------------------------
# SEASON_1 >= 2016, soit 2015-16 a 2024-25. Raisons : jeu homogene (ere du tir a
# 3 points) et coordonnees toutes fiables.
FIRST_SEASON = 2016
# Rupture de collecte des coordonnees : avant 2010-11, les tirs au cercle sont
# ramenes au point du panier. Hors de la fenetre, garde pour documenter le choix.
COORD_FIABLE_FROM_SEASON = 2011
FIRST_SEASON_IN_DATA = 2004              # le CSV commence en 2003-04 : experience censuree

# Une saison est consideree comme "a echelle corrompue" si l'ecart moyen entre
# SHOT_DISTANCE declaree et distance recalculee depasse ce seuil (en pieds).
# Valeur normale : ~0.5 ft (SHOT_DISTANCE est le plancher de la distance).
SCALE_MAE_THRESHOLD_FT = 3.0
SCALE_MAE_OK_FT = 1.0                    # apres correction, on exige moins que ca

# --------------------------------------------------------------------------
# Perimetre joueurs : selection par regle, pas a la main
# --------------------------------------------------------------------------
# Classement ESPN des 25 meilleurs joueurs du 21e siecle (juillet 2024), dans l'ordre.
ESPN_TOP_25 = [
    "LeBron James", "Kobe Bryant", "Stephen Curry", "Tim Duncan", "Shaquille O'Neal",
    "Kevin Garnett", "Nikola Jokic", "Dwyane Wade", "Kevin Durant", "Dirk Nowitzki",
    "Giannis Antetokounmpo", "Steve Nash", "James Harden", "Jason Kidd", "Chris Paul",
    "Kawhi Leonard", "Manu Ginobili", "Allen Iverson", "Anthony Davis", "Ray Allen",
    "Tony Parker", "Draymond Green", "Russell Westbrook", "Pau Gasol", "Luka Doncic",
]
# Un joueur fait partie du projet s'il est dans ce classement ET, sur la fenetre :
LAST_SEASON_IN_DATA = 2025      # actif : il a tire pendant la derniere saison (2024-25)
MIN_SEASONS = 5                 # au moins 5 saisons d'anciennete
MIN_SHOTS = 5000                # assez de tirs pour evaluer un modele joueur par joueur

# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------
END_OF_PERIOD_SECONDS = 3        # fin_de_periode : 3 dernieres secondes du quart-temps
REST_DAYS_CAP = 7                # au-dela, jours_repos est plafonne (pause, all-star break)
SEQ_WINDOW = 3                   # nombre de tirs precedents pour reussite_tirs_precedents

# Decoupage apprentissage / validation / test
SPLIT_SEED = 42
SPLIT_FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}   # par match (GAME_ID)
# split_temps : train 2015-16 a 2022-23,
# validation 2023-24, test 2024-25.
TEMPORAL_TRAIN_MAX_SEASON = 2023
TEMPORAL_VAL_SEASON = 2024

TARGET = "cible"
