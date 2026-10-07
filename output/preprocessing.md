# 🏀 NBA Shot Analysis — Pre-processing (étape 2)

Notebook : `notebooks/02_preprocessing.ipynb` · Entrée : les 22 zips de saison `data/shots_04_25/NBA_YYYY_Shots.csv.zip` (dépôt GitHub DomSamangy/NBA_Shots_04_25) · Sorties : `data/processed/shots_clean_2015_2025.parquet`, `data/processed/shots_encoded_2015_2025.parquet` · Démarche complète : `output/synthese_demarche.md`

## Objectif

Transformer la table brute (22 saisons, 4 450 789 tirs, 26 colonnes) en une table prête pour un **modèle de qualité du tir** : probabilité de réussite estimée à partir du contexte du tir (position, geste, temps, poste du tireur, domicile), entraînée sur toute la ligue, appliquée ensuite joueur par joueur. Conformément au cadrage du 1er octobre : fenêtre 2015-16 → 2024-25, identité du joueur hors des variables d'entrée, découpage train / validation / test par saison.

## Réconciliation des effectifs

| Étape | Lignes retirées | Lignes restantes | Justification |
|---|---:|---:|---|
| Table brute (22 fichiers assemblés par nom de colonne) | — | 4 450 789 | EDA (Tristan) — 5 contrôles automatiques passés |
| Saisons < 2015-16 | 2 350 533 | 2 100 256 | basket moderne (part de 3 pts × 2 depuis 2013) ; sort la rupture de collecte des coordonnées ≤ 2010 |
| Doublons exacts | 98 | 2 100 158 | doubles saisies (même joueur, même seconde, mêmes coordonnées) |
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
| `shot_id` | numéro de ligne après tri chronologique — la clé naturelle (match, quart-temps, seconde, joueur) a 1 591 collisions | clé unique commune aux deux fichiers |
| `saison_debut` | `SEASON_1 − 1` | 2015 → 2024 |
| `temps_restant_qt` | `MINS_LEFT × 60 + SECS_LEFT` (s) | — |
| `temps_restant_match` | `(4 − QUARTER) × 720 + temps_restant_qt` ; = `temps_restant_qt` en prolongation | dernière minute Q4/OT : 42,0 % vs 46,6 % |
| `prolongation` | `QUARTER ≥ 5` | 0,6 % des tirs |
| `type_geste` | 53 `ACTION_TYPE` → Dunk / Layup / Floater / Hook / Jump shot | 89,4 / 56,0 / 45,2 / 48,2 / 37,8 % |
| `tireur_domicile` | abréviation de l'équipe reconstruite par saison (celle présente dans 100 % de ses matchs), comparée à `HOME_TEAM` ; vérifié sur 300 équipes-saisons, 0 ambiguïté | 46,9 % vs 46,0 % |
| `POSITION_GROUP` imputé | dernier poste connu du joueur ; `Inconnu` pour 117 rookies 2024-25 (21 836 tirs) | C 54,3 % · F 46,2 % · G 43,9 % |
| `LOC_X`, `LOC_Y` corrigés | × 10 (et − 52,5 sur Y) sur les saisons 2019-20, 2020-21, 2021-22 | voir ci-dessous |

## Qualificatifs du libellé : testés, puis écartés (section 4.2 bis)

Les qualificatifs d'`ACTION_TYPE` (*driving / running / cutting*, *pullup / step back / fadeaway / turnaround*, *tip / putback*, *alley oop*) auraient pu devenir quatre indicateurs 0/1. On a mesuré, sur les saisons du futur `train`, leur écart de réussite **à famille de geste et distance égales** (cases `type_geste` × tranche de `SHOT_DISTANCE`, pondération de Mantel-Haenszel) :

| Indicateur candidat | Tirs concernés | Écart brut | Écart à geste et distance égaux |
|---|---:|---:|---:|
| en_course | 435 666 | +17,5 pts | +7,6 pts |
| en_desequilibre | 332 099 | −4,1 pts | **+6,4 pts** |
| seconde_chance | 65 049 | +14,9 pts | **−6,1 pts** |
| alley_oop | 22 866 | +35,1 pts | +2,7 pts |

