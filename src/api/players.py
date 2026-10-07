"""Résolution des joueurs : nom -> player_id, et saisons réellement jouées.

Deux intérêts :
  * fiabiliser le join avec les datasets Kaggle (qui utilisent les mêmes PLAYER_ID
    NBA que l'API, ce qui en fait la clé de raccordement naturelle) ;
  * éviter des milliers de requêtes inutiles : on n'interroge une saison que si
    le joueur l'a effectivement jouée.
"""

from __future__ import annotations

import logging

import pandas as pd
from nba_api.stats.endpoints import PlayerCareerStats
from nba_api.stats.static import players as static_players

from . import config
from .client import call_endpoint

logger = logging.getLogger(__name__)

# Homonymes / graphies à trancher explicitement (player_id officiel NBA).
MANUAL_IDS: dict[str, int] = {
    "Nikola Jokic": 203999,
    "Giannis Antetokounmpo": 203507,
    "Luka Doncic": 1629029,
}


def resolve_player_id(full_name: str) -> int:
    if full_name in MANUAL_IDS:
        return MANUAL_IDS[full_name]
    matches = static_players.find_players_by_full_name(full_name)
    if not matches:
        raise ValueError(f"Joueur introuvable dans le référentiel nba_api : {full_name!r}")
    if len(matches) > 1:
        logger.warning(
            "%s : %d correspondances, on prend %s (id=%s). Ajoutez-le à MANUAL_IDS si c'est faux.",
            full_name, len(matches), matches[0]["full_name"], matches[0]["id"],
        )
    return int(matches[0]["id"])


def roster() -> pd.DataFrame:
    """DataFrame des 20 joueurs du périmètre : rang ESPN, nom, player_id."""
    rows = [
        {"espn_rank": i + 1, "player_name": name, "player_id": resolve_player_id(name)}
        for i, name in enumerate(config.PLAYERS_20)
    ]
    return pd.DataFrame(rows)


def played_seasons(player_id: int) -> list[str]:
    """Saisons de saison régulière effectivement jouées, format '2015-16'."""
    df = call_endpoint(
        PlayerCareerStats,
        dataset="SeasonTotalsRegularSeason",
        player_id=player_id,
    )
    if df.empty:
        return []
    seasons = sorted(set(df["SEASON_ID"].astype(str)))
    first = config.FIRST_SHOTCHART_SEASON
    last = config.LAST_SEASON
    return [s for s in seasons if first <= int(s[:4]) <= last]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    r = roster()
    print(r.to_string(index=False))
