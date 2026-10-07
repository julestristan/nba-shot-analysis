# Rapport d'exploration : source API stats.nba.com

## Contexte

- **Source :** endpoint `ShotChartDetail` de `stats.nba.com`, interrogé via le paquet Python `nba_api` (voir `docs/api_scouting.md`).
- **Périmètre :** 30 saisons **régulières** (playoffs non extraits), de **1996-97** à **2025-26**, restreint aux **20 joueurs** du top 25 ESPN du 21e siècle retenus par le sujet.
- **Donnée :** 1 ligne = 1 tentative de tir (lancers francs exclus).
- **Extraction :** `src/api/fetch_shots.py`, 342 appels, sortie `data/interim/shots_top20.parquet` (3,3 Mo).
- **Rôle dans le projet :** cette source complète les CSV analysés par ailleurs. Elle couvre 7 saisons supplémentaires en amont, la saison 2025-26, et donne accès au play-by-play.

## Chiffres clés

| Indicateur | Valeur |
|---|---|
| **Nombre de lignes (30 saisons)** | **360 279** |
| Nombre de colonnes | 24 (22 de l'API + 2 ajoutées à l'extraction) |
| Matchs distincts (`GAME_ID`) | 16 051 |
| Joueurs distincts (`PLAYER_ID`) | 20 |
| Équipes distinctes (`TEAM_ID`) | 22 |
| Taux de réussite global (`SHOT_MADE_FLAG`) | 48,4 % |
| Part de tirs à 3 points | 23,5 % (16,6 % en 2003-04, 34,3 % en 2025-26) |
| Distance moyenne | 12,45 ft (médiane 13, écart-type 9,70) |
| Lignes en double (exactes) | **0** |
| Cellules manquantes | 22 lignes (0,006 %) sur 6 colonnes de localisation |

Volume par joueur : de 10 262 tirs (Manu Ginobili) à 31 502 (LeBron James), médiane 18 286. Tous les joueurs dépassent largement le seuil de viabilité d'un modèle individuel.

---

## Description des variables

**Légende « Disponible a priori »** : l'information existe-t-elle **au moment où le joueur arme son tir**, donc utilisable pour prédire `SHOT_MADE_FLAG` ?
`Oui` = variable candidate. `Oui, mais` = connue avant le tir mais sans valeur prédictive (identifiant, constante). `Non` = cible ou fuite.

