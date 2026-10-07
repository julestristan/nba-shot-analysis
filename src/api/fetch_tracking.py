"""Extraction des splits de tracking (PlayerDashPtShots), à partir de 2013-14.

⚠️ Point clé pour le projet : ces données NE SONT PAS au niveau du tir.
L'API expose des AGRÉGATS par joueur × saison × modalité :
  - `closest_defender`   : distance du défenseur le plus proche (0-2ft, 2-4ft, 4-6ft, 6+ft)
  - `dribble_shooting`   : nombre de dribbles avant le tir (0, 1, 2, 3-6, 7+)
  - `touch_time_shooting`: temps de possession du ballon avant le tir (<2s, 2-6s, 6+s)
  - `shot_clock_shooting`: temps restant à l'horloge des 24 s
  - `general_shooting`   / `catch_shoot_shooting`

Conséquence : on ne peut pas rattacher une pression défensive à CHAQUE tir. Ces
tables servent (a) à quantifier le biais d'omission décrit dans le sujet,
(b) à construire des features de contexte au niveau joueur-saison
(ex. « part des tirs contestés »), à manier avec précaution pour éviter la fuite
de données (elles sont calculées a posteriori sur la saison).

Usage :
    python -m src.api.fetch_tracking
    python -m src.api.fetch_tracking --dataset closest_defender
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd
from nba_api.stats.endpoints import PlayerDashPtShots

from . import config
from .client import call_endpoint
from .players import played_seasons, resolve_player_id

logger = logging.getLogger(__name__)

# alias lisible -> nom exact du resultSet renvoyé par PlayerDashPtShots
DATASETS = {
    "overall": "Overall",
    "general_shooting": "GeneralShooting",
    "shot_clock_shooting": "ShotClockShooting",
    "dribble_shooting": "DribbleShooting",
    "closest_defender": "ClosestDefenderShooting",
    "closest_defender_10ft_plus": "ClosestDefender10ftPlusShooting",
    "touch_time_shooting": "TouchTimeShooting",
}


def run(dataset: str, players: list[str]) -> None:
    rs_name = DATASETS[dataset]
    frames: list[pd.DataFrame] = []

    for name in players:
        pid = resolve_player_id(name)
        seasons = [s for s in played_seasons(pid) if int(s[:4]) >= config.FIRST_TRACKING_SEASON]
        if not seasons:
            logger.info("%s : aucune saison à l'ère tracking (>= 2013-14)", name)
            continue

        for season in seasons:
            df = call_endpoint(
                PlayerDashPtShots,
                dataset=rs_name,
                team_id=0,
                player_id=pid,
                season=season,
                season_type_all_star="Regular Season",
                per_mode_simple="Totals",
            )
            if df.empty:
                continue
            df["PLAYER_ID"] = pid
            df["PLAYER_NAME"] = name
            df["SEASON"] = season
            frames.append(df)
            logger.info("  %s %s : %d lignes", name, season, len(df))

    if not frames:
        logger.warning("Aucune donnée récupérée.")
        return

    full = pd.concat(frames, ignore_index=True)
    dest = config.INTERIM_DIR / f"tracking_{dataset}_top20.parquet"
    full.to_parquet(dest, index=False)
    logger.info("Écrit %s : %d lignes", dest, len(full))


def main() -> None:
    p = argparse.ArgumentParser(description="Extraction PlayerDashPtShots (tracking, 2013-14+)")
    p.add_argument("--dataset", choices=sorted(DATASETS), default="closest_defender")
    p.add_argument("--players", nargs="*", default=config.PLAYERS_20)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    run(args.dataset, args.players)


if __name__ == "__main__":
    main()
