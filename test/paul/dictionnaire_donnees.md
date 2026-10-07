# Dictionnaire des données : `shots_model.parquet`

Ce fichier décrit, colonne par colonne, le dataset prêt pour la modélisation : **1 ligne = 1 tir**, 2 099 311 tirs, saisons 2015-16 à 2024-25, 45 colonnes.

Pour chaque colonne, j'indique ce qu'elle contient, d'où elle vient et sa valeur sur un exemple.

- **« Fichier d'origine »** : colonne présente dans les CSV de départ, éventuellement nettoyée.
- **« Calculée »** : colonne que j'ai créée, à partir d'autres colonnes.

## Le tir pris en exemple

Stephen Curry (Golden State) reçoit les New Orleans Pelicans le 27 octobre 2015, match d'ouverture de la saison. Au 1er quart-temps, il reste 9 min 13 s : il prend son 4e tir du match, un tir en suspension à 3 points depuis l'aile, à 27,6 pieds du panier. **Il le met.**

---

## 1. Identifiants : qui, quand, quel match

Ils servent à retrouver et à regrouper les tirs. **Ils ne sont jamais donnés au modèle.**

| Colonne | Ce que c'est | D'où ça vient | Exemple |
|---|---|---|---|
| `GAME_ID` | Numéro unique du match | Fichier d'origine | 21500003 |
| `PLAYER_ID` | Numéro unique du joueur. C'est lui que j'utilise pour relier les tables, jamais le nom. | Fichier d'origine | 201939 |
| `PLAYER_NAME` | Nom du joueur, sans accents | Fichier d'origine, accents retirés (Jokić devient Jokic) | Stephen Curry |
| `TEAM_ID` | Numéro unique de l'équipe du tireur | Fichier d'origine | 1610612744 |
| `SEASON_1` | Saison, notée par son **année de fin** : 2016 = saison 2015-16 | Fichier d'origine | 2016 |
| `GAME_DATE` | Date du match | Fichier d'origine, texte converti en date | 2015-10-27 |

## 2. Drapeaux : pour filtrer facilement

Des colonnes vrai / faux pour sélectionner une partie des tirs. **Pas données au modèle.**

| Colonne | Ce que c'est | D'où ça vient | Exemple |
|---|---|---|---|
| `joueur_projet` | Le tireur fait partie des 11 joueurs étudiés (top 25 ESPN, actif en 2024-25, au moins 5 saisons et 5 000 tirs) | Calculée par une règle, voir `config.py` | vrai |
| `espn_top25` | Le tireur fait partie du classement ESPN des 25 meilleurs joueurs du 21e siècle, retenu ou non | Calculée : liste dans `config.py` | vrai |
| `actif_2024_25` | Le tireur a joué en 2024-25 (encore actif) | Calculée : le joueur a des tirs en 2024-25 | vrai |
| `coord_corrigee` | La position du tir a été corrigée (saisons 2019-20 à 2021-22 : échelle divisée par 10 et côté gauche/droite inversé dans le fichier) | Calculée par le nettoyage | faux |
| `split` | Groupe du tir : `train` (70 %), `val` (15 %) ou `test` (15 %). Tous les tirs d'un même match sont dans le même groupe. | Calculée à partir de `GAME_ID` | train |
| `split_temps` | Autre découpage, par saison : `train` de 2015-16 à 2022-23, `val` 2023-24, `test` 2024-25 | Calculée à partir de `SEASON_1` | train |

## 3. Où le tir est pris

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `LOC_X` | Position gauche / droite, en pieds. 0 = milieu du terrain. | Fichier d'origine (corrigée sur 3 saisons) | −25 à 25 | 19,7 |
| `LOC_Y` | Distance depuis la ligne de fond, en pieds. Le panier est à 5,25. | Fichier d'origine (corrigée sur 3 saisons) | 0 à 93 | 24,55 |
| `distance_ft` | Distance exacte au panier, en pieds | **Calculée** : Pythagore, √(LOC_X² + (LOC_Y − 5,25)²) | 0 à 90 | 27,6 |
| `angle_deg` | Angle par rapport à l'axe du panier, en degrés. 0° = face au panier, 90° = dans le corner. | **Calculée** : trigonométrie, arctan(\|LOC_X\| / (LOC_Y − 5,25)) | 0 à 180 | 45,6 |
| `BASIC_ZONE` | Zone du terrain | Fichier d'origine | 7 zones : Restricted Area (sous le panier), In The Paint (raquette), Mid-Range (mi-distance), Above the Break 3, Left Corner 3, Right Corner 3, Backcourt | Above the Break 3 |
| `tir_3pts` | 1 si tir à 3 points | **Calculée** à partir de `SHOT_TYPE` | 0 ou 1 | 1 |
| `tir_backcourt` | 1 si tir pris depuis son propre camp (tir désespéré) | **Calculée** à partir de `BASIC_ZONE` | 0 ou 1 | 0 |

