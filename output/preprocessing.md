# 🏀 NBA Shot Analysis — Pre-processing (étape 2)

Notebook : `src/preprocessing.ipynb` · Entrée : `data/NBA_2004_2025_Shots.csv.zip` · Sorties : `data/processed/shots_clean_2015_2025.parquet`, `data/processed/shots_encoded_2015_2025.parquet`

## Objectif

Transformer la table brute (22 saisons, 4 450 789 tirs, 26 colonnes) en une table prête pour un **modèle de qualité du tir** : probabilité de réussite estimée à partir du contexte du tir (position, geste, temps, poste du tireur), entraînée sur toute la ligue, appliquée ensuite joueur par joueur. Conformément au cadrage du 1er octobre : fenêtre 2015-16 → 2024-25, identité du joueur hors des variables d'entrée, découpage train / validation / test par saison.

## Réconciliation des effectifs

| Étape | Lignes retirées | Lignes restantes | Justification |
|---|---:|---:|---|
| Table brute | — | 4 450 789 | EDA (Tristan) |
| Saisons < 2015-16 | 2 350 533 | 2 100 256 | basket moderne (part de 3 pts × 2 depuis 2013) ; sort la rupture de collecte des coordonnées ≤ 2010 |
| Doublons exacts | 98 | 2 100 158 | doubles saisies de la table de marque (même joueur, même seconde, mêmes coordonnées) |
| Tirs Backcourt (42-88 ft, 2,3 % de réussite) + 81 « No Shot » | 4 520 | **2 095 638** | désespoirs de fin de quart-temps, événements sans geste |

## Colonnes supprimées

| Colonne | Raison |
|---|---|
| `EVENT_TYPE` | **Fuite** : strictement équivalent à la cible `SHOT_MADE` (0 incohérence) |
| `SEASON_2` | redondant avec `SEASON_1` |
| `ZONE_ABB` | redondant avec `ZONE_NAME` (correspondance 1:1 vérifiée) |
| `POSITION` | 18 modalités, résumées par `POSITION_GROUP` |
| `MINS_LEFT`, `SECS_LEFT` | remplacées par `temps_restant_qt` |

## Conversions

| Colonne | Avant | Après |
|---|---|---|
| `SHOT_MADE` | bool | int 0/1 (cible) |
| `GAME_DATE` | texte `MM-DD-YYYY` | datetime |
| `SHOT_TYPE` | texte | `tir_3pts` 0/1 (`SHOT_TYPE` conservé en contexte) |

## Variables créées (toutes connues au moment du tir)

| Variable | Construction | Signal observé |
|---|---|---|
| `saison_debut` | `SEASON_1 − 1` | 2015 → 2024 |
| `temps_restant_qt` | `MINS_LEFT × 60 + SECS_LEFT` (s) | — |
| `temps_restant_match` | `(4 − QUARTER) × 720 + temps_restant_qt` ; = `temps_restant_qt` en prolongation | dernière minute Q4/OT : 42,0 % vs 46,6 % |
| `prolongation` | `QUARTER ≥ 5` | 0,6 % des tirs |
| `type_geste` | 53 `ACTION_TYPE` → Dunk / Layup / Floater / Hook / Jump shot | 89,4 / 56,0 / 45,2 / 48,2 / 37,8 % |
| `en_course` | libellé contient *driving / running / cutting* | 58,2 % vs 41,8 % |
| `en_desequilibre` | *pullup / step back / fadeaway / turnaround* | 42,2 % vs 47,6 % |
| `seconde_chance` | *tip / putback* | 60,4 % vs 45,9 % |
| `alley_oop` | *alley oop* | 81,2 % |
| `tireur_domicile` | abréviation de l'équipe reconstruite par saison (celle présente dans 100 % de ses matchs), comparée à `HOME_TEAM` ; vérifié sur 300 équipes-saisons, 0 ambiguïté | 46,9 % vs 46,0 % |
| `POSITION_GROUP` imputé | dernier poste connu du joueur ; `Inconnu` pour 117 rookies 2024-25 (21 836 tirs) | C 54,3 % · F 46,2 % · G 43,9 % |
| `LOC_X`, `LOC_Y` corrigés | × 10 (et − 52,5 sur Y) sur les saisons 2019-20, 2020-21, 2021-22 | voir ci-dessous |

## Difficulté découverte : coordonnées à la mauvaise échelle sur trois saisons

Sur **2019-20, 2020-21 et 2021-22**, `LOC_X` / `LOC_Y` sont environ 10 fois trop petites par rapport aux autres saisons (distance recalculée 8,3 fois inférieure à `SHOT_DISTANCE`, sur 100 % des matchs de ces saisons). Tout indique une conversion d'unités appliquée deux fois à la source. Le contrôle « coordonnées hors terrain = 0 » de l'EDA ne pouvait pas le détecter.

| Indicateur | Avant correction | Après correction |
|---|---|---|
| Corrélation distance recalculée ↔ `SHOT_DISTANCE` | 0,736 | 0,9996 |
| Écart absolu moyen | 3,69 ft | 0,48 ft |
| Tirs avec écart > 3 ft | 19,7 % | 0,0 % |
| `SHOT_DISTANCE` = partie entière de la distance recalculée | — | 99,8 % |

Conséquence : toute carte de tir ou densité spatiale sur ces trois saisons sans correction est fausse. `SHOT_DISTANCE` et `BASIC_ZONE` ne sont pas touchés.

## Table finale

**2 095 638 tirs × 31 colonnes + `split`**, 0 valeur manquante.

| Famille | Colonnes |
|---|---|
| Identifiants & contexte (jamais en entrée du modèle) | `saison_debut`, `SEASON_1`, `GAME_ID`, `GAME_DATE`, `TEAM_ID`, `TEAM_NAME`, `PLAYER_ID`, `PLAYER_NAME`, `HOME_TEAM`, `AWAY_TEAM`, `ACTION_TYPE`, `SHOT_TYPE`, `ZONE_NAME`, `ZONE_RANGE` |
| Variables d'entrée numériques | `SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `tir_3pts`, `QUARTER`, `prolongation`, `temps_restant_qt`, `temps_restant_match`, `tireur_domicile`, `en_course`, `en_desequilibre`, `seconde_chance`, `alley_oop` |
| Variables d'entrée catégorielles (one-hot → 15 colonnes) | `BASIC_ZONE` (6), `type_geste` (5), `POSITION_GROUP` (4) |
| Cible | `SHOT_MADE` |

**28 variables d'entrée** après encodage. Pas de standardisation à ce stade (dépend du modèle, à ajuster sur `train` uniquement).

## Découpage temporel

| Jeu | Saisons | Tirs | Réussite | Part 3 pts |
|---|---|---:|---:|---:|
| `train` | 2015-16 → 2022-23 | 1 658 384 | 46,3 % | 35,6 % |
| `validation` | 2023-24 | 218 254 | 47,5 % | 39,4 % |
| `test` | 2024-25 | 219 000 | 46,8 % | 42,0 % |

Baseline à battre : prédire ~46 % pour tout tir (moyenne de `train`).

## Notes pratiques

- Le zip contient un fichier parasite `__MACOSX/…` : le notebook sélectionne explicitement le membre `.csv`.
- Le fichier source 2024-25 n'a que 24 colonnes (pas de `POSITION` / `POSITION_GROUP`) : d'où les 219 527 postes manquants de l'EDA.
- Chargement complet ≈ 2,5 Go de RAM, 15 à 60 s ; la table complète est libérée dès le filtre de saison.
- Sorties en Parquet (pyarrow) ; repli automatique en CSV si pyarrow est absent.
