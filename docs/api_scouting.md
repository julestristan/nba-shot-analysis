# Note de cadrage : API stats.nba.com (`nba_api`)

**Auteur :** Paul · **Date :** 1er septembre 2026 · **Statut :** à valider en réunion d'équipe

Objet : évaluer si l'API officielle NBA doit remplacer, compléter ou seulement
contrôler les datasets Kaggle listés dans `datasets_ref.md`. Conclusion en tête,
détails ensuite.

---

## 1. Recommandation en une page

| Question | Réponse |
|---|---|
| L'API couvre-t-elle le périmètre du sujet ? | **Oui, et plus largement que Kaggle** : 1996-97 → 2025-26, mis à jour en continu. |
| Faut-il en faire la source principale ? | **Oui pour les tirs.** Les CSV Kaggle sont des dumps figés de cette même API. |
| Coût d'extraction ? | ~340 appels pour les 20 joueurs (saison régulière), **~10 min** de run, ~370 k tirs. |
| Risque ? | API **non officielle et non documentée** : pas de SLA, throttling agressif, schéma modifiable sans préavis. → on **versionne les extractions en parquet** et on ne dépend jamais du réseau pendant l'analyse. |
| Apport décisif | L'API est la **seule** source qui expose des variables de **pression défensive** (distance du défenseur, touch time, dribbles), exactement les facteurs que le sujet désigne comme « difficiles à trouver ». Avec une limite majeure : voir §4. |

**Décision proposée à l'équipe :** l'API devient la source de référence pour la
table de tirs ; les datasets Kaggle servent (a) de jeu de travail immédiat pour
démarrer l'EDA sans attendre, (b) de **contrôle croisé** pour valider notre
extraction.

---

## 2. Ce qu'est réellement cette « API »

Il n'existe pas d'API publique NBA avec clé et documentation. Ce que tout le
monde appelle « l'API NBA » est l'**endpoint interne qui alimente nba.com/stats**.
`nba_api` (paquet Python `swar/nba_api`, v1.11.4) est un wrapper communautaire
qui construit les URL, pose les bons en-têtes HTTP et normalise les réponses.

Conséquences pratiques, à écrire noir sur blanc dans le rapport :

- **Aucune garantie de disponibilité.** Le service coupe régulièrement, et refuse
  les requêtes sans en-têtes `Referer`/`User-Agent` crédibles (gérés par `nba_api`).
- **Throttling.** Pas de quota publié, mais au-delà d'environ 1 requête/seconde
  soutenue, on récolte des timeouts puis un blocage temporaire d'IP. Notre client
  se cale à **1 requête / 1,2-1,8 s** avec backoff exponentiel.
- **Pas de versionnement du schéma.** Les colonnes peuvent bouger. On sélectionne
  donc les `resultSets` **par nom, jamais par index** (`ShotChartDetail` renvoie
  ses deux tables dans un ordre non garanti, piège vérifié).
- **Ne tourne pas dans les environnements bridés.** `stats.nba.com` est
  inaccessible depuis un CI ou un sandbox réseau restreint : le run se fait
  depuis nos postes / le conteneur Docker du repo.

---

## 3. Endpoints retenus

### 3.1 `ShotChartDetail`, la table centrale

Un enregistrement = **un tir tenté**. C'est la table qui porte la variable cible.

| Paramètre | Valeur retenue | Pourquoi |
|---|---|---|
| `player_id` | id NBA officiel | cf. §5 |
| `team_id` | `0` | « toutes équipes » : indispensable pour les joueurs transférés (LeBron, Durant, Harden, CP3…) |
| `season_nullable` | `"2015-16"` | une saison par appel |
| `season_type_all_star` | `Regular Season` / `Playoffs` | deux passes distinctes |
| `context_measure_simple` | **`FGA`** | ⚠️ **piège n°1 du projet** |

> **⚠️ À retenir absolument.** La valeur par défaut de `context_measure_simple`
> est `PTS`, qui ne renvoie **que les tirs réussis**. Une extraction faite sans y
> penser produit un `SHOT_MADE_FLAG` constant à 1, cible dégénérée, modèle à
> 100 % d'accuracy, et personne ne comprend pourquoi. Il faut `FGA`.

**24 colonnes renvoyées**, dont les exploitables pour la modélisation :

| Colonne | Type | Rôle pressenti |
|---|---|---|
| `SHOT_MADE_FLAG` | 0/1 | **cible** |
| `LOC_X`, `LOC_Y` | int (1/10 de pied, origine = panier) | localisation exacte → features géométriques (distance euclidienne, angle) |
| `SHOT_DISTANCE` | int (pieds) | distance au panier |
| `SHOT_ZONE_BASIC` / `_AREA` / `_RANGE` | catégoriel | découpage terrain fourni par la NBA |
| `ACTION_TYPE` | catégoriel (~70 modalités) | **la variable la plus discriminante** : « Driving Layup », « Step Back Jump Shot », « Alley Oop Dunk »… encode le type de geste |
| `SHOT_TYPE` | 2PT / 3PT | |
| `PERIOD`, `MINUTES_REMAINING`, `SECONDS_REMAINING` | int | contexte temporel → clutch, fatigue de fin de quart-temps |
| `GAME_ID`, `GAME_EVENT_ID` | id | **clé de jointure vers le play-by-play** (§4.2) |
| `HTM`, `VTM` | code équipe | domicile / extérieur, identité de l'adversaire |
| `GAME_DATE` | date | back-to-backs, jours de repos, saisonnalité |