**Exemple de calcul, sur le tir de Curry :** écart horizontal = 19,7 ; écart vertical = 24,55 − 5,25 = 19,3. Distance = √(19,7² + 19,3²) = 27,6 pieds. Angle = arctan(19,7 / 19,3) = 45,6°, soit un tir pris en diagonale, sur l'aile.

## 4. Comment le tir est pris

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `ACTION_TYPE` | Geste détaillé, tel que noté par la NBA | Fichier d'origine | 52 libellés (« Jump Shot », « Driving Layup Shot »...) | Jump Shot |
| `geste_famille` | Famille de geste | **Calculée** : les libellés regroupés en 6 familles | `dunk`, `layup`, `tip_putback` (claquette, rebond remis), `hook` (bras roulé), `jump_cree` (tir créé : pull-up, step back, fadeaway...), `jump_simple` (tir en suspension classique) | jump_simple |
| `tir_planche` | 1 si le tir est joué contre la planche | **Calculée** : le libellé contient « Bank » | 0 ou 1 | 0 |
| `en_course` | 1 si le tir est pris en mouvement vers le panier (« Driving », « Running », « Cutting ») | **Calculée** à partir du libellé | 0 ou 1 | 0 |
| `en_desequilibre` | 1 si le tir est pris en déséquilibre (« Pullup », « Step Back », « Fadeaway », « Turnaround ») | **Calculée** à partir du libellé | 0 ou 1 | 0 |
| `alley_oop` | 1 si le tir finit une passe en l'air (« Alley Oop ») | **Calculée** à partir du libellé | 0 ou 1 | 0 |

## 5. Quand le tir est pris

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `QUARTER` | Quart-temps. 5 et plus = prolongation. | Fichier d'origine | 1 à 8 | 1 |
| `temps_restant_periode_s` | Secondes restantes dans le quart-temps | **Calculée** : minutes × 60 + secondes | 0 à 720 | 553 (9 min 13 s) |
| `temps_ecoule_match_s` | Secondes de jeu écoulées depuis le début du match | **Calculée** à partir du quart-temps et du temps restant | 0 à 4 079 | 167 (2 min 47 s de jeu) |
| `fin_de_periode` | 1 si le tir est pris dans les 3 dernières secondes du quart-temps (tir au buzzer) | **Calculée** : `temps_restant_periode_s` ≤ 3 | 0 ou 1 | 0 |
| `derniere_minute` | 1 si le tir est pris dans la dernière minute du 4e quart-temps ou d'une prolongation | **Calculée** : `QUARTER` ≥ 4 et `temps_restant_periode_s` ≤ 60 | 0 ou 1 | 0 |
| `prolongation` | 1 si le tir est pris en prolongation | **Calculée** : `QUARTER` ≥ 5 | 0 ou 1 | 0 |

## 6. Dans quel contexte

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `domicile` | 1 si l'équipe du tireur joue chez elle | **Calculée** : je compare l'équipe du tireur à l'équipe qui reçoit | 0 ou 1 | 1 |
| `equipe` | Abréviation de l'équipe du tireur | **Calculée** à partir de `TEAM_ID` | 30 abréviations | GSW |
| `adversaire` | Abréviation de l'équipe adverse | **Calculée** : l'autre équipe du match | 30 abréviations | NOP |
| `jours_repos` | Jours sans match avant celui-ci, pour l'équipe. Plafonné à 7. | **Calculée** à partir du calendrier des matchs | 0 à 7 | 7 (premier match de la saison) |
| `back_to_back` | 1 si l'équipe a joué la veille | **Calculée** : `jours_repos` = 0 | 0 ou 1 | 0 |
| `premier_match_saison` | 1 si c'est le premier match de la saison de l'équipe | **Calculée** à partir du calendrier | 0 ou 1 | 1 |

