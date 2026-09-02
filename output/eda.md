# 🏀 NBA Shot Analysis

# Rapport d'Exploration des Données

## Contexte

- **Source :** *NBA.com* (voir `datasets_ref.md`).
- **Périmètre :** 22 saisons **régulières** (playoffs exclus), de **2003‑04** (`NBA_2004`) à **2024‑25** (`NBA_2025`).
- **Donnée :** 1 ligne = 1 tentative de tir (hors lancers francs).
- **Fichiers :** 22 CSV `data/NBA_YYYY_Shots.csv`, ~850 Mo, schéma identique (26 colonnes).

## Chiffres clés

| Indicateur | Valeur |
|---|---|
| **Nombre de lignes (total 22 saisons)** | **4 450 789** |
| Nombre de colonnes | 26 |
| Matchs distincts (`GAME_ID`) | 26 453 |
| Joueurs distincts (`PLAYER_ID`) | 2 265 |
| Équipes distinctes (`TEAM_ID`) | 30 |
| Taux de réussite global (`SHOT_MADE`) | 45,8 % |
| Part de tirs à 3 points | 29,2 % (18,7 % en 2003‑04 → 42,1 % en 2024‑25) |
| Lignes en double (exactes) | 398 (0,009 %) |
| Cellules manquantes | `POSITION` / `POSITION_GROUP` uniquement — 219 527 `NULL` (toute la saison 2024‑25) + ~7 930 littéraux `"NA"` |

---

## Description des variables

**Légende « Disponibilité a priori »** : la variable est-elle connue **au moment du tir**, donc utilisable pour prédire `SHOT_MADE` en production ?
`Oui` = features candidates · `Non (fuite)` = connu seulement après le tir.

