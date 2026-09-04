"""Extraction des tirs (ShotChartDetail) pour les 20 joueurs du périmètre.

Un fichier parquet par (joueur, saison, type de saison) dans data/raw/, puis une
concaténation dans data/interim/shots_top20.parquet.

Usage (depuis la racine du repo) :

    python -m src.api.fetch_shots                      # tout le périmètre
    python -m src.api.fetch_shots --players "Stephen Curry" "LeBron James"
    python -m src.api.fetch_shots --first-season 2013  # ère tracking uniquement
    python -m src.api.fetch_shots --dry-run            # affiche le plan d'appels

Le script est idempotent : relancé, il saute ce qui existe déjà.
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
from nba_api.stats.endpoints import ShotChartDetail

from . import config
from .client import call_endpoint
from .players import played_seasons, resolve_player_id

logger = logging.getLogger(__name__)

# Colonnes finalement conservées (ShotChartDetail en renvoie 24).
KEEP = [
    "GAME_ID", "GAME_EVENT_ID", "GAME_DATE", "PLAYER_ID", "PLAYER_NAME",
    "TEAM_ID", "TEAM_NAME", "PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING",
    "ACTION_TYPE", "SHOT_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA",
    "SHOT_ZONE_RANGE", "SHOT_DISTANCE", "LOC_X", "LOC_Y",
    "SHOT_ATTEMPTED_FLAG", "SHOT_MADE_FLAG", "HTM", "VTM",
]


def _out_path(player_id: int, season: str, season_type: str):
    tag = "reg" if season_type == "Regular Season" else "po"
    return config.RAW_DIR / f"shots_{player_id}_{season}_{tag}.parquet"


def fetch_one(player_id: int, season: str, season_type: str) -> pd.DataFrame:
    """Tous les tirs TENTÉS d'un joueur sur une saison.

    `context_measure_simple="FGA"` est indispensable : la valeur par défaut
    ("PTS") ne renvoie que les tirs RÉUSSIS, ce qui rendrait la cible
    SHOT_MADE_FLAG constante à 1. C'est le piège classique de cet endpoint.
    `team_id=0` signifie « toutes les équipes » (utile pour les joueurs transférés).
    """
    df = call_endpoint(
        ShotChartDetail,
        dataset="Shot_Chart_Detail",
        team_id=0,
        player_id=player_id,
        season_nullable=season,
        season_type_all_star=season_type,
        context_measure_simple="FGA",
    )
    if df.empty:
        return df
    df = df[[c for c in KEEP if c in df.columns]].copy()
    df["SEASON"] = season
    df["SEASON_TYPE"] = season_type
    return df


def run(players: list[str], first_season: int, season_types: list[str], dry_run: bool) -> None:
    frames: list[pd.DataFrame] = []
    planned = 0

    for name in players:
        pid = resolve_player_id(name)
        seasons = [s for s in played_seasons(pid) if int(s[:4]) >= first_season]
        logger.info("%s (id=%s) : %d saisons dans le périmètre", name, pid, len(seasons))

        for season in seasons:
            for st in season_types:
                out = _out_path(pid, season, st)
                planned += 1
                if dry_run:
                    continue
                if out.exists():
                    frames.append(pd.read_parquet(out))
                    continue
                df = fetch_one(pid, season, st)
                if df.empty:
                    logger.info("  %s %s %s : aucun tir", name, season, st)
                    continue
                df.to_parquet(out, index=False)
                frames.append(df)
                logger.info("  %s %s %s : %d tirs", name, season, st, len(df))

    if dry_run:
        est_min = planned * (config.REQUEST_DELAY_S + config.REQUEST_JITTER_S / 2) / 60
        logger.info("DRY RUN : %d appels ShotChartDetail, ~%.0f min", planned, est_min)
        return

    if not frames:
        logger.warning("Aucune donnée récupérée.")
        return

    full = pd.concat(frames, ignore_index=True)
    dest = config.INTERIM_DIR / "shots_top20.parquet"
    full.to_parquet(dest, index=False)
    logger.info("Écrit %s : %d lignes, %d joueurs", dest, len(full), full["PLAYER_ID"].nunique())


def main() -> None:
    p = argparse.ArgumentParser(description="Extraction ShotChartDetail (stats.nba.com)")
    p.add_argument("--players", nargs="*", default=config.PLAYERS_20)
    p.add_argument("--first-season", type=int, default=config.FIRST_SHOTCHART_SEASON)
    p.add_argument("--playoffs", action="store_true", help="inclure aussi les playoffs")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    season_types = ["Regular Season"] + (["Playoffs"] if args.playoffs else [])
    run(args.players, args.first_season, season_types, args.dry_run)


if __name__ == "__main__":
    main()
