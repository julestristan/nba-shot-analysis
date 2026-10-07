# test/hassan — exploration, pre-processing et baseline

Travail d'Hassan sur le projet « Analyse des tirs NBA » (DataScientest). Ce dossier reprend l'arborescence de mon dépôt de travail, sans les données ni l'environnement.

**Document de présentation : [`rapport.md`](rapport.md)**, au format du template DataScientest, figures incluses (Rendu 1 complet, Rendu 2 au niveau de la baseline).

## Contenu

| Dossier / fichier | Contenu |
|---|---|
| `notebooks/01_eda.ipynb` | exploration et data visualisation (DuckDB), 6 figures avec validation statistique |
| `notebooks/02_preprocessing.ipynb` | nettoyage, variables dérivées, correction des coordonnées, découpage par saison, encodage → 2 Parquet |
| `notebooks/03_modelisation.ipynb` | baseline : plancher, régression logistique, arbre de décision ; log-loss, AUC, calibration ; modèle sauvegardé |
| `notebooks/archive/eda_kaggle.ipynb` | première EDA sur le dataset Kaggle 1997-2020, gardée pour référence |
| `output/*.md` | comptes rendus par étape : `synthese_demarche.md` (la démarche), `eda.md`, `data.md`, `preprocessing.md`, `modelisation.md` |
| `output/figures/` | toutes les figures (exploration, `P1` correction des coordonnées, `M1` à `M4` modélisation) |
| `models/` | le modèle de référence (régression logistique) avec la liste exacte de ses 24 colonnes, 4 ko |
| `requirements.txt` | dépendances épinglées (pandas 3.0.5, scikit-learn 1.9.1, pyarrow, duckdb, matplotlib, scipy, joblib) |

Les notebooks s'exécutent dans cet ordre. Chacun est écrit pour être lu seul : une cellule d'explication avant chaque bloc, du code commenté, une cellule « Lecture » après.

## Reproduire

1. Environnement : `python3 -m venv env && source env/bin/activate && pip install -r requirements.txt`, depuis ce dossier.
2. Données : les 22 zips `NBA_YYYY_Shots.csv.zip` du dépôt `DomSamangy/NBA_Shots_04_25` dans `test/hassan/data/shots_04_25/`, et leurs CSV décompressés dans `test/hassan/data/shots_04_25/csv/` (pour l'EDA, DuckDB ne lit pas dans les zips). Voir `datasets_ref.md`.
3. `jupyter lab` depuis ce dossier, puis les notebooks 01, 02, 03. Le pre-processing écrit `data/processed/`, la modélisation écrit `models/` et `data/processed/predictions_validation_baseline.parquet`.

Les chemins des notebooks sont relatifs à ce dossier (`../data`, `../output`, `../models`) : ils ne dépendent pas de l'arborescence du reste du dépôt.
