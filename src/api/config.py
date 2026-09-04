"""Configuration partagée du module d'extraction API.

Une seule source de vérité pour : la liste des joueurs, les saisons couvertes,
les chemins de cache et les paramètres de politesse réseau.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------
# src/api/config.py -> src/api -> src -> racine du repo
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # 1 fichier parquet par (joueur, saison)
INTERIM_DIR = DATA_DIR / "interim"  # concaténations
CACHE_DIR = DATA_DIR / ".api_cache"  # réponses brutes JSON (debug / reproductibilité)

for _d in (RAW_DIR, INTERIM_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Périmètre joueurs
# --------------------------------------------------------------------------
# Top 25 ESPN des joueurs du 21e siecle (publication ESPN, juillet 2024).
# Le sujet demande "20 des meilleurs joueurs du 21e siecle (selon ESPN)" :
# on retient les 20 premiers, et on garde les rangs 21-25 en reserve pour
# d'eventuels tests de robustesse. A VALIDER avec le mentor (cf. docs/api_scouting.md).
ESPN_TOP_25 = [
    "LeBron James",
    "Kobe Bryant",
    "Stephen Curry",
    "Tim Duncan",
    "Shaquille O'Neal",
    "Kevin Garnett",
    "Nikola Jokic",
    "Dwyane Wade",
    "Kevin Durant",
    "Dirk Nowitzki",
    "Giannis Antetokounmpo",
    "Steve Nash",
    "James Harden",
    "Jason Kidd",
    "Chris Paul",
    "Kawhi Leonard",
    "Manu Ginobili",
    "Allen Iverson",
    "Anthony Davis",
    "Ray Allen",
    # --- reserve ---
    "Tony Parker",
    "Draymond Green",
    "Russell Westbrook",
    "Pau Gasol",
    "Luka Doncic",
]

PLAYERS_20 = ESPN_TOP_25[:20]

# --------------------------------------------------------------------------
# Périmètre temporel
# --------------------------------------------------------------------------
# stats.nba.com expose les coordonnees de tir a partir de 1996-97.
FIRST_SHOTCHART_SEASON = 1996
# Le tracking SportVU / Second Spectrum (defenseur le plus proche, touch time,
# nombre de dribbles) n'existe qu'a partir de 2013-14. C'est LA rupture a
# connaitre pour le projet.
FIRST_TRACKING_SEASON = 2013
LAST_SEASON = 2025  # saison 2025-26, derniere saison complete a date

SEASON_TYPES = ["Regular Season", "Playoffs"]


def season_str(start_year: int) -> str:
    """1996 -> '1996-97', 2025 -> '2025-26'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def seasons(first: int = FIRST_SHOTCHART_SEASON, last: int = LAST_SEASON) -> list[str]:
    return [season_str(y) for y in range(first, last + 1)]


# --------------------------------------------------------------------------
# Politesse réseau
# --------------------------------------------------------------------------
# stats.nba.com n'a pas de quota documenté mais coupe (timeouts, 429) au-delà
# d'environ 1 requête/seconde soutenue. On reste volontairement en dessous.
REQUEST_DELAY_S = 1.2      # pause de base entre deux requêtes
REQUEST_JITTER_S = 0.6     # bruit aléatoire ajouté à la pause
REQUEST_TIMEOUT_S = 60     # timeout HTTP par requête
MAX_RETRIES = 5            # nombre de tentatives avant abandon
BACKOFF_BASE_S = 4         # backoff exponentiel : 4s, 8s, 16s, 32s, 64s