| N° | Nom de la colonne | Description | Dispo. a priori | Type | Taux de NA | Gestion des NA | Distribution des valeurs | Remarques |
|:--:|:--|:--|:--|:--|:--:|:--|:--|:--|
| 1 | `GAME_ID` | Identifiant du match (10 chiffres, préfixe `002` = saison régulière) | Oui, mais identifiant | object | 0 % | - | 16 051 modalités | Clé de découpage train/test par match, et de jointure vers le play-by-play. Jamais comme feature. |
| 2 | `GAME_EVENT_ID` | Numéro de l'événement dans le déroulé du match | Oui, mais identifiant | int64 | 0 % | - | min 1 · max 864 · moy 258 | Avec `GAME_ID`, identifie le tir de façon unique. **Absent des CSV : c'est la seule porte d'entrée vers le play-by-play.** |
| 3 | `GAME_DATE` | Date du match, format `AAAAMMJJ` | Oui | object | 0 % | - | 4 628 dates distinctes | **Texte** à convertir. Permet de dériver jours de repos et back-to-backs (fait, voir §Analyses dérivées). |
| 4 | `PLAYER_ID` | Identifiant NBA du tireur | Oui | int64 | 0 % | - | 20 modalités | **Identique aux CSV** : clé de raccordement entre les deux sources. |
| 5 | `PLAYER_NAME` | Nom du tireur | Oui | object | 0 % | - | 20 modalités · LeBron James 8,7 % · Kobe Bryant 7,3 % | L'API renvoie « Nikola Jokić » accentué, le CSV « Nikola Jokic ». Se rattacher à `PLAYER_ID`. |
| 6 | `TEAM_ID` | Franchise du tireur au moment du tir | Oui | int64 | 0 % | - | 22 modalités | Clé stable de la franchise. |
| 7 | `TEAM_NAME` | Nom de cette franchise | Oui | object | 0 % | - | **27 modalités pour 22 `TEAM_ID`** | Relocations et renommages : Seattle→OKC, New Jersey→Brooklyn, NO Hornets→Pelicans, Los Angeles→LA Clippers. Se rattacher à `TEAM_ID`. |
| 8 | `PERIOD` | Quart-temps ; 5 à 7 = prolongations | Oui | int64 | 0 % | - | `1` 27,9 % · `3` 27,2 % · `2` 22,5 % · `4` 21,4 % · `5-7` 1,0 % | Cohérent : aucune prolongation avec plus de 4 minutes restantes. |
| 9 | `MINUTES_REMAINING` | Minutes restantes dans le quart-temps | Oui | int64 | 0 % | - | 0 à 12 ; ~8 % par minute sauf `0` (10,2 %) | Le pic à 0 traduit les tirs de fin de période. Seulement 6 lignes à 12. |
| 10 | `SECONDS_REMAINING` | Secondes restantes dans la minute courante | Oui | int64 | 0 % | - | min 0 · max 59 · moy 28,7 | À combiner : `temps_restant_s = MINUTES_REMAINING × 60 + SECONDS_REMAINING`. |
| 11 | `ACTION_TYPE` | Geste technique du tir | Oui (vérifié, voir §Fuites) | object | 0 % | - | **70 modalités**, très déséquilibrées : `Jump Shot` 48,5 % · `Layup Shot` 9,3 % · `Driving Layup` 7,1 % · `Pullup Jump shot` 5,1 %, longue traîne | **Variable la plus liée à la cible** (V de Cramér 0,319). Forte cardinalité et **vocabulaire non stationnaire** : à regrouper en familles (jump / layup / dunk / hook / tip / floater). |
| 12 | `SHOT_TYPE` | `2PT Field Goal` / `3PT Field Goal` | Oui | object | 0 % | - | `2PT` 76,5 % · `3PT` 23,5 % | Déductible de la zone et de la distance : redondant à 0,996 avec `SHOT_ZONE_BASIC`. |
| 13 | `SHOT_ZONE_BASIC` | Zone de tir (7 modalités) | Oui | object | 0,01 % | Suppression | `Mid-Range` 31,3 % · `Restricted Area` 28,6 % · `Above the Break 3` 20,0 % · `Paint Non-RA` 16,7 % · corners 3,2 % · `Backcourt` 0,2 % | Bon compromis granularité / lisibilité pour la dataviz. |
| 14 | `SHOT_ZONE_AREA` | Latéralité (6 modalités) | Oui | object | 0,01 % | Suppression | `Center` 53,0 % · `Left Side` 12,3 % · `Right Center` 11,9 % · `Left Center` 11,7 % · `Right Side` 10,8 % | **La moins redondante des variables spatiales** (0,686 max) : elle seule porte la position gauche/droite. À conserver. |
| 15 | `SHOT_ZONE_RANGE` | Tranche de distance (5 modalités) | Oui | object | 0,01 % | Suppression | `< 8 ft` 38,2 % · `24+ ft` 23,1 % · `8-16 ft` 19,4 % · `16-24 ft` 19,0 % · `Back Court` 0,2 % | Discrétisation de `SHOT_DISTANCE`. |
| 16 | `SHOT_DISTANCE` | Distance au panier, en pieds entiers | Oui | float64 | 0,01 % | Suppression | min 0 · max 87 · moy 12,45 · méd 13 · σ 9,70 · **distribution bimodale** | `= 0` sur **15,6 %** des lignes ; 23,7 % jusqu'en 2009-10 contre 7,6 % ensuite. **Non comparable dans le temps** (voir §Ruptures). |
| 17 | `LOC_X` | Abscisse, dixièmes de pied, 0 = axe du panier | Oui | float64 | 0,01 % | Suppression | min −250 · max 250 · moy −2,17 · méd 0 | **Unité différente des CSV** (pieds, origine ligne de fond). Conversion : `X_api = X_csv × 10`. |
| 18 | `LOC_Y` | Ordonnée, dixièmes de pied, 0 = **panier** | Oui | float64 | 0,01 % | Suppression | min −52 · max 867 (tirs pleine longueur) · moy 87 · méd 55 | Conversion : `Y_api = (Y_csv − 5,25) × 10`. **Imputé à 0 pour les tirs au cercle jusqu'en 2009-10.** |
| 19 | `SHOT_ATTEMPTED_FLAG` | Indicateur de tentative | Oui, mais **constante** | int64 | 0 % | - | `1` sur 100 % des lignes | Aucune information. À supprimer. |
| 20 | `SHOT_MADE_FLAG` | Tir réussi (0/1) : **variable cible** | **Non (cible)** | int64 | 0 % | - | `0` 51,6 % · `1` 48,4 % | Classes quasi équilibrées : l'accuracy est trompeuse, un modèle constant atteint 51,6 %. |
| 21 | `HTM` | Abréviation de l'équipe à domicile | Oui | object | 0 % | - | **36 modalités** · `LAL` 8,7 % · `SAS` 6,7 % | Abréviations non stables : `SEA`, `NJN`, `VAN`, `CHH`, `NOH`, `NOK` ont disparu. |
| 22 | `VTM` | Abréviation de l'équipe visiteuse | Oui | object | 0 % | - | **36 modalités** · `LAL` 8,9 % · `SAS` 6,9 % | Croisée avec `TEAM_ID`, permet de dériver l'indicateur domicile/extérieur (fait, voir §Analyses dérivées). |
| 23 | `SEASON` | Saison, format `AAAA-AA` | Oui | object | 0 % | - | 30 modalités, 1,5 % à 4,7 % chacune | **Ajoutée à l'extraction**, absente de la réponse de l'API. Feature « effet époque ». |
| 24 | `SEASON_TYPE` | Type de saison | Oui, mais **constante** | object | 0 % | - | `Regular Season` sur 100 % des lignes | **Ajoutée à l'extraction.** Constante par choix d'extraction : les playoffs sont disponibles via l'API et non extraits à ce stade. |

