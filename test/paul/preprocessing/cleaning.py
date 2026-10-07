"""Etape 2.1 : chargement et nettoyage des 22 CSV de tirs (2003-04 a 2024-25).

Chaque fonction lit/ecrit des tables DuckDB et renseigne le dictionnaire `audit`
(comptes avant/apres) qui alimente le rapport. Aucune valeur n'est ecrite en dur :
tout vient de config.py.

Ordre des etapes :
    load_raw -> build_base -> fix_coordinate_scale -> dedupe ->
    drop_incoherent -> impute_position -> (table `clean`)
"""

from __future__ import annotations

import logging

import duckdb

from . import config as C

log = logging.getLogger(__name__)

BASKET_Y = C.BASKET_Y
# Un doublon exact de tip / putback / follow-up est physiquement plausible (deux
# tentatives dans la meme seconde, au meme endroit) : on le conserve, en le marquant.
TIP_FAMILY = (
    "(ACTION_TYPE ILIKE '%tip%' OR ACTION_TYPE ILIKE '%putback%' "
    "OR ACTION_TYPE ILIKE '%follow up%')"
)
DIST_SQL = f"sqrt(LOC_X * LOC_X + (LOC_Y - {BASKET_Y}) * (LOC_Y - {BASKET_Y}))"


def _n(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]