## 7. Qui tire, et comment se passe son match

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `POSITION_GROUP` | Grand poste : G (arrière), F (ailier), C (pivot)... | Fichier d'origine. Vide en 2024-25 : complété avec le dernier poste connu du joueur. | 5 valeurs, dont `Inconnu` pour les recrues de 2024-25 | G |
| `POSITION` | Poste précis : PG (meneur), SG, SF, PF, C... | Fichier d'origine, complété comme ci-dessus | 18 valeurs | PG |
| `saisons_depuis_premiere_apparition` | Nombre de saisons depuis la première saison du joueur dans le CSV complet (depuis 2003-04, pas seulement depuis 2015-16) | **Calculée** | 0 à 21 | 6 (Curry apparaît en 2009-10) |
| `experience_censuree` | 1 si le joueur était déjà en NBA avant le début des données (2003-04) : son expérience réelle est alors plus grande que la colonne précédente | **Calculée** | 0 ou 1 | 0 |
| `tirs_deja_pris` | Nombre de tirs déjà pris par le joueur dans ce match, **avant** ce tir | **Calculée** | 0 à 49 | 3 |
| `premier_tir_match` | 1 si c'est le premier tir du joueur dans le match | **Calculée** : `tirs_deja_pris` = 0 | 0 ou 1 | 0 |
| `reussite_tirs_precedents` | Part de réussite sur ses 3 derniers tirs du match, **avant** ce tir. Vide pour son premier tir (rien à mesurer). | **Calculée** | 0 à 1, ou vide | 0,33 (1 réussi sur ses 3 précédents) |

## 8. Ce que je cherche à prédire

| Colonne | Ce que c'est | D'où ça vient | Valeurs possibles | Exemple |
|---|---|---|---|---|
| `cible` | **1 si le tir est réussi**, 0 s'il est raté | Fichier d'origine (`SHOT_MADE`, converti en 0 / 1) | 0 ou 1 | 1 |

---

## Règles importantes

- **Les features sont les 32 colonnes des sections 3 à 7.** Après sélection, le modèle n'en utilise que 12 (`FEATURES_RETENUES` dans `model_features.py`) : les autres sont redondantes pour la prédiction, mais servent à l'analyse par situation de jeu. Les identifiants, les drapeaux et la cible n'en font pas partie : la liste exacte est dans `preprocessing/model_features.py`.
- **Aucune colonne ne connaît le résultat du tir**, ni ce qui se passe après lui. Par exemple, `reussite_tirs_precedents` ne regarde que les tirs **précédents**.
- **Colonne supprimée partout :** `EVENT_TYPE` (« Made Shot » / « Missed Shot ») recopie le résultat du tir et aurait permis au modèle de tricher.

---

## Le second fichier : `shots_clean.parquet`

Il contient **les mêmes 2 099 311 tirs**, avec les 45 colonnes ci-dessus plus 14 colonnes brutes ou de contrôle, qui ne sont pas données au modèle :

| Colonne | Ce que c'est | D'où ça vient | Exemple |
|---|---|---|---|
| `coord_fiable` | Vrai si la position exacte du tir est fiable (saisons 2010-11 et suivantes). Toujours vrai dans la fenêtre de 10 saisons : gardée pour documenter le choix. | Calculée à partir de `SEASON_1` | vrai |
| `SEASON_2` | Saison en toutes lettres | Fichier d'origine | 2015-16 |
| `TEAM_NAME` | Nom complet de l'équipe du tireur | Fichier d'origine | Golden State Warriors |
| `HOME_TEAM`, `AWAY_TEAM` | Abréviations de l'équipe qui reçoit et de l'équipe qui se déplace. Ont servi à calculer `domicile`. | Fichier d'origine | GSW, NOP |
| `SHOT_TYPE` | « 2PT Field Goal » ou « 3PT Field Goal ». A servi à calculer `tir_3pts`. | Fichier d'origine | 3PT Field Goal |
| `SHOT_DISTANCE` | Distance au panier **arrondie au pied inférieur**. Remplacée dans le modèle par `distance_ft`, plus précise. | Fichier d'origine | 27 |
| `ZONE_NAME`, `ZONE_ABB` | Côté du terrain (gauche, centre, droite) et son abréviation | Fichier d'origine | Left Side Center, LC |
| `ZONE_RANGE` | Tranche de distance (moins de 8 ft, 8-16 ft, 16-24 ft, 24 ft et plus) | Fichier d'origine | 24+ ft. |
| `MINS_LEFT`, `SECS_LEFT` | Minutes et secondes restantes. Ont servi à calculer `temps_restant_periode_s`. | Fichier d'origine | 9, 13 |
| `doublon_plausible` | Vrai pour les 151 tirs en double conservés (tips et putbacks, possibles deux fois dans la même seconde) | Calculée par le nettoyage | faux |
| `position_imputee` | Vrai si le poste du joueur a été complété (saison 2024-25) | Calculée par le nettoyage | faux |

Ces colonnes sont exclues du modèle parce qu'elles sont redondantes avec des features plus précises (`SHOT_DISTANCE` avec `distance_ft`, `ZONE_RANGE` avec `distance_ft`, `SHOT_TYPE` avec `tir_3pts`), ou parce qu'elles ne servent qu'au contrôle qualité.
