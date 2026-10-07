"""Couche d'accès bas niveau à stats.nba.com via `nba_api`.

Rôle :
  * throttler les appels (stats.nba.com blackliste vite),
  * retenter proprement en cas de timeout / 429 / 5xx,
  * mettre en cache les réponses pour ne jamais retélécharger deux fois.

Toute la suite du projet passe par `call_endpoint`. Aucun autre module ne doit
instancier un endpoint `nba_api` directement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from requests.exceptions import ReadTimeout, ConnectionError as ReqConnectionError

from . import config

logger = logging.getLogger(__name__)

_last_call_ts: float = 0.0


def _throttle() -> None:
    """Garantit un espacement minimal entre deux requêtes sortantes."""
    global _last_call_ts
    wait = config.REQUEST_DELAY_S + random.uniform(0, config.REQUEST_JITTER_S)
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < wait:
        time.sleep(wait - elapsed)
    _last_call_ts = time.monotonic()


def _cache_path(endpoint_name: str, params: dict[str, Any]) -> Path:
    key = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha1(f"{endpoint_name}|{key}".encode()).hexdigest()[:16]
    return config.CACHE_DIR / f"{endpoint_name}_{digest}.json"


def call_endpoint(
    endpoint_cls: Callable[..., Any],
    *,
    dataset: str | int = 0,
    use_cache: bool = True,
    **params: Any,
) -> pd.DataFrame:
    """Appelle un endpoint `nba_api` et renvoie un DataFrame.

    Parameters
    ----------
    endpoint_cls
        La classe d'endpoint, ex. `nba_api.stats.endpoints.ShotChartDetail`.
    dataset
        Nom du resultSet voulu (ex. "Shot_Chart_Detail") ou index numérique.
        Préférez TOUJOURS le nom : l'ordre des resultSets n'est pas garanti par
        stats.nba.com et un index en dur casse silencieusement.
    use_cache
        Si True, relit le JSON déjà téléchargé au lieu de refaire la requête.
    **params
        Paramètres passés tels quels à l'endpoint.
    """
    name = endpoint_cls.__name__
    path = _cache_path(name, params)

    if use_cache and path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _payload_to_df(payload, dataset)

    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        _throttle()
        try:
            ep = endpoint_cls(timeout=config.REQUEST_TIMEOUT_S, **params)
            payload = json.loads(ep.get_json())
            path.write_text(json.dumps(payload), encoding="utf-8")
            return _payload_to_df(payload, dataset)
        except (ReadTimeout, ReqConnectionError, json.JSONDecodeError) as exc:
            last_exc = exc
            backoff = config.BACKOFF_BASE_S * (2 ** (attempt - 1))
            logger.warning(
                "%s tentative %d/%d échouée (%s) - nouvelle tentative dans %ds",
                name, attempt, config.MAX_RETRIES, type(exc).__name__, backoff,
            )
            time.sleep(backoff)
        except Exception as exc:  # noqa: BLE001 - on veut voir l'erreur métier
            logger.error("%s : erreur non réseau %s : %s", name, type(exc).__name__, exc)
            raise

    raise RuntimeError(f"{name} : échec après {config.MAX_RETRIES} tentatives") from last_exc


def _payload_to_df(payload: dict[str, Any], dataset: str | int) -> pd.DataFrame:
    sets = payload.get("resultSets") or payload.get("resultSet")
    if isinstance(sets, dict):  # certains endpoints renvoient un objet unique
        sets = [sets]

    if isinstance(dataset, int):
        rs = sets[dataset]
    else:
        try:
            rs = next(s for s in sets if s.get("name") == dataset)
        except StopIteration as exc:
            available = [s.get("name") for s in sets]
            raise KeyError(f"resultSet {dataset!r} absent ; disponibles : {available}") from exc

    return pd.DataFrame(rs["rowSet"], columns=rs["headers"])