| N° | Nom de la colonne | Description | Dispo. a priori | Type | Taux de NA | Gestion des NA | Distribution des valeurs | Remarques |
|:---:|:---|:---|:---|:---|:---:|:---|:---|:---|
| 1 | `SEASON_1` | Année de fin de saison (2004 = saison 2003‑04) | Oui | int64 | 0 % | — | 22 modalités, 2004→2025 ; ~150 k–220 k lignes/saison | Redondant avec `SEASON_2`. Garder comme feature « effet époque ». |
| 2 | `SEASON_2` | Libellé de saison `AAAA-AA` | Oui | object | 0 % | — | 22 modalités, `2003-04`→`2024-25` | **Redondant** avec `SEASON_1` → à supprimer. |
| 3 | `TEAM_ID` | Identifiant de la franchise du tireur | Oui | int64 | 0 % | — | 30 modalités | Clé stable de la franchise. |
| 4 | `TEAM_NAME` | Nom de la franchise du tireur | Oui | object | 0 % | — | **36 modalités pour 30 `TEAM_ID`** | Renommages/relocations (Seattle→OKC, NJ→Brooklyn, Bobcats→Hornets, NO Hornets→Pelicans). Se rattacher à `TEAM_ID`. |
| 5 | `PLAYER_ID` | Identifiant du tireur | Oui | int64 | 0 % | — | 2 265 modalités | Clé joueur fiable. |
| 6 | `PLAYER_NAME` | Nom du tireur | Oui | object | 0 % | — | **2 286 modalités > 2 265 `PLAYER_ID`** | Variantes d'orthographe (accents, « Jr. »). Se rattacher à `PLAYER_ID`. |
| 7 | `POSITION_GROUP` | Poste agrégé : Guard / Forward / Center | Oui | object | **4,9 % `NULL` + 0,2 % `"NA"`** | Imputer via `PLAYER_ID` (saisons antérieures) ; sinon `"Unknown"` | `G` 42,9 % · `F` 36,8 % · `C` 15,2 % · `NULL` 4,9 % (⇒ **100 % de la saison 2024‑25**) · `"NA"` 0,2 % | NA **non aléatoires** : concentrés sur la dernière saison. |
| 8 | `POSITION` | Poste détaillé (PG, SG, SF, PF, C + combinés type `SG-PG`) | Oui | object | **4,9 % `NULL` + 0,2 % `"NA"`** | idem `POSITION_GROUP` | 18 modalités ; top : `SG` 22 % · `PG` 20 % · `PF` 19 % · `SF` 17 % · `C` 15 % | Fortement cardinalisé par les combos ; regrouper vers `POSITION_GROUP`. |
| 9 | `GAME_DATE` | Date du match | Oui | object (`MM-DD-YYYY`) | 0 % | — | 3 517 dates distinctes ; chaque saison ≈ fin oct. → mi‑avril | **Texte** → `pd.to_datetime(format="%m-%d-%Y")`. Absence de dates de playoffs = confirme périmètre saison régulière. |
| 10 | `GAME_ID` | Identifiant du match | Oui | int64 | 0 % | — | 26 453 modalités | ~1 230 matchs/saison (82 × 30 / 2), sauf saisons écourtées. |
| 11 | `HOME_TEAM` | Abréviation de l'équipe à domicile | Oui | object | 0 % | — | **34 modalités** | Abréviations non stables dans le temps (relocations). |
| 12 | `AWAY_TEAM` | Abréviation de l'équipe à l'extérieur | Oui | object | 0 % | — | **34 modalités** | Idem. Croiser avec `TEAM_NAME`/`TEAM_ID` pour dériver « tireur à domicile ». |
| 13 | `EVENT_TYPE` | `Made Shot` / `Missed Shot` | **Non (fuite)** | object | 0 % | — | `Missed` 54,2 % · `Made` 45,8 % | **Strictement équivalent à `SHOT_MADE`** (0 incohérence / 4,45 M) → supprimer. |
| 14 | `SHOT_MADE` | Tir réussi (booléen) — **variable cible** | **Non (cible)** | bool | 0 % | — | `True` 45,8 % · `False` 54,2 % | Cible du modèle. Classes quasi équilibrées. |
| 15 | `ACTION_TYPE` | Geste technique (Jump Shot, Driving Layup, Dunk…) | Oui | object | 0 % | — | **70 modalités**, très déséquilibrées : `Jump Shot` majoritaire, puis `Layup Shot`, `Driving Layup Shot`, `Pullup Jump Shot`, `Dunk Shot`… longue traîne de gestes rares | Très informatif mais forte cardinalité → regrouper (jump / layup / dunk / tip / hook / floater). |
| 16 | `SHOT_TYPE` | `2PT Field Goal` / `3PT Field Goal` | Oui | object | 0 % | — | `2PT` 70,8 % · `3PT` 29,2 % | Déductible des zones « 3 » et de la distance → redondant partiel. |
| 17 | `BASIC_ZONE` | Zone de tir (7) : Restricted Area, In The Paint (Non‑RA), Mid‑Range, Above the Break 3, Left/Right Corner 3, Backcourt | Oui | object | 0 % | — | `Restricted Area` 31,6 % · `Mid‑Range` 23,8 % · `Above the Break 3` 21,5 % · `Paint Non‑RA` 15,5 % · `L Corner 3` 3,9 % · `R Corner 3` 3,6 % · `Backcourt` 0,2 % | Bon compromis granularité/lisibilité pour la dataviz. |
| 18 | `ZONE_NAME` | Latéralité (6) : Center, Left/Right Side, Left/Right Side Center, Back Court | Oui | object | 0 % | — | `Center` 54,3 % · `L/R Side Center` ~11,8 % · `L/R Side` ~11 % · `Back Court` 0,2 % | 1:1 avec `ZONE_ABB`. |
| 19 | `ZONE_ABB` | Code latéralité : `C`, `LC`, `RC`, `L`, `R`, `BC` | Oui | object | 0 % | — | idem `ZONE_NAME` | **Redondant** avec `ZONE_NAME` → garder une seule. |
| 20 | `ZONE_RANGE` | Tranche de distance (5) : `Less Than 8 ft.`, `8-16 ft.`, `16-24 ft.`, `24+ ft.`, `Back Court Shot` | Oui | object | 0 % | — | `<8 ft` 41,0 % · `24+ ft` 28,9 % · `16‑24 ft` 15,6 % · `8‑16 ft` 14,2 % · `Back Court` 0,2 % | Discrétisation de `SHOT_DISTANCE`. |
| 21 | `LOC_X` | Coordonnée latérale (ft), 0 = axe du panier | Oui | float64 | 0 % | Voir §rupture de collecte | min −25 · max 25 · symétrique autour de 0 | 951 valeurs distinctes (arrondi 0,05). **Imputé à 0 pour les tirs au cercle des saisons ≤ 2010.** |
| 22 | `LOC_Y` | Coordonnée longitudinale (ft), 0 = ligne de fond, panier ≈ 5,25 | Oui | float64 | 0 % | Voir §rupture de collecte | min 0,05 · max 93,65 (heaves plein terrain) | 1 696 valeurs distinctes. **Imputé à ~5,25 pour les tirs au cercle des saisons ≤ 2010.** |
| 23 | `SHOT_DISTANCE` | Distance du tir au panier (ft, entier) | Oui | int64 | 0 % | Voir §rupture de collecte | min 0 · max 89 · moy 12,63 · méd 13 · σ 10,16 · **distribution bimodale** | **`= 0` sur 14,2 % des lignes** ; part passant de ~26 % (≤ 2010) à ~8 % (≥ 2011) → **non comparable dans le temps**. |
| 24 | `QUARTER` | Quart‑temps ; 5‑8 = prolongations | Oui | int64 | 0 % | — | `1` 26,1 % · `2` 25,0 % · `3` 24,6 % · `4` 23,7 % · `5‑8` (OT) 0,7 % | Cohérent. |
| 25 | `MINS_LEFT` | Minutes restantes dans le quart‑temps | Oui | int64 | 0 % | — | 0 → 12 | Combiner avec `SECS_LEFT` → `temps_restant_s = MINS_LEFT*60 + SECS_LEFT`. |
| 26 | `SECS_LEFT` | Secondes restantes dans la minute courante | Oui | int64 | 0 % | — | 0 → 59 | idem. |