**Colonnes de l'API volontairement écartées à l'extraction :** `EVENT_TYPE` (`Made Shot` / `Missed Shot`), strictement équivalente à la cible et donc constitutive d'une fuite. Elle est retirée dès `fetch_shots.py` plutôt qu'au pre-processing, pour qu'elle ne puisse pas se retrouver dans un jeu d'entraînement par inadvertance.

---

### Point d'attention sur le calcul de la distance

La corrélation de 1,000 obtenue ici tient à une subtilité de repère qui mérite d'être signalée à l'équipe.

Dans les CSV, `LOC_Y` est mesuré **depuis la ligne de fond** et le panier se situe à `Y = 5,25 ft`. Une distance euclidienne calculée naïvement par `√(X² + Y²)` ne mesure donc pas la distance au panier mais la distance à la ligne de fond.

Vérification faite sur `data/NBA_2004_Shots.csv` :

| Formule | Corrélation avec `SHOT_DISTANCE` | Erreur moyenne |
|---|---|---|
| `√(X² + Y²)` sans décalage | 0,988 | **4,27 ft** |
| `√(X² + (Y − 5,25)²)` avec décalage | **1,000** | **0,37 ft** |

Le décalage du panier est donc indispensable côté CSV. Il ne l'est pas côté API, où l'origine du repère **est déjà le panier**. Les deux sources décrivent la même géométrie dans deux repères différents.

---

## Ruptures de collecte

Deux discontinuités touchent les variables les plus prédictives du jeu de données. Elles sont d'origine NBA et se retrouvent identiquement dans les CSV, ce qui les confirme.