Deux signes s'inversent : les écarts bruts sont des effets de composition. Un test prédictif (même modèle entraîné avec et sans ces quatre colonnes, évalué sur `validation`) ne montre aucun gain, alors que retirer `type_geste` dégrade nettement le score. **Décision : ces variables ne sont pas créées.** `ACTION_TYPE` reste dans la table lisible, l'hypothèse pourra être re-testée à l'étape optimisation.

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

**2 095 638 tirs × 28 colonnes + `split`**, 0 valeur manquante.

| Famille | Colonnes |
|---|---|
| Identifiants & contexte (jamais en entrée du modèle) | `shot_id`, `saison_debut`, `SEASON_1`, `GAME_ID`, `GAME_DATE`, `TEAM_ID`, `TEAM_NAME`, `PLAYER_ID`, `PLAYER_NAME`, `HOME_TEAM`, `AWAY_TEAM`, `ACTION_TYPE`, `SHOT_TYPE`, `ZONE_NAME`, `ZONE_RANGE` |
| Variables d'entrée numériques | `SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `tir_3pts`, `QUARTER`, `prolongation`, `temps_restant_qt`, `temps_restant_match`, `tireur_domicile` |
| Variables d'entrée catégorielles (one-hot → 15 colonnes) | `BASIC_ZONE` (6), `type_geste` (5), `POSITION_GROUP` (4) |
| Cible | `SHOT_MADE` |

**24 variables d'entrée** après encodage one-hot (`pd.get_dummies`). Pas de standardisation à ce stade (dépend du modèle, à ajuster sur `train` uniquement).

## Découpage temporel

| Jeu | Saisons | Tirs | Réussite | Part 3 pts |
|---|---|---:|---:|---:|
| `train` | 2015-16 → 2022-23 | 1 658 384 | 46,3 % | 35,6 % |
| `validation` | 2023-24 | 218 254 | 47,5 % | 39,4 % |
| `test` | 2024-25 | 219 000 | 46,8 % | 42,0 % |

Baseline à battre : prédire ~46 % pour tout tir (moyenne de `train`).

## Fichiers produits

| Fichier | Contenu | Taille |
|---|---|---|
| `shots_clean_2015_2025.parquet` | table lisible (libellés en clair), 29 colonnes | 35,3 Mo |
| `shots_encoded_2015_2025.parquet` | `shot_id`, `saison_debut`, `GAME_ID`, `PLAYER_ID`, `split`, cible + 24 variables 0/1 ou numériques, 30 colonnes | 28,5 Mo |

## Notes pratiques

- Chaque zip de saison contient un fichier parasite `__MACOSX/…` : le notebook sélectionne explicitement le membre `.csv`.
- Le fichier source 2024-25 n'a que 24 colonnes (pas de `POSITION` / `POSITION_GROUP`) : d'où les 219 527 postes manquants de l'EDA. `pd.concat` aligne par nom de colonne, ce qui les met à manquant au lieu de décaler les colonnes.
- Une version « tout-en-un » du dataset circulant sur le Drive de la source (24 colonnes, 4 443 714 lignes) **n'est pas** la table de l'EDA : les contrôles de la section 0.3 la rejettent.
- Chargement complet ≈ 2,5 Go de RAM, 20 à 60 s ; la table complète est libérée dès le filtre de saison.
- Sorties en Parquet (pyarrow) ; repli automatique en CSV si pyarrow est absent. Environnement : `env/` créé depuis `requirements.txt`.
- Les 22 CSV sont aussi décompressés dans `data/shots_04_25/csv/` pour l'EDA (DuckDB) ; le pre-processing lit directement les zips.
- 453 tirs de 39 à 47 ft ont `ZONE_RANGE` = « Back Court Shot » mais `BASIC_ZONE` = « Above the Break 3 » (la source se contredit). Ils sont **conservés** : 0,02 % des lignes, 7 % de réussite, effet négligeable.