---

## Contrôles de cohérence effectués

| Contrôle | Résultat |
|---|---|
| `EVENT_TYPE = 'Made Shot'` ⇔ `SHOT_MADE = True` | **0 incohérence** / 4 450 789 |
| `HOME_TEAM = AWAY_TEAM` | 0 |
| `LOC_X` / `LOC_Y` hors terrain (|X|>25, Y<0 ou Y>94) | 0 |
| Corrélation `SHOT_DISTANCE` ↔ distance euclidienne calculée depuis `(LOC_X, LOC_Y)` | **0,82** (MAE ≈ 2,3 ft) — cohérent mais bruité (arrondi + rupture de collecte) |
| `SHOT_TYPE = '3PT'` avec `SHOT_DISTANCE < 22 ft` | 459 (0,04 % des 3 pts) — tirs de coin limites, tolérable |
| `SHOT_TYPE = '2PT'` avec `SHOT_DISTANCE > 23 ft` | 50 — négligeable |
| Nombre de matchs par saison ≈ 1 230 | Écarts attendus : 1 189 (2003‑04, 29 équipes), 990 (lockout 2011‑12), 1 059 / 1 076 (COVID 2019‑20 / 2020‑21) |

---

## Difficultés & biais (synthèse pour l'étape 2)

| # | Constat | Sévérité | Traitement retenu |
|---|---|---|---|
| 1 | **Rupture de méthode de collecte** des coordonnées : `SHOT_DISTANCE = 0` / `LOC = (0 ; 5.25)` sur ~26 % des tirs jusqu'en 2009‑10, ~8 % ensuite | 🔴 Élevée | Indicateur `coord_fiable` ; analyse spatiale restreinte à 2011+ ; ou recalcul de la distance depuis `LOC` |
| 2 | `POSITION` / `POSITION_GROUP` **absents sur toute la saison 2024‑25** + littéral `"NA"` (anciennes saisons) | 🟠 Moyenne | Imputation par `PLAYER_ID` (poste quasi stable) ; sinon `"Unknown"`. Ne **pas** supprimer les lignes |
| 3 | **Non‑stationnarité** du jeu : part de 3 pts ×2, distance et FG% en évolution | 🟠 Moyenne | `SEASON_1` en feature ; envisager un split train/test temporel |
| 4 | Colonnes **redondantes** : `EVENT_TYPE`=`SHOT_MADE`, `ZONE_NAME`=`ZONE_ABB`, `SEASON_1`=`SEASON_2` | 🟢 Faible | Supprimer les doublons |
| 5 | **Saisons écourtées** (2011‑12, 2019‑20, 2020‑21) → volumes hétérogènes | 🟢 Faible | Raisonner en taux, pas en volumes bruts |
| 6 | **398 doublons exacts** (doubles saisies de la table de marque) | 🟢 Faible | `drop_duplicates()` |
| 7 | **Aucune variable domicile/extérieur pour le tireur**, ni score courant du match | 🟠 Moyenne | Dériver « équipe du tireur = équipe à domicile » via mapping `TEAM_ID`/`TEAM_NAME` ↔ abréviation |
| 8 | `PLAYER_NAME` (2 286) > `PLAYER_ID` (2 265) : variantes d'orthographe | 🟢 Faible | Clé = `PLAYER_ID` uniquement |
| 9 | `GAME_DATE` au format texte `MM-DD-YYYY` ; périmètre = **saison régulière seule** | 🟢 Faible | Parsing datetime ; en tenir compte dans l'interprétation |

---

## Data Visualisation

Voir `eda.ipynb` (section 10) — 6 représentations, chacune avec commentaire métier et validation statistique :

1. **Révolution du 3‑points** (2003‑04 → 2024‑25) — régression linéaire : +1,20 pt/an, R² = 0,94, p ≈ 1,4·10⁻¹³.
2. **Shot chart** (densité `LOC_X`/`LOC_Y`, saison 2024‑25) — polarisation cercle / arc à 3 pts ; χ² d'ajustement.
3. **Efficacité vs distance** (FG% et espérance de points par tranche) — le long 2 est économiquement dominé.
4. **Corner 3 vs above‑the‑break 3** — 38,7 % vs 35,2 %, χ² ≈ 1 357, p ≈ 5·10⁻²⁹⁷.
5. **Clutch time** — FG% −2,2 pts, part de 3 pts +5 pts ; test de deux proportions, z ≈ −29, p ≈ 3·10⁻¹⁹⁰.
6. **Profil de tir par poste** — Centres 52,2 % près du cercle vs Arrières 43,4 % à longue distance ; χ² ≈ 15 800 (ddl = 2).
