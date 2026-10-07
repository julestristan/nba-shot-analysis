# Sources de données

## Dataset retenu (EDA, pre-processing, modélisation)

- **NBA_Shots_04_25**, dépôt GitHub [DomSamangy/NBA_Shots_04_25](https://github.com/DomSamangy/NBA_Shots_04_25) : un CSV par saison régulière, 2003-04 → 2024-25, 4 450 789 tirs, 26 colonnes (données NBA.com). Zips dans `data/shots_04_25/`, décompressés dans `data/shots_04_25/csv/` ; le dossier `data/` est ignoré par Git.
- Attention : la version « tout-en-un » diffusée sur le Drive de la source (24 colonnes, 4 443 714 lignes) n'est pas la même table. Les contrôles de `notebooks/02_preprocessing.ipynb` la rejettent.

## Dataset de la première exploration (archive)

- Kaggle **NBA Shot Locations 1997-2020** : 4 729 512 tirs, 22 colonnes, saison régulière et playoffs. Fichier dans `data/NBA shot locations/`. EDA : `notebooks/archive/eda_kaggle.ipynb`, compte rendu `output/eda_kaggle.md`.

## Autres datasets Kaggle présents dans `data/`, non utilisés par le pipeline

- NBA games data, NBA Box Scores, NBA Players stats since 1950.

## Références

- Classement ESPN des 25 meilleurs joueurs du XXIe siècle (juillet 2024) : liste `ESPN25` dans `notebooks/archive/eda_kaggle.ipynb`. Le sujet retient les 20 premiers.
- [espn_nba_shots (sportsdataverse)](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/espn_nba_shots)
- [nba_api](https://github.com/swar/nba_api)
- [sportsdataverse-py](https://py.sportsdataverse.org/docs/intro)
