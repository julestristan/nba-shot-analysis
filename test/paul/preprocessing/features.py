"""Etape 2.2 : feature engineering, flags joueurs et decoupages.

Entree : table DuckDB `clean` (cleaning.py). Sortie : table `shots`.

Regle d'or anti-fuite : aucune feature ne s'appuie sur le resultat du tir courant
ni sur un tir posterieur. Les deux features de sequence n'utilisent que des tirs
pris STRICTEMENT avant (en secondes de jeu ecoulees) dans le meme match.
Interdits : pourcentage de reussite du joueur sur la saison, agregats de tracking
non decales, EVENT_TYPE (copie de la cible).
"""

from __future__ import annotations

import logging

import duckdb

from . import config as C

log = logging.getLogger(__name__)

# 6 familles de gestes, regroupant les 69 libelles ACTION_TYPE.
# L'ordre des WHEN compte : un "Turnaround Hook Shot" est un hook, un
# "Putback Dunk Shot" est un tip/putback (contexte de 2e chance).
GESTE_SQL = """
CASE
  WHEN ACTION_TYPE ILIKE '%tip%' OR ACTION_TYPE ILIKE '%putback%'
       OR ACTION_TYPE ILIKE '%follow up%'                         THEN 'tip_putback'
  WHEN ACTION_TYPE ILIKE '%dunk%'                                 THEN 'dunk'
  WHEN ACTION_TYPE ILIKE '%hook%'                                 THEN 'hook'
  WHEN ACTION_TYPE ILIKE '%layup%' OR ACTION_TYPE ILIKE '%finger roll%' THEN 'layup'
  WHEN ACTION_TYPE ILIKE '%pullup%' OR ACTION_TYPE ILIKE '%pull-up%'
       OR ACTION_TYPE ILIKE '%step back%' OR ACTION_TYPE ILIKE '%fadeaway%'
       OR ACTION_TYPE ILIKE '%turnaround%' OR ACTION_TYPE ILIKE '%floating%'
                                                                  THEN 'jump_cree'
  ELSE 'jump_simple'
END
"""