Second `resultSet` fourni gratuitement : `LeagueAverages` (FG% moyen de la ligue
par zone) → **benchmark tout prêt** pour la partie 1 du sujet (« comparer
l'efficacité »), et base d'un indicateur type *points au-dessus de la moyenne*.

### 3.2 `PlayerDashPtShots`, la pression défensive (2013-14 →)

Splits de tir issus du tracking optique (SportVU puis Second Spectrum) :

| `resultSet` | Modalités |
|---|---|
| `ClosestDefenderShooting` | défenseur à 0-2 ft / 2-4 ft / 4-6 ft / 6+ ft |
| `TouchTimeShooting` | ballon tenu < 2 s / 2-6 s / 6+ s |
| `DribbleShooting` | 0 / 1 / 2 / 3-6 / 7+ dribbles avant le tir |
| `ShotClockShooting` | temps restant sur les 24 s |
| `GeneralShooting` | catch & shoot vs pull-up |

C'est exactement le vocabulaire du sujet (« pression défensive exercée sur le
tireur », « qualité de la dernière passe »). **Mais lire le §4 avant de s'emballer.**

### 3.3 Endpoints d'appoint

- `PlayerCareerStats` → saisons réellement jouées (évite des centaines d'appels vides).
- `CommonPlayerInfo` → taille, poste, année de draft (features statiques).
- `PlayByPlayV3` → reconstruction du contexte de chaque possession (§4.2).
- `LeagueDashPlayerPtShot` → mêmes splits tracking, mais pour **toute la ligue** :
  permet de situer nos 20 joueurs par rapport au reste des joueurs NBA.
- `nba_api.stats.static.players` → référentiel local nom ↔ id, **sans appel réseau**.

---

## 4. Les trois limites à assumer dans le rapport

### 4.1 Le tracking n'est PAS au niveau du tir

`PlayerDashPtShots` renvoie des **agrégats joueur × saison × modalité**, pas la
distance du défenseur pour chaque tir. La NBA ne publie plus les données
tracking par événement depuis la fin de l'accès public SportVU.

Conséquence, et c'est un vrai choix de conception à trancher en équipe :

- ❌ on ne peut pas mettre `defender_distance` comme feature d'un modèle par tir ;
- ✅ on peut construire des features de **profil de joueur-saison** (« part de
  tirs contestés », « % de tirs en catch & shoot »), mais **attention à la fuite
  de données** : ces agrégats sont calculés a posteriori sur la saison entière.
  Si on les utilise, il faut au minimum les décaler d'une saison (features en
  N-1) et le justifier ;
- ✅ on peut les utiliser en **analyse descriptive** (partie 1 du sujet) et pour
  **quantifier le biais d'omission** : comparer le pouvoir prédictif d'un modèle
  sur des tirs contestés vs ouverts est en soi un résultat intéressant pour la
  conclusion.

### 4.2 Le play-by-play comble une partie du trou, pour un coût réel

`GAME_ID` + `GAME_EVENT_ID` permettent de rattacher chaque tir à l'événement
correspondant du play-by-play, et donc de reconstruire :

- **l'assist** (qui a passé, donc « tir créé » vs « tir isolé ») ;
- **l'écart au score** au moment du tir (pression du scénario) ;
- les **minutes jouées consécutives** (proxy de fatigue) ;
- le **rebond offensif** précédent (défense non replacée = tir plus facile).

Coût : ~1 appel par match, soit plusieurs dizaines de milliers d'appels si on
couvre tout. **Proposition : ne le faire que sur l'ère tracking (2013-14 →)** et
sur les matchs où l'un de nos 20 joueurs a tiré. À arbitrer selon le temps.

### 4.3 Ce qui restera hors de portée, quoi qu'on fasse

Le sujet cite l'orientation des appuis, la qualité de la tenue de balle, la force
du contact, l'état physique. **Aucune source publique ne les contient.** Ce n'est
pas un échec du projet : c'est le **plafond de performance irréductible** du
modèle, et l'expliquer proprement dans le rapport final vaut mieux que de courir
après une AUC impossible. Ordre de grandeur : les modèles publiés de *shot
quality* plafonnent autour de **0,65-0,70 d'AUC** sur données publiques. C'est
notre repère de réalisme, à annoncer dès le rapport de modélisation.

---

## 5. Articulation avec les datasets Kaggle (l'équipe)

**Bonne nouvelle vérifiée :** le CSV déjà présent dans le repo
(`data/NBA_2004_Shots.csv`) utilise les **mêmes `PLAYER_ID` que l'API**
(Kobe Bryant = `977` des deux côtés). La jointure est donc directe, sans
matching flou sur les noms.