# --------------------------------------------------------------------------
def load_raw(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Lit les 22 CSV saisonniers en une seule table `raw`."""
    con.execute(f"""
        CREATE OR REPLACE TABLE raw AS
        SELECT row_number() OVER () AS rid, *
        FROM read_csv('{C.RAW_CSV_GLOB}', header = true, union_by_name = true,
                      sample_size = -1)
    """)
    audit["lignes_brutes"] = _n(con, "raw")
    audit["saisons_brutes"] = con.sql("SELECT count(DISTINCT SEASON_1) FROM raw").fetchone()[0]
    audit["joueurs_bruts"] = con.sql("SELECT count(DISTINCT PLAYER_ID) FROM raw").fetchone()[0]
    # EVENT_TYPE est la cible sous forme de texte : a exclure absolument des features.
    audit["event_type_different_de_cible"] = con.sql(
        "SELECT count(*) FROM raw WHERE (EVENT_TYPE = 'Made Shot') <> SHOT_MADE"
    ).fetchone()[0]
    log.info("raw : %s lignes", f"{audit['lignes_brutes']:,}")


# --------------------------------------------------------------------------
def build_base(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Typage, renommage de la cible, retrait des lignes sans tir, suppression d'EVENT_TYPE."""
    audit["joueurs_avec_plusieurs_graphies"] = con.sql(
        "SELECT count(*) FROM (SELECT PLAYER_ID FROM raw GROUP BY 1 "
        "HAVING count(DISTINCT PLAYER_NAME) > 1)"
    ).fetchone()[0]
    audit["lignes_hors_fenetre"] = con.sql(
        f"SELECT count(*) FROM raw WHERE SEASON_1 < {C.FIRST_SEASON}").fetchone()[0]
    audit["lignes_no_shot"] = con.sql(
        f"SELECT count(*) FROM raw WHERE ACTION_TYPE = 'No Shot' AND SEASON_1 >= {C.FIRST_SEASON}"
    ).fetchone()[0]
    con.execute(f"""
        CREATE OR REPLACE TABLE base AS
        SELECT rid, SEASON_1, SEASON_2, TEAM_ID, TEAM_NAME, PLAYER_ID,
               strip_accents(PLAYER_NAME)                      AS PLAYER_NAME,
               POSITION_GROUP, POSITION,
               min(strptime(GAME_DATE, '%m-%d-%Y')::DATE) OVER (PARTITION BY GAME_ID)
                                                               AS GAME_DATE,
               GAME_ID, HOME_TEAM, AWAY_TEAM,
               SHOT_MADE::INTEGER                              AS cible,
               ACTION_TYPE, SHOT_TYPE, BASIC_ZONE, ZONE_NAME, ZONE_ABB, ZONE_RANGE,
               LOC_X, LOC_Y, SHOT_DISTANCE, QUARTER, MINS_LEFT, SECS_LEFT
        FROM raw
        WHERE ACTION_TYPE <> 'No Shot' AND SEASON_1 >= {C.FIRST_SEASON}
    """)
    audit["lignes_apres_base"] = _n(con, "base")
    audit["matchs_avec_2_dates"] = con.sql(
        "SELECT count(*) FROM (SELECT GAME_ID FROM raw GROUP BY 1 "
        "HAVING count(DISTINCT GAME_DATE) > 1)"
    ).fetchone()[0]
    audit["matchs_sans_2_equipes"] = con.sql(
        "SELECT count(*) FROM (SELECT GAME_ID FROM raw GROUP BY 1 "
        "HAVING count(DISTINCT TEAM_ID) <> 2)"
    ).fetchone()[0]


# --------------------------------------------------------------------------
def fix_coordinate_scale(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Detecte et corrige les saisons dont LOC_X / LOC_Y sont a la mauvaise echelle.

    Constat (saisons 2019-20 a 2021-22) : LOC_X est divise par 10 ET de signe inverse
    (le corner gauche a un X negatif, contre positif les autres saisons), et LOC_Y vaut
    5.25 + y_reel / 10, alors que SHOT_DISTANCE reste correcte. La detection est
    pilotee par les donnees : une saison est corrompue si l'ecart moyen entre
    SHOT_DISTANCE et la distance recalculee depasse SCALE_MAE_THRESHOLD_FT.
    Correction : x = -LOC_X * 10 ; y = (LOC_Y - 5.25) * 10. On verifie ensuite que
    l'ecart redevient normal, sinon on leve une erreur (pas de correction a l'aveugle).
    """
    mae_sql = (
        f"SELECT SEASON_1, avg(abs(SHOT_DISTANCE - {DIST_SQL})) FROM base "
        "GROUP BY 1 ORDER BY 1"
    )
    before = {int(s): float(m) for s, m in con.sql(mae_sql).fetchall()}
    bad = sorted(s for s, m in before.items() if m > C.SCALE_MAE_THRESHOLD_FT)
    con.execute("ALTER TABLE base ADD COLUMN coord_corrigee BOOLEAN DEFAULT FALSE")
    audit["mae_distance_par_saison_avant"] = before
    audit["saisons_echelle_corrompue"] = bad
    if bad:
        seasons = ",".join(str(s) for s in bad)
        con.execute(f"""
            UPDATE base
            SET LOC_X = round(LOC_X * -10, 1),   -- x10 ET axe gauche/droite inverse
                LOC_Y = round((LOC_Y - {BASKET_Y}) * 10, 1),
                coord_corrigee = TRUE
            WHERE SEASON_1 IN ({seasons})
        """)
        after = {int(s): float(m) for s, m in con.sql(mae_sql).fetchall()}
        audit["mae_distance_par_saison_apres"] = after
        still_bad = [s for s in bad if after[s] > C.SCALE_MAE_OK_FT]
        if still_bad:
            raise RuntimeError(
                f"Correction d'echelle insuffisante pour les saisons {still_bad} : "
                f"{ {s: after[s] for s in still_bad} }"
            )
        audit["lignes_coordonnees_corrigees"] = con.sql(
            "SELECT count(*) FROM base WHERE coord_corrigee"
        ).fetchone()[0]
        log.info("echelle corrigee pour les saisons %s", bad)


# --------------------------------------------------------------------------
def dedupe(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Retire les doublons exacts, sauf tip/putback/follow-up (plausibles)."""
    cols = (
        "SEASON_1, TEAM_ID, PLAYER_ID, GAME_ID, ACTION_TYPE, SHOT_TYPE, BASIC_ZONE, "
        "ZONE_NAME, ZONE_ABB, ZONE_RANGE, LOC_X, LOC_Y, SHOT_DISTANCE, QUARTER, "
        "MINS_LEFT, SECS_LEFT, cible"
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE dup_stats AS
        SELECT *, row_number() OVER (PARTITION BY {cols} ORDER BY rid) AS rn,
                  count(*)     OVER (PARTITION BY {cols})              AS nb
        FROM base
    """)
    audit["lignes_dans_groupes_doublons"] = con.sql(
        "SELECT count(*) FROM dup_stats WHERE nb > 1").fetchone()[0]
    audit["lignes_en_trop_doublons"] = con.sql(
        "SELECT count(*) FROM dup_stats WHERE rn > 1").fetchone()[0]
    audit["doublons_tip_putback_conserves"] = con.sql(
        f"SELECT count(*) FROM dup_stats WHERE rn > 1 AND {TIP_FAMILY}").fetchone()[0]
    con.execute(f"""
        CREATE OR REPLACE TABLE dedup AS
        SELECT * EXCLUDE (rn, nb), (nb > 1 AND {TIP_FAMILY}) AS doublon_plausible
        FROM dup_stats
        WHERE rn = 1 OR {TIP_FAMILY}
    """)
    con.execute("DROP TABLE dup_stats")
    audit["doublons_supprimes"] = audit["lignes_apres_base"] - _n(con, "dedup")


# --------------------------------------------------------------------------
def drop_incoherent(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Retire les tirs dont le type (2PT/3PT) contredit la zone ou la distance."""
    zone_bad = (
        "((SHOT_TYPE LIKE '3PT%' AND BASIC_ZONE IN "
        "('Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range')) OR "
        "(SHOT_TYPE LIKE '2PT%' AND BASIC_ZONE IN "
        "('Above the Break 3', 'Left Corner 3', 'Right Corner 3')))"
    )
    # Tolerance : SHOT_DISTANCE est un plancher, la ligne des coins est a 22 ft.
    dist_bad = (
        f"((SHOT_TYPE LIKE '3PT%' AND distance_ft < {C.CORNER_THREE_FT - 1.0}) OR "
        f"(SHOT_TYPE LIKE '2PT%' AND distance_ft > {C.ARC_THREE_FT + 1.0}))"
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE clean_pre AS
        SELECT *, {DIST_SQL} AS distance_ft FROM dedup
    """)
    audit["incoherences_zone_type"] = con.sql(
        f"SELECT count(*) FROM clean_pre WHERE {zone_bad}").fetchone()[0]
    audit["incoherences_distance_type"] = con.sql(
        f"SELECT count(*) FROM clean_pre WHERE {dist_bad}").fetchone()[0]
    audit["incoherences_union"] = con.sql(
        f"SELECT count(*) FROM clean_pre WHERE {zone_bad} OR {dist_bad}").fetchone()[0]
    con.execute(f"""
        CREATE OR REPLACE TABLE clean_pre2 AS
        SELECT * FROM clean_pre WHERE NOT ({zone_bad}) AND NOT ({dist_bad})
    """)
    con.execute("DROP TABLE clean_pre")
    audit["lignes_apres_incoherences"] = _n(con, "clean_pre2")


# --------------------------------------------------------------------------
def impute_position(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """POSITION / POSITION_GROUP sont absents pour toute la saison 2024-25.

    On reprend la derniere position connue du joueur (saison la plus recente ou elle
    est renseignee). Les recrues 2024-25 sans historique passent en 'Inconnu'.
    """
    audit["position_manquante_avant"] = con.sql(
        "SELECT count(*) FROM clean_pre2 WHERE POSITION IS NULL").fetchone()[0]
    con.execute("""
        CREATE OR REPLACE TABLE clean AS
        WITH last_pos AS (
            SELECT PLAYER_ID,
                   arg_max(POSITION, SEASON_1) FILTER (WHERE POSITION IS NOT NULL)       AS pos,
                   arg_max(POSITION_GROUP, SEASON_1) FILTER (WHERE POSITION_GROUP IS NOT NULL) AS grp
            FROM clean_pre2 GROUP BY 1
        )
        SELECT c.* EXCLUDE (POSITION, POSITION_GROUP),
               coalesce(c.POSITION, l.pos, 'Inconnu')       AS POSITION,
               coalesce(c.POSITION_GROUP, l.grp, 'Inconnu') AS POSITION_GROUP,
               (c.POSITION IS NULL)                         AS position_imputee
        FROM clean_pre2 c LEFT JOIN last_pos l USING (PLAYER_ID)
    """)
    audit["position_inconnue_apres"] = con.sql(
        "SELECT count(*) FROM clean WHERE POSITION = 'Inconnu'").fetchone()[0]
    audit["lignes_clean"] = _n(con, "clean")
    for t in ("base", "dedup", "clean_pre2"):
        con.execute(f"DROP TABLE IF EXISTS {t}")


def run(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    load_raw(con, audit)
    build_base(con, audit)
    fix_coordinate_scale(con, audit)
    dedupe(con, audit)
    drop_incoherent(con, audit)
    impute_position(con, audit)
