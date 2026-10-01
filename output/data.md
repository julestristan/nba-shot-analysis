# COLONNES

## Description des variables

| N° | Nom de la colonne | Description | Dispo. a priori | Type | Taux de NA | Gestion des NA | Distribution des valeurs | Remarques |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | :--- | :--- |
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

## Chiffres clés

| Indicateur | Valeur |
| :--- | :--- |
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

## Redondance

| Redondance | Détail | Action étape 2 |
| :--- | :--- | :--- |
| `EVENT_TYPE` ↔ `SHOT_MADE` | **0 incohérence** sur 4,45 M lignes → strictement équivalents | garder `SHOT_MADE`, supprimer `EVENT_TYPE` |
| `ZONE_NAME` ↔ `ZONE_ABB` | correspondance 1:1 (autant de paires que de modalités) | garder une seule |
| `SEASON_1` ↔ `SEASON_2` | même info, formats différents | garder `SEASON_1` (int) |
| `BASIC_ZONE` / `ZONE_RANGE` / `ZONE_NAME` | hiérarchie spatiale corrélée à `LOC_X/Y` et `SHOT_DISTANCE` | choisir *soit* les zones *soit* les coordonnées |
| `SHOT_TYPE` | déductible des zones « 3 » et de la distance | redondant partiel |

---

## Valeurs manquantes

| Variable | n_null | n_literal_NA | taux_% |
| :--- | :---: | :---: | :---: |
| **POSITION_GROUP** | 219 527 | 7 930 | 5,11 |
| **POSITION** | 219 527 | 7 930 | 5,11 |

<br>

| Idx | SEASON_2 | n_tirs | pos_null | pos_literal_na |
| :---: | :---: | :---: | :---: | :---: |
| 0 | 2003-04 | 189 803 | 0 | 0 |
| 1 | 2004-05 | 197 626 | 0 | 0 |
| 2 | 2005-06 | 194 314 | 0 | 0 |
| 3 | 2006-07 | 196 072 | 0 | 0 |
| 4 | 2007-08 | 200 501 | 0 | 0 |
| 5 | 2008-09 | 199 030 | 0 | 0 |
| 6 | 2009-10 | 200 966 | 0 | 0 |
| 7 | 2010-11 | 199 761 | 0 | 0 |
| 8 | 2011-12 | 161 205 | 0 | 0 |
| 9 | 2012-13 | 201 579 | 0 | 399 |
| 10 | 2013-14 | 204 126 | 0 | 364 |
| 11 | 2014-15 | 205 550 | 0 | 114 |
| 12 | 2015-16 | 207 893 | 0 | 0 |
| 13 | 2016-17 | 209 929 | 0 | 0 |
| 14 | 2017-18 | 211 707 | 0 | 484 |
| 15 | 2018-19 | 219 458 | 0 | 686 |
| 16 | 2019-20 | 188 116 | 0 | 857 |
| 17 | 2020-21 | 190 983 | 0 | 1 244 |
| 18 | 2021-22 | 216 722 | 0 | 1 087 |
| 19 | 2022-23 | 217 220 | 0 | 1 431 |
| 20 | 2023-24 | 218 701 | 0 | 1 264 |
| 21 | 2024-25 | 219 527 | 219 527 | 0 |

---

## Données dupliquées

| lignes_en_double | total |
| :---: | :---: |
| 398 | 4 450 789 |

---

## Remarques et analyses

- **LOC=0 à travers les années**  
  Les points près du panier sont finement traqués à partir de 2011.  
  ![Tirs distance 0](./tirs_distance_0.png)

- **Pas de POSITION / POSITION_GROUP pour 2024/2025**
- **Saisons écourtées**
- **Pas de variable HOME / EXT pour le tireur**
- **Pas de shot clock**

- **Distribution des tirs**  
  La distribution de la distance des tirs semble cohérente sur la durée :  
  ![Distribution 2007](./distribution_shot_distance_2007.png)  
  ![Distribution 2025](./distribution_shot_distance_2025.png)