### Rupture 1 : les coordonnées, à la saison 2010-11

Jusqu'en 2009-10, la position réelle des tirs pris près du cercle n'était pas relevée : ils étaient tous ramenés aux coordonnées exactes du panier.

Part des tirs de la zone restreinte enregistrés à `LOC = (0 ; 0)` :

| Saison | Part | Saison | Part |
|---|---|---|---|
| 1996-97 | 95,2 % | 2010-11 | **0,0 %** |
| 1997-98 | 81,8 % | 2012-13 | 0,0 % |
| 2002-03 | 82,8 % | 2015-16 | 0,0 % |
| 2006-07 | 70,6 % | 2019-20 | 0,0 % |
| 2009-10 | 63,1 % | 2020-21 | 7,2 % |

Volume concerné : **39 057 tirs, soit 22 % des données antérieures à 2010**, tous en zone restreinte, à 64,2 % de réussite. Le phénomène réapparaît partiellement à 7-8 % à partir de 2020-21.

**Conséquence :** toute analyse spatiale fine antérieure à 2010-11 est faussée. La tache très dense sous le panier sur les cartes de tirs anciennes est un artefact d'enregistrement, pas un fait de jeu.

### Rupture 2 : le vocabulaire de `ACTION_TYPE`

| Période | Nombre de libellés distincts |
|---|---|
| 1996-97 à 1999-00 | 10 |
| 2000-01 à 2006-07 | 29 |
| 2007-08 à 2009-10 | 49 |
| 2010-11 à 2016-17 | 65 |
| 2017-18 à 2025-26 | 48 |

55 libellés apparus après 2007 n'existaient pas avant 2000. `Step Back Jump shot` et `Pullup Jump shot`, aujourd'hui parmi les plus fréquents, sont des créations du système de notation, pas des gestes nouveaux.

**Conséquence :** `ACTION_TYPE` étant notre variable la plus prédictive, un découpage train/test chronologique sur toute la profondeur ferait travailler le modèle sur deux vocabulaires différents. Cette rupture n'est pas visible dans les CSV, qui démarrent en 2003-04.

---

## Analyses dérivées

Deux variables absentes du jeu de données brut ont été reconstruites, l'une et l'autre signalées comme manquantes dans l'analyse des CSV.

### Domicile ou extérieur

Ni les CSV ni l'API n'indiquent directement si le tireur joue à domicile. L'information est reconstituée en identifiant l'abréviation propre à chaque franchise : elle apparaît dans **tous** ses matchs, à domicile via `HTM` et à l'extérieur via `VTM`, alors que celles des adversaires varient. Le mapping couvre 100 % des lignes.

| | Tirs | Réussite |
|---|---|---|
| À domicile | 171 133 | **49,30 %** |
| À l'extérieur | 189 146 | **47,56 %** |

Écart de **+1,75 point** en faveur du domicile. Test de comparaison de deux proportions : **z = 10,5**, p pratiquement nul. L'avantage du terrain est donc mesurable et statistiquement incontestable, mais modeste au regard des autres facteurs.

*Note : la part de tirs à domicile est de 47,5 % et non 50 %, ce qui est attendu, les joueurs disputant en moyenne un peu moins de minutes à l'extérieur.*

### Jours de repos

Dérivés de l'écart entre deux dates de match consécutives pour un même joueur.

| Repos | Tirs | Réussite |
|---|---|---|
| Back-to-back (1 jour) | 72 262 | **47,72 %** |
| 2 jours | 197 788 | 48,62 % |
| 3 jours | 55 307 | 48,64 % |
| 4 jours et plus | 29 576 | 48,33 % |

L'effet de la fatigue est réel mais faible : moins d'un point de pourcentage entre un back-to-back et un match normalement espacé. Au-delà de 3 jours, le repos n'apporte plus rien et semble même légèrement défavorable, ce qui est cohérent avec la perte de rythme évoquée par les entraîneurs.

