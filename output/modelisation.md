# 🏀 NBA Shot Analysis — Modélisation, étape 1 : baseline

Notebook : `notebooks/03_modelisation.ipynb` · Entrée : `data/processed/shots_encoded_2015_2025.parquet` (produit par `02_preprocessing.ipynb`) · Sorties : `models/baseline_regression_logistique.joblib`, `data/processed/predictions_validation_baseline.parquet`, figures `output/figures/M1` à `M4` · Échéance du planning : 6 novembre 2026 (*models baseline*).

## Objectif de l'étape

Premiers modèles **simples**, comparés honnêtement, pour répondre à une question : peut-on estimer la probabilité qu'un tir rentre à partir de son seul contexte (24 variables : distance, coordonnées, zone, famille de geste, moment du match, domicile, poste), mieux qu'en prédisant la moyenne ? Conformément au cadrage, le modèle ignore l'identité du joueur : `PLAYER_ID` et `PLAYER_NAME` restent dans les tables comme clés, jamais comme variables d'entrée.

## Cadre

| Élément | Choix | Pourquoi |
|---|---|---|
| Type de problème | classification supervisée binaire, cible `SHOT_MADE` (0/1), sortie = probabilité | cadrage : « probabilité de réussite » |
| Variables d'entrée | les 24 colonnes de la table encodée, listées en toutes lettres dans le notebook, contrôle automatique qu'aucune clé n'y figure | neutralité du modèle |
| Apprentissage / jugement | `split == train` (2015-16 → 2022-23, 1 658 384 tirs) / `split == validation` (2023-24, 218 254 tirs) | découpage par saison du pre-processing |
| Jeu `test` (2024-25) | **scellé**, pas même chargé | il ne servira qu'une fois, à l'étape finale |
| Arbitre principal | **log-loss** (la probabilité est-elle juste ?) | le produit final est une probabilité, pas une classe |
| Compléments | AUC (classement), courbe de calibration (visuelle) ; accuracy affichée pour information seulement | l'accuracy exige un seuil et ne distingue pas 0,51 de 0,95 |
| Modèles de cette étape | plancher (moyenne), régression logistique, arbre de décision | modèles simples du planning ; forêt en décembre, boosting et deep learning en février |
| Modèles écartés | SVM (coût impraticable sur 1,66 M lignes), k plus proches voisins (lent, mauvais avec des 0/1), naïf bayésien (variables très redondantes) | tableau « panorama » du notebook |

## Résultats sur la validation (saison 2023-24)

| Modèle | log-loss | AUC | accuracy (seuil 0,5) |
|---|---:|---:|---:|
| Plancher : prédire 46,3 % pour tout tir | 0,692 | 0,500 | 0,525 |
| **Régression logistique** (standardisation ajustée sur train + modèle, dans un `Pipeline`) | 0,650 | 0,642 | 0,622 |
| **Arbre de décision**, profondeur 6, ≥ 1 000 tirs par feuille (55 feuilles) | 0,646 | 0,643 | 0,624 |
| Arbre de décision libre (89 niveaux, 575 000 feuilles) | 16,3 | 0,542 | 0,544 |

Lecture :

- **L'approche tient.** Les deux modèles limités battent nettement le plancher, et leur courbe de calibration (`M4_calibration.png`) suit la diagonale : quand ils annoncent 60 %, environ 60 % des tirs rentrent.
- **L'AUC modeste (0,64) est structurelle**, pas un échec : deux tirs identiques sur les 24 colonnes peuvent avoir deux résultats différents (défense, fatigue, adresse du soir). Le modèle estime ce qu'un tir *vaut* en moyenne, c'est ce que le cadrage demande.
- **Le sur-apprentissage se voit** : l'arbre libre obtient 0,007 de log-loss sur le train et 16,3 sur la validation. On ne juge jamais un modèle sur les données qu'il a apprises.
- **Les deux modèles sont légèrement pessimistes en moyenne** (46,0 % et 45,4 % prédits contre 47,5 % réels) : ils héritent du taux du train (46,3 %), la saison 2023-24 ayant été un peu plus adroite. Effet époque, à traiter avec la variante `saison_debut` en décembre.
- **L'arbre limité devance légèrement la régression logistique** (0,646 contre 0,650) : avec six questions il combine les variables (« sous le cercle *et* dunk »), ce qu'une somme pondérée ne peut pas exprimer. Cette avance motive les modèles à base d'arbres des étapes suivantes.