| Source | Couverture | Granularité | Rôle proposé |
|---|---|---|---|
| **`ShotChartDetail` (API)** | 1996-97 → 2025-26 | tir | **source de référence** |
| CSV `NBA_*_Shots` (repo) | 2004 → 2024 | tir | démarrage EDA + **contrôle croisé** de notre extraction |
| Kaggle `nba-shot-locations` | 1997 → 2019 | tir | redondant avec l'API, s'arrête en 2019 |
| Kaggle `nba-games` (ranking) | 2014 → 2018 | équipe-match | contexte équipe (bilan, forme) |
| Kaggle `nba-players-stats` | depuis 1950 | joueur-saison | attributs joueur (taille, poste) |
| `PlayerDashPtShots` (API) | 2013-14 → | joueur-saison-modalité | pression défensive, cf. §4.1 |

**Test de contrôle croisé à faire en priorité** (une demi-heure, très rentable) :
extraire via l'API la saison 2003-04 des joueurs présents dans
`NBA_2004_Shots.csv`, puis comparer nombre de tirs, FG% et distribution des
`LOC_X`/`LOC_Y`. Si les deux coïncident, on valide d'un coup notre pipeline
**et** la fiabilité du dataset des collègues. Si ça diverge, on a identifié un
problème avant l'EDA plutôt qu'après.

---

## 6. Le code livré

```
src/api/
├── config.py          périmètre (20 joueurs, saisons), chemins, réglages réseau
├── client.py          throttling + retry + cache disque : TOUT passe par ici
├── players.py         nom -> player_id, saisons réellement jouées
├── fetch_shots.py     extraction ShotChartDetail        -> data/raw/*.parquet
└── fetch_tracking.py  extraction PlayerDashPtShots      -> data/interim/*.parquet
```

Trois propriétés voulues :

1. **Idempotent**, relancé, le script saute ce qui est déjà téléchargé. On peut
   couper le run et le reprendre.
2. **Cache disque**, chaque réponse JSON brute est conservée dans
   `data/.api_cache/`. On ne redemande jamais deux fois la même chose, et on peut
   rejouer l'extraction hors ligne (reproductibilité pour le jury).
3. **Sortie parquet**, 5 à 10× plus compact que le CSV, types préservés,
   lecture instantanée dans les notebooks.

### Lancer l'extraction

```bash
docker compose up -d --build
docker compose exec jupyter bash

pip install -r requirements.txt

# 1. vérifier le plan sans rien télécharger
python -m src.api.fetch_shots --dry-run

# 2. run de validation sur 2 joueurs
python -m src.api.fetch_shots --players "Stephen Curry" "Kobe Bryant"

# 3. extraction complète (~10 min) puis playoffs
python -m src.api.fetch_shots
python -m src.api.fetch_shots --playoffs

# 4. pression défensive (2013-14 ->)
python -m src.api.fetch_tracking --dataset closest_defender
python -m src.api.fetch_tracking --dataset touch_time_shooting
```

⚠️ Ajouter au `.gitignore` : `data/raw/`, `data/interim/`, `data/.api_cache/`.
Les parquets d'extraction ne vont **pas** dans Git.

---

## 7. Points à trancher en réunion

1. **Liste des 20 joueurs.** Le sujet dit « 20 des meilleurs joueurs du 21e
   siècle selon ESPN, de LeBron James à Giannis Antetokounmpo ». Le classement
   ESPN de référence est un **top 25** où Giannis est 11e, pas 20e : la borne
   citée par le sujet ne correspond à rien de littéral. On propose de retenir les
   **20 premiers du top 25 ESPN** (LeBron → Ray Allen) et de faire valider par le
   mentor. La liste est dans `config.PLAYERS_20`, les rangs 21-25 sont gardés en
   réserve.
2. **« Encore actifs aujourd'hui » (formulation du sujet) est factuellement faux**
   pour la majorité de la liste (Kobe, Duncan, Shaq, Garnett, Nash, Kidd, Iverson,
   Ray Allen sont retraités). À signaler au mentor. Si le périmètre devait se
   limiter aux joueurs actifs, il ne resterait que ~6 joueurs, trop peu.
3. **Profondeur temporelle.** Tout depuis 1996-97 (plus de données, mais le jeu a
   radicalement changé : explosion du tir à 3 points) ou 2013-14 → (moins de
   données, mais tracking disponible et jeu homogène) ? Recommandation :
   **extraire tout, filtrer au moment de la modélisation**, et traiter la saison
   comme une variable à part entière.
4. **Play-by-play : on y va ou pas ?** Gros gain en features, gros coût en temps
   d'extraction (§4.2).

---

## Sources

- [swar/nba_api, dépôt et documentation](https://github.com/swar/nba_api)
- [Documentation de l'endpoint ShotChartDetail](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/shotchartdetail.md)
- [Discussion sur le rythme de requêtes acceptable](https://github.com/swar/nba_api/issues/69)
- [ESPN : Ranking the top 25 NBA players of the 21st century](https://www.espn.com/nba/story/_/id/40616441/ranking-top-25-nba-players-21st-century)
