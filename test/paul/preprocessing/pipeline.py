"""Orchestrateur de la preparation des donnees.

Usage (depuis le dossier test/paul, dans le conteneur ou le venv) :

    python -m preprocessing.pipeline

Produit :
    data/interim/shots_clean.parquet   toutes saisons, nettoye + features (objectif 1)
    data/interim/shots_model.parquet   saisons a coordonnees fiables, colonnes modele (objectif 2)
    test/paul/resultats/preprocessing_audit.json    comptes a chaque etape (alimente le rapport)

Le script est deterministe : relance, il reconstruit tout depuis les CSV bruts.
"""

from __future__ import annotations

import json
import logging
import time

import duckdb

from . import cleaning, features
from . import config as C
from . import model_features as M

log = logging.getLogger(__name__)


def _connect() -> duckdb.DuckDBPyConnection:
    if C.DB_PATH.exists():
        C.DB_PATH.unlink()
    con = duckdb.connect(str(C.DB_PATH))
    con.execute(f"PRAGMA memory_limit='{C.DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"PRAGMA threads={C.DUCKDB_THREADS}")
    con.execute(f"PRAGMA temp_directory='{C.TMP_DIR}'")
    return con


def _sanity_checks(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    """Controles bloquants : le pipeline s'arrete si l'un d'eux echoue."""
    q = lambda sql: con.sql(sql).fetchone()[0]  # noqa: E731
    must_be_zero = {
        "cible_hors_0_1": "SELECT count(*) FROM shots WHERE cible NOT IN (0, 1)",
        "lignes_dupliquees_rid": "SELECT count(*) - count(DISTINCT rid) FROM clean",
        "nulls_distance": "SELECT count(*) FROM shots WHERE distance_ft IS NULL",
        "nulls_angle": "SELECT count(*) FROM shots WHERE angle_deg IS NULL",
        "nulls_domicile": "SELECT count(*) FROM shots WHERE domicile IS NULL",
        "nulls_jours_repos": "SELECT count(*) FROM shots WHERE jours_repos IS NULL",
        "nulls_geste": "SELECT count(*) FROM shots WHERE geste_famille IS NULL",
        "temps_hors_bornes": "SELECT count(*) FROM shots WHERE temps_restant_periode_s < 0 "
                             "OR temps_restant_periode_s > CASE WHEN QUARTER <= 4 THEN 720 ELSE 300 END",
        "domicile_incoherent": "SELECT count(*) FROM shots WHERE domicile = 1 AND equipe <> HOME_TEAM",
        "hors_fenetre": f"SELECT count(*) FROM shots WHERE SEASON_1 < {C.FIRST_SEASON}",
        "coordonnees_non_fiables": "SELECT count(*) FROM shots WHERE NOT coord_fiable",
        "experience_negative": "SELECT count(*) FROM shots WHERE saisons_depuis_premiere_apparition < 0",
        "match_dans_plusieurs_splits": "SELECT count(*) FROM (SELECT GAME_ID FROM shots "
                                       "GROUP BY 1 HAVING count(DISTINCT split) > 1)",
    }
    failed = {}
    for name, sql in must_be_zero.items():
        v = q(sql)
        audit.setdefault("controles", {})[name] = v
        if v != 0:
            failed[name] = v
    if failed:
        raise RuntimeError(f"Controles de qualite en echec : {failed}")

    audit["repartition_split"] = dict(con.sql(
        "SELECT split, count(*) FROM shots GROUP BY 1 ORDER BY 1").fetchall())
    audit["repartition_split_temps"] = dict(con.sql(
        "SELECT split_temps, count(*) FROM shots GROUP BY 1 ORDER BY 1").fetchall())
    audit["taux_reussite_global"] = q("SELECT avg(cible) FROM shots")
    audit["taux_reussite_par_split"] = dict(con.sql(
        "SELECT split, round(avg(cible), 4) FROM shots GROUP BY 1 ORDER BY 1").fetchall())
    audit["lignes_par_saison"] = dict(con.sql(
        "SELECT SEASON_1, count(*) FROM shots GROUP BY 1 ORDER BY 1").fetchall())
    audit["familles_geste"] = {
        r[0]: {"n": r[1], "reussite": round(r[2], 4)} for r in con.sql(
            "SELECT geste_famille, count(*), avg(cible) FROM shots GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()}
    audit["nb_action_type_distincts"] = q("SELECT count(DISTINCT ACTION_TYPE) FROM shots")
    audit["lignes_fin_de_periode"] = q("SELECT count(*) FROM shots WHERE fin_de_periode = 1")
    audit["reussite_fin_de_periode"] = q(
        "SELECT avg(cible) FROM shots WHERE fin_de_periode = 1")
    audit["reussite_hors_fin_de_periode"] = q(
        "SELECT avg(cible) FROM shots WHERE fin_de_periode = 0")
    audit["reussite_domicile"] = q("SELECT avg(cible) FROM shots WHERE domicile = 1")
    audit["reussite_exterieur"] = q("SELECT avg(cible) FROM shots WHERE domicile = 0")
    audit["reussite_par_jours_repos"] = {
        int(k): round(v, 4) for k, v in con.sql(
            "SELECT jours_repos, avg(cible) FROM shots WHERE NOT premier_match_saison "
            "GROUP BY 1 ORDER BY 1").fetchall()}
    audit["reussite_tirs_precedents_null"] = q(
        "SELECT count(*) FROM shots WHERE reussite_tirs_precedents IS NULL")
    audit["nb_joueurs_projet"] = q(
        "SELECT count(DISTINCT PLAYER_ID) FROM shots WHERE joueur_projet")
    audit["tirs_joueurs_projet"] = q("SELECT count(*) FROM shots WHERE joueur_projet")


def _export(con: duckdb.DuckDBPyConnection, audit: dict) -> None:
    con.execute(f"""
        COPY (SELECT * FROM shots ORDER BY SEASON_1, GAME_ID, temps_ecoule_match_s)
        TO '{C.SHOTS_CLEAN_PATH}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    cols = ", ".join(
        f"{c}::INTEGER AS {c}" if c == "premier_match_saison" else c for c in M.MODEL_COLUMNS
    )
    con.execute(f"""
        COPY (SELECT {cols} FROM shots WHERE coord_fiable
              ORDER BY SEASON_1, GAME_ID, temps_ecoule_match_s)
        TO '{C.SHOTS_MODEL_PATH}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    audit["lignes_shots_clean"] = con.sql(
        f"SELECT count(*) FROM read_parquet('{C.SHOTS_CLEAN_PATH}')").fetchone()[0]
    audit["lignes_shots_model"] = con.sql(
        f"SELECT count(*) FROM read_parquet('{C.SHOTS_MODEL_PATH}')").fetchone()[0]
    audit["taille_mo_clean"] = round(C.SHOTS_CLEAN_PATH.stat().st_size / 1e6, 1)
    audit["taille_mo_model"] = round(C.SHOTS_MODEL_PATH.stat().st_size / 1e6, 1)


def run() -> dict:
    t0 = time.time()
    audit: dict = {}
    con = _connect()
    cleaning.run(con, audit)
    features.run(con, audit)
    _sanity_checks(con, audit)
    _export(con, audit)
    audit["duree_s"] = round(time.time() - t0, 1)
    C.AUDIT_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
    con.close()
    log.info("termine en %.0f s", audit["duree_s"])
    return audit


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run()