## Ce que disent les modèles

- **Régression logistique** (`M1_poids_regression_logistique.png`) : poids dominants `type_geste_Dunk` (+0,38) et `SHOT_DISTANCE` (−0,31) ; `BASIC_ZONE_Restricted Area` +0,12, `BASIC_ZONE_In The Paint (Non-RA)` −0,12 ; moment du match, domicile et poste entre 0,01 et 0,02. Le poids négatif de `type_geste_Layup` (−0,09) se lit *à distance et zone égales* : effet des variables redondantes (`SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `tir_3pts`, zones), limite connue d'un modèle linéaire.
- **Arbre de décision** (`M2_arbre_decision.png`, `M3_importances_arbre.png`) : racine `SHOT_DISTANCE` ≤ 2,5 pieds (sous le cercle ou pas) ; sous le cercle, `type_geste_Dunk` isole une case à 91 % ; loin du cercle, `SHOT_DISTANCE` ≤ 20,5 puis `temps_restant_qt` ≤ 3,5 s (tirs au buzzer). Importance : distance 77 %, dunk 19 %.

## Vérification du découpage par saison

Même régression logistique, jugée sur un jeu de côté de même taille : tirage au hasard 0,6490, découpage par saison 0,6497. L'écart (0,0007) est dans le sens attendu, le tirage au hasard est plus flatteur, mais petit : le jeu a changé lentement sur 2015-2024 pour ce modèle. Le découpage par saison est conservé parce qu'il reproduit l'usage réel (prédire une saison jamais vue). L'écart sera re-mesuré en décembre avec des modèles capables de sur-apprendre une époque. Ce n'est pas une série temporelle : aucune date n'entre dans le modèle, la date sert seulement à répartir les lignes.

## Décisions

| Décision | Section du notebook |
|---|---|
| Arbitre : log-loss ; AUC et calibration en complément ; accuracy pour information | 2 |
| Découpage par saison conservé, démontré contre le tirage au hasard | 4 |
| Standardisation ajustée sur le train seulement, dans un `Pipeline` | 5 |
| Arbre limité à la profondeur 6 (le choix fin de la profondeur est un réglage de décembre) | 6 |
| **Référence conservée : la régression logistique**, modèle le plus simple, stable, calibré, explicable poids par poids ; avance de l'arbre notée | 7 |
| Modèle sauvegardé avec la liste exacte de ses 24 colonnes, rechargement vérifié (prédiction identique sur 1 000 tirs) | 9 |
| Variante `saison_debut` (effet époque) reportée à décembre | 8 |

## Fichiers produits

| Fichier | Contenu |
|---|---|
| `models/baseline_regression_logistique.joblib` | dictionnaire : `modele` (Pipeline standardisation + régression), `features` (ordre des 24 colonnes), `scores_validation`, `date` — 4 ko |
| `data/processed/predictions_validation_baseline.parquet` | un tir de la validation par ligne : `shot_id`, `SHOT_MADE`, `proba_reg_log`, `proba_arbre` — 218 254 lignes, 1,7 Mo ; se joint à `shots_clean` par `shot_id` |
| `output/figures/M1_poids_regression_logistique.png` | poids standardisés des 24 variables |
| `output/figures/M2_arbre_decision.png` | les 3 premiers niveaux de l'arbre limité |
| `output/figures/M3_importances_arbre.png` | importance des variables de l'arbre |
| `output/figures/M4_calibration.png` | courbes de calibration des deux modèles |

## Prochaine étape (11 décembre)

Réglage des paramètres (profondeur de l'arbre, régularisation de la régression), forêt aléatoire, variante avec `saison_debut`. Toujours jugé sur `validation` ; le `test` reste scellé. Février : gradient boosting, deep learning, interprétabilité (SHAP). Notebook 04 : comparaison réel − attendu par joueur pour les 20 joueurs ESPN (liste à fournir).