### Fin de possession et fin de période

2,45 % des tirs (8 811) sont pris dans les **3 dernières secondes** d'une période. Leur taux de réussite est de **28,5 %** contre 48,4 % en général, soit 20 points de moins. Ce sont des tirs désespérés, souvent de très longue distance. Ils justifient à eux seuls la création d'une variable de temps restant, et éventuellement leur exclusion du jeu d'entraînement.

---

## Efficacité par zone

| Zone | Tirs | Part | Réussite | Espérance de points |
|---|---|---|---|---|
| Restricted Area | 103 110 | 28,6 % | 66,4 % | **1,328** |
| Left Corner 3 | 6 037 | 1,7 % | 40,8 % | **1,224** |
| Right Corner 3 | 5 502 | 1,5 % | 39,7 % | **1,190** |
| Above the Break 3 | 71 945 | 20,0 % | 36,7 % | **1,101** |
| In The Paint (Non-RA) | 60 345 | 16,7 % | 44,7 % | 0,894 |
| Mid-Range | 112 677 | 31,3 % | 42,4 % | **0,850** |
| Backcourt | 641 | 0,2 % | 3,9 % | 0,117 |

Lecture métier : **la zone la plus fréquentée est la moins rentable.** La mi-distance concentre 31,3 % des tirs pour 0,850 point par tentative, soit moins que n'importe quel tir à 3 points. Les deux corners sont les meilleurs tirs extérieurs du terrain, parce que la ligne y est plus proche du panier, mais ils ne représentent que 3,2 % des tentatives.

Le classement par pourcentage de réussite et le classement par espérance de points ne coïncident pas : c'est le piège de lecture principal de ce jeu de données.

---

## Profil des 20 joueurs

| Joueur | Tirs | Réussite | Espérance | Part 3 pts | Distance moy. |
|---|---|---|---|---|---|
| Nikola Jokić | 12 274 | 56,1 % | 1,197 | 20,8 % | 10,1 ft |
| Shaquille O'Neal | 13 935 | 58,3 % | 1,166 | 0,1 % | 3,5 ft |
| Stephen Curry | 19 155 | 47,1 % | 1,164 | 52,6 % | 18,1 ft |
| Giannis Antetokounmpo | 14 266 | 55,4 % | 1,146 | 13,7 % | 7,9 ft |
| Kevin Durant | 22 375 | 50,3 % | 1,113 | 27,1 % | 14,0 ft |
| Kawhi Leonard | 11 994 | 49,9 % | 1,112 | 28,9 % | 13,5 ft |
| Steve Nash | 12 892 | 49,0 % | 1,111 | 30,6 % | 14,6 ft |
| LeBron James | 31 502 | 50,7 % | 1,097 | 24,0 % | 11,7 ft |
| Anthony Davis | 13 923 | 52,2 % | 1,072 | 9,4 % | 9,2 ft |
| Ray Allen | 18 955 | 45,2 % | 1,061 | 39,2 % | 15,4 ft |
| James Harden | 19 733 | 43,9 % | 1,050 | 47,2 % | 15,1 ft |
| Chris Paul | 17 408 | 46,9 % | 1,045 | 29,1 % | 14,9 ft |
| Manu Ginobili | 10 262 | 44,7 % | 1,039 | 39,5 % | 13,5 ft |
| Dirk Nowitzki | 23 734 | 47,1 % | 1,025 | 22,0 % | 14,8 ft |
| Tim Duncan | 20 334 | 50,6 % | 1,013 | 0,8 % | 7,5 ft |
| Kevin Garnett | 20 407 | 49,7 % | 1,002 | 3,0 % | 10,8 ft |
| Dwyane Wade | 17 617 | 48,0 % | 0,991 | 10,6 % | 10,2 ft |
| Kobe Bryant | 26 200 | 44,7 % | 0,964 | 21,2 % | 13,5 ft |
| Jason Kidd | 13 407 | 40,2 % | 0,938 | 37,7 % | 15,8 ft |
| Allen Iverson | 19 906 | 42,5 % | 0,904 | 17,0 % | 11,8 ft |