def build_team_abbr(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Table (SEASON_1, TEAM_ID) -> abreviation (celle presente dans TOUS ses matchs).

    HOME_TEAM / AWAY_TEAM sont des abreviations, TEAM_ID un identifiant : pour savoir
    si le tireur joue a domicile il faut relier les deux. L'abreviation d'une equipe
    est la seule qui apparait dans chacun de ses matchs de la saison. On gere ainsi
    les changements de nom (NJN -> BKN, SEA -> OKC, NOH -> NOP, CHA -> CHO...).
    """
    con.execute("""
        CREATE OR REPLACE TABLE team_abbr AS
        WITH g AS (SELECT DISTINCT SEASON_1, GAME_ID, TEAM_ID, HOME_TEAM, AWAY_TEAM FROM clean),
        u AS (SELECT SEASON_1, GAME_ID, TEAM_ID, HOME_TEAM AS abbr FROM g
              UNION ALL
              SELECT SEASON_1, GAME_ID, TEAM_ID, AWAY_TEAM FROM g),
        c AS (SELECT SEASON_1, TEAM_ID, abbr, count(DISTINCT GAME_ID) AS n FROM u GROUP BY ALL),
        t AS (SELECT SEASON_1, TEAM_ID, count(DISTINCT GAME_ID) AS ng FROM g GROUP BY ALL)
        SELECT c.SEASON_1, c.TEAM_ID, c.abbr, c.n, t.ng
        FROM c JOIN t USING (SEASON_1, TEAM_ID)
        WHERE c.n = t.ng
    """)
    bad = con.sql("""
        SELECT count(*) FROM (SELECT SEASON_1, TEAM_ID FROM team_abbr
                              GROUP BY 1, 2 HAVING count(*) <> 1)
    """).fetchone()[0]
    missing = con.sql("""
        SELECT count(*) FROM (SELECT DISTINCT SEASON_1, TEAM_ID FROM clean) d
        LEFT JOIN team_abbr a USING (SEASON_1, TEAM_ID) WHERE a.abbr IS NULL
    """).fetchone()[0]
    audit["equipes_abreviation_ambigue"] = bad
    audit["equipes_abreviation_introuvable"] = missing
    if bad or missing:
        raise RuntimeError(f"Mapping equipe -> abreviation invalide ({bad} ambigus, {missing} manquants)")


def build_rest_days(con: duckdb.DuckDBPyConnection) -> None:
    """Jours de repos par (equipe, match), calcules sur le calendrier du jeu de donnees."""
    con.execute(f"""
        CREATE OR REPLACE TABLE rest AS
        WITH gm AS (SELECT DISTINCT TEAM_ID, SEASON_1, GAME_ID, GAME_DATE FROM clean),
        l AS (SELECT *, lag(GAME_DATE) OVER (PARTITION BY TEAM_ID, SEASON_1
                                             ORDER BY GAME_DATE, GAME_ID) AS prev_date FROM gm)
        SELECT TEAM_ID, GAME_ID,
               prev_date IS NULL AS premier_match_saison,
               CASE WHEN prev_date IS NULL THEN {C.REST_DAYS_CAP}
                    ELSE least(datediff('day', prev_date, GAME_DATE) - 1, {C.REST_DAYS_CAP})
               END AS jours_repos
        FROM l
    """)


def build_players(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Selectionne les joueurs du projet par une regle, sans choix a la main.

    Regle : classement ESPN (top 25 du 21e siecle) ET actif en 2024-25 ET au moins
    MIN_SEASONS saisons ET MIN_SHOTS tirs dans la fenetre. Les noms ne servent qu'a
    retrouver les PLAYER_ID ; toutes les jointures se font ensuite sur l'identifiant.
    Les joueurs du classement absents de la fenetre (retraites) sont simplement ignores.
    """
    con.execute("CREATE OR REPLACE TABLE espn (rang INTEGER, name VARCHAR)")
    con.executemany("INSERT INTO espn VALUES (?, ?)",
                    [(i + 1, n) for i, n in enumerate(C.ESPN_TOP_25)])
    ambigus = con.sql("""
        SELECT e.name FROM espn e JOIN (SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM clean) p
          ON p.PLAYER_NAME = e.name GROUP BY 1 HAVING count(DISTINCT p.PLAYER_ID) > 1
    """).fetchall()
    if ambigus:
        raise RuntimeError(f"Noms ESPN correspondant a plusieurs PLAYER_ID : {ambigus}")
    con.execute(f"""
        CREATE OR REPLACE TABLE joueurs_ids AS
        WITH st AS (SELECT PLAYER_ID, any_value(PLAYER_NAME) AS nom, count(*) AS tirs,
                           count(DISTINCT SEASON_1) AS saisons, max(SEASON_1) AS derniere
                    FROM clean GROUP BY 1)
        SELECT st.*, e.rang,
               (st.derniere = {C.LAST_SEASON_IN_DATA} AND st.saisons >= {C.MIN_SEASONS}
                AND st.tirs >= {C.MIN_SHOTS}) AS retenu
        FROM st JOIN espn e ON e.name = st.nom
    """)
    rows = con.sql("SELECT rang, nom, tirs, saisons, derniere, retenu FROM joueurs_ids ORDER BY rang").fetchall()
    audit["selection_joueurs"] = [
        {"rang_espn": r[0], "joueur": r[1], "tirs": r[2], "saisons": r[3],
         "derniere_saison": r[4], "retenu": bool(r[5])} for r in rows]
    audit["espn_absents_de_la_fenetre"] = [
        n for n in C.ESPN_TOP_25 if n not in {r[1] for r in rows}]
    audit["joueurs_projet"] = [r[1] for r in rows if r[5]]


def build_features(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    build_team_abbr(con, audit)
    build_rest_days(con)
    build_players(con, audit)

    left = "(MINS_LEFT * 60 + SECS_LEFT)"
    con.execute(f"""
        CREATE OR REPLACE TABLE feat AS
        SELECT c.*,
               -- contexte equipe
               a.abbr AS equipe,
               CASE WHEN a.abbr = c.HOME_TEAM THEN c.AWAY_TEAM ELSE c.HOME_TEAM END AS adversaire,
               (a.abbr = c.HOME_TEAM)::INTEGER AS domicile,
               r.jours_repos, r.premier_match_saison,
               (r.jours_repos = 0 AND NOT r.premier_match_saison)::INTEGER AS back_to_back,
               -- geometrie (angle 0 = dans l'axe du panier, 90 = parallele a la ligne de fond)
               degrees(atan2(abs(c.LOC_X), c.LOC_Y - {C.BASKET_Y})) AS angle_deg,
               (c.SHOT_TYPE LIKE '3PT%')::INTEGER AS tir_3pts,
               (c.BASIC_ZONE = 'Backcourt')::INTEGER AS tir_backcourt,
               -- temps
               {left} AS temps_restant_periode_s,
               (c.QUARTER > 4)::INTEGER AS prolongation,
               CASE WHEN c.QUARTER <= 4 THEN (c.QUARTER - 1) * 720 + (720 - {left})
                    ELSE 2880 + (c.QUARTER - 5) * 300 + (300 - {left}) END AS temps_ecoule_match_s,
               ({left} <= {C.END_OF_PERIOD_SECONDS})::INTEGER AS fin_de_periode,
               -- geste
               {GESTE_SQL} AS geste_famille,
               (c.ACTION_TYPE ILIKE '%bank%')::INTEGER AS tir_planche,
               -- modificateurs du geste
               (c.ACTION_TYPE ILIKE '%driving%' OR c.ACTION_TYPE ILIKE '%running%'
                OR c.ACTION_TYPE ILIKE '%cutting%')::INTEGER AS en_course,
               (c.ACTION_TYPE ILIKE '%pullup%' OR c.ACTION_TYPE ILIKE '%pull-up%'
                OR c.ACTION_TYPE ILIKE '%step back%' OR c.ACTION_TYPE ILIKE '%fadeaway%'
                OR c.ACTION_TYPE ILIKE '%turnaround%')::INTEGER AS en_desequilibre,
               (c.ACTION_TYPE ILIKE '%alley oop%')::INTEGER AS alley_oop,
               -- "money time" : derniere minute du 4e quart-temps ou d'une prolongation
               (c.QUARTER >= 4 AND {left} <= 60)::INTEGER AS derniere_minute,
               -- experience (censuree : le jeu de donnees commence en 2003-04)
               -- experience mesuree sur tout l'historique du CSV (depuis 2003-04),
               -- pas seulement sur la fenetre : un veteran n'a pas 0 saison en 2015-16
               c.SEASON_1 - h.premiere AS saisons_depuis_premiere_apparition,
               (h.premiere = {C.FIRST_SEASON_IN_DATA})::INTEGER AS experience_censuree,
               -- fiabilite des coordonnees
               (c.SEASON_1 >= {C.COORD_FIABLE_FROM_SEASON}) AS coord_fiable
        FROM clean c
        JOIN team_abbr a ON a.SEASON_1 = c.SEASON_1 AND a.TEAM_ID = c.TEAM_ID
        JOIN rest r ON r.TEAM_ID = c.TEAM_ID AND r.GAME_ID = c.GAME_ID
        JOIN (SELECT PLAYER_ID, min(SEASON_1) AS premiere FROM raw GROUP BY 1) h
          ON h.PLAYER_ID = c.PLAYER_ID
    """)
    n_clean = con.sql("SELECT count(*) FROM clean").fetchone()[0]
    n_feat = con.sql("SELECT count(*) FROM feat").fetchone()[0]
    if n_clean != n_feat:
        raise RuntimeError(f"Les jointures ont modifie le nombre de lignes : {n_clean} -> {n_feat}")

    # Sequence intra-match : uniquement des tirs STRICTEMENT anterieurs (en secondes).
    # Egalites de temps (meme joueur, meme seconde) : un tir rate precede forcement un tir
    # reussi (un panier rend le ballon a l'adversaire), d'ou `cible` en 2e cle. Sans risque
    # de fuite : les tirs d'une egalite recoivent NULL, et les tirs ulterieurs ne voient
    # que des resultats deja connus.
    order_tie = "temps_ecoule_match_s, cible, ACTION_TYPE, LOC_X, LOC_Y, rid"
    con.execute(f"""
        CREATE OR REPLACE TABLE seq AS
        SELECT rid,
               count(*) OVER (PARTITION BY GAME_ID, PLAYER_ID ORDER BY temps_ecoule_match_s
                   RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)          AS tirs_deja_pris,
               CASE WHEN count(*) OVER (PARTITION BY GAME_ID, PLAYER_ID, temps_ecoule_match_s) > 1
                    THEN NULL
                    ELSE avg(cible) OVER (PARTITION BY GAME_ID, PLAYER_ID ORDER BY {order_tie}
                         ROWS BETWEEN {C.SEQ_WINDOW} PRECEDING AND 1 PRECEDING) END
                                                                               AS reussite_tirs_precedents
        FROM feat
    """)
    audit["lignes_seq_egalite_temps"] = con.sql("""
        SELECT count(*) FROM (SELECT 1 FROM feat
            GROUP BY GAME_ID, PLAYER_ID, temps_ecoule_match_s HAVING count(*) > 1)
    """).fetchone()[0]


def build_final(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Assemble `shots` : features + sequence + flags joueurs + decoupages."""
    # Hachage multiplicatif de Knuth sur GAME_ID : deterministe, sans dependance a la
    # version de DuckDB (contrairement a hash()).
    u = "((f.GAME_ID * 2654435761 + %d) %% 4294967296) / 4294967296.0" % C.SPLIT_SEED
    tr = C.SPLIT_FRACTIONS["train"]
    va = tr + C.SPLIT_FRACTIONS["val"]
    con.execute(f"""
        CREATE OR REPLACE TABLE shots AS
        SELECT f.* EXCLUDE (rid),
               s.tirs_deja_pris,
               (s.tirs_deja_pris = 0)::INTEGER AS premier_tir_match,
               s.reussite_tirs_precedents,
               coalesce(j.retenu, FALSE)      AS joueur_projet,
               (j.PLAYER_ID IS NOT NULL)      AS espn_top25,
               (max(f.SEASON_1) OVER (PARTITION BY f.PLAYER_ID) = {C.LAST_SEASON_IN_DATA})
                                               AS actif_2024_25,
               CASE WHEN {u} < {tr} THEN 'train' WHEN {u} < {va} THEN 'val' ELSE 'test' END
                                               AS split,
               CASE WHEN f.SEASON_1 <= {C.TEMPORAL_TRAIN_MAX_SEASON} THEN 'train'
                    WHEN f.SEASON_1 = {C.TEMPORAL_VAL_SEASON} THEN 'val' ELSE 'test' END
                                               AS split_temps
        FROM feat f
        JOIN seq s USING (rid)
        LEFT JOIN joueurs_ids j ON j.PLAYER_ID = f.PLAYER_ID
    """)
    audit["lignes_shots"] = con.sql("SELECT count(*) FROM shots").fetchone()[0]


def run(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    build_features(con, audit)
    build_final(con, audit)