Deux constats.

**Le classement par espérance de points n'est pas celui par pourcentage de réussite.** Stephen Curry, 3e à l'espérance avec seulement 47,1 % de réussite, devance Tim Duncan qui réussit 50,6 % de ses tirs. La raison tient en une colonne : 52,6 % de tirs à 3 points contre 0,8 %. Curry ne réussit pas mieux, il tire mieux.

**L'amplitude entre joueurs est faible.** De 40,2 % à 58,3 % de réussite, soit 18 points, alors que l'amplitude entre types de geste atteint 62 points (36,0 % pour un `Jump Shot`, 98,5 % pour un `Slam Dunk Shot`). **La nature du tir pèse trois fois plus lourd que l'identité du tireur.** C'est le constat le plus contre-intuitif de cette exploration, et il oriente directement la modélisation vers un modèle global plutôt que vers 20 modèles individuels.

---

## Contrôle croisé avec la source CSV

Le CSV `data/NBA_2004_Shots.csv` et l'API couvrent tous deux la saison 2003-04. Les 12 joueurs du périmètre présents cette saison-là servent de test de validation croisée.

| Joueur | CSV tentés | API | CSV réussis | API |
|---|---|---|---|---|
| Kevin Garnett | 1 611 | 1 611 | 804 | 804 |
| LeBron James | 1 492 | 1 492 | 622 | 622 |
| Dirk Nowitzki | 1 310 | 1 310 | 605 | 605 |
| Tim Duncan | 1 181 | 1 181 | 592 | 592 |
| Kobe Bryant | 1 178 | 1 178 | 516 | 516 |
| Allen Iverson | 1 125 | 1 125 | 435 | 435 |
| Ray Allen | 1 017 | 1 017 | 447 | 447 |
| Jason Kidd | 959 | 959 | 368 | 368 |
| Shaquille O'Neal | 948 | 948 | 554 | 554 |
| Steve Nash | 845 | 845 | 397 | 397 |
| Dwyane Wade | 798 | 798 | 371 | 371 |
| Manu Ginobili | 789 | 789 | 330 | 330 |

**12 joueurs sur 12, identiques au tir près**, sur les tentatives comme sur les réussites. Les totaux correspondent par ailleurs aux statistiques officielles de saison régulière.

Ce test valide deux choses simultanément : le pipeline d'extraction API, et la fidélité du dataset CSV. Les deux sources sont donc interchangeables sur leur périmètre commun, ce qui autorise à les combiner.

### Écarts constatés à périmètre égal

En restreignant l'extraction API à la période couverte par les CSV (2003-04 à 2024-25), les écarts avec les chiffres de la ligue entière sont les suivants :

| Indicateur | Ligue entière (CSV) | Top 20 (API) | Écart |
|---|---|---|---|
| Taux de réussite | 45,8 % | 48,6 % | +2,8 pt |
| Part de tirs à 3 points | 29,2 % | 25,0 % | −4,2 pt |
| Mid-range | 23,8 % | 30,3 % | +6,5 pt |
| Restricted Area | 31,6 % | 28,5 % | −3,1 pt |
| Distance moyenne | 12,63 ft | 12,76 ft | +0,13 ft |
| Modalités de `ACTION_TYPE` | 70 | 70 | identique |

Ces écarts ne sont pas des anomalies mais un résultat : **les 20 meilleurs joueurs du siècle prennent des tirs statistiquement moins rentables que la moyenne de la ligue, et les réussissent malgré tout plus souvent.** Ils tirent 6,5 points de plus à mi-distance, la zone la moins rentable du terrain, parce que le périmètre contient beaucoup d'intérieurs et de joueurs d'avant la révolution du 3 points, et parce que le tir en isolation à mi-distance est la signature des créateurs.

---

## Difficultés et biais : synthèse pour l'étape 2

| # | Constat | Sévérité | Traitement retenu |
|---|---|---|---|
| 1 | **Rupture de collecte des coordonnées** : `LOC = (0 ; 0)` sur 63 à 95 % des tirs au cercle jusqu'en 2009-10, 0 % ensuite, 7-8 % à partir de 2020-21 | Élevée | Indicateur `coord_fiable` ; analyse spatiale restreinte à 2010-11 et après ; ou recalcul de la distance depuis les coordonnées |
| 2 | **Vocabulaire de `ACTION_TYPE` non stationnaire** : 10 libellés en 1996-97, 70 au total | Élevée | Regrouper en familles de gestes stables dans le temps (jump / layup / dunk / hook / tip / floater) avant toute modélisation |
| 3 | **Redondance spatiale** : `SHOT_TYPE`, `SHOT_ZONE_BASIC`, `SHOT_ZONE_RANGE` et `SHOT_DISTANCE` décrivent le même fait (V de Cramér jusqu'à 0,996) | Moyenne | Conserver `SHOT_DISTANCE` (continue, la plus fine) et `SHOT_ZONE_AREA` (position latérale, non redondante) ; écarter les trois autres |
| 4 | **Colonnes constantes** : `SHOT_ATTEMPTED_FLAG`, `SEASON_TYPE` | Faible | Supprimer |
| 5 | **Non-stationnarité du jeu** : part de 3 points de 16,6 % à 34,3 % sur la période | Moyenne | `SEASON` en feature ; découpage train/test temporel **et** par match |
| 6 | **Saisons écourtées** : lockout 2011-12, COVID 2019-20 et 2020-21 | Faible | Raisonner en taux, jamais en volumes bruts |
| 7 | **Libellés instables** : 27 noms d'équipe pour 22 identifiants, 36 abréviations pour 30 franchises, accentuation variable des noms de joueurs | Faible | Toute jointure passe par les identifiants, jamais par les libellés |
| 8 | **Absence des playoffs** dans l'extraction actuelle | Moyenne | Disponibles via l'API : à extraire si l'équipe retient le périmètre complet |
| 9 | **Absence du poste du joueur**, présent dans les CSV | Faible | Récupérable via l'endpoint `CommonPlayerInfo`, ou par jointure sur `PLAYER_ID` avec les CSV |
| 10 | **Incohérences zone / type de tir** : 535 lignes (0,15 %) | Faible | Bruit de saisie. Écarter ou laisser, l'impact est nul à cette échelle |

---

## Data visualisation

Voir `eda_api.ipynb`, 7 représentations, chacune accompagnée d'un commentaire métier et d'une validation.

1. **Volumétrie par joueur** : de 10 262 à 31 502 tirs. Valide la faisabilité d'une modélisation.
2. **Couverture temporelle** (joueur × saison) : maximum 16 joueurs simultanés, en 2009. Les comparaisons directes entre joueurs de générations différentes ne sont pas légitimes.
3. **Réussite selon la distance**, avec intervalle de confiance et volume associé. Validation par l'espérance de points : le tir à 3 points rapporte 1,114 point contre 0,842 à mi-distance, soit **+32 % de rendement** (test z = 42).
4. **Carte des tirs** : densité des tentatives et écart de réussite à la moyenne, sur demi-terrain.
5. **Évolution des emplacements par période** (petits multiples) : la part du 3 points passe de 11 % à 29 %, la mi-distance de 22 % à 12 %. La figure rend également visible la rupture de collecte de 2010-11.
6. **Réussite par type de geste** : amplitude de 62 pct entre le meilleur et le pire geste.
7. **Force du lien avec la cible** (V de Cramér) et **redondance entre variables**. `ACTION_TYPE` 0,319 · `SHOT_ZONE_BASIC` 0,236 · `SHOT_DISTANCE` 0,227 · `PLAYER_NAME` 0,082 · `PERIOD` 0,024.

---

