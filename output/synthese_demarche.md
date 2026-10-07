# 🏀 Projet NBA — De l'exploration au pre-processing : la démarche

*Synthèse rédigée le 2 octobre 2026, mise à jour le 7 octobre 2026 · Équipe : Hassan, Tristan, Paul + 1 · Formation DataScientest*

Ce document raconte **comment on a travaillé** et **pourquoi**, de la première lecture du sujet jusqu'à la table prête pour la modélisation. Il est écrit pour être relu dans six mois sans avoir à rouvrir les notebooks. Chaque variable est expliquée entre parenthèses la première fois qu'elle apparaît.

---

## 1. Le sujet, relu phrase par phrase

Le sujet demande deux choses : **comparer les tirs** (fréquence et efficacité, selon la situation de jeu et l'endroit du terrain) des 20 meilleurs joueurs NBA du XXIe siècle selon ESPN ; et, pour les joueurs encore en activité, **modéliser la probabilité qu'un tir rentre**.

Deux pièges qu'on a dû lever avant d'écrire une ligne de code.

Le premier : « meilleurs joueurs » ne veut pas dire « meilleurs tireurs ». Le classement ESPN (juillet 2024) mélange des pivots qui dunkent (Shaquille O'Neal, 58 % de réussite) et des arrières qui tirent de loin (Stephen Curry, 47 %). Comparer leurs pourcentages bruts n'a aucun sens : ils ne prennent pas les mêmes tirs. Il faut donc comparer **à tir égal**.

Le second : « prédire si un tir rentre » est impossible à l'unité — personne ne sait si le prochain tir de Curry rentrera. Ce qu'on peut estimer, c'est une **probabilité** : sur 100 tirs pris dans ces conditions-là, combien rentrent.

Ces deux pièges ont une seule et même solution, et c'est elle qui est devenue notre objectif.

## 2. L'objectif qu'on s'est fixé (cadrage du 1er octobre)

**Construire un modèle de qualité du tir** : à partir du **contexte** d'un tir, estimer sa probabilité de réussite. Le contexte, c'est tout ce qu'on sait au moment où le ballon quitte la main : d'où il part (distance, zone du terrain, coordonnées), comment (dunk, layup, tir en suspension ; en course ou en déséquilibre), quand (quart-temps, secondes restantes), par quel type de joueur (poste : meneur, ailier, pivot) et où (domicile ou extérieur).

**Ce que le modèle produit.** Un nombre entre 0 et 1. Exemple : *tir en suspension à 25 pieds (7,6 m), zone « Above the Break 3 », 4e quart-temps, 1 min 30 restante, meneur, à l'extérieur* → **0,34**. Lecture : sur 100 tirs pris exactement dans ces conditions par un joueur NBA quelconque, 34 rentrent. Un dunk sous le cercle donnera ~0,90, un layup en course ~0,58.

**Pourquoi le modèle ignore l'identité du joueur.** C'est le cœur de la méthode. Si on apprenait au modèle que « Curry = bon tireur », on ne pourrait plus mesurer son talent : il serait déjà dans la prédiction. En l'excluant, le modèle devient une **règle graduée neutre** : il dit ce qu'un tir *vaut*, indépendamment de qui le tente. Ensuite, pour chaque joueur, on compare ce qu'il **réussit réellement** à ce que ses tirs **valaient** : réel − attendu = sa contribution propre. +6 points pour Curry veut dire qu'il rentre ce que les autres ratent ; −3 pour un autre veut dire l'inverse. C'est ça qui permet de comparer les 20 joueurs ESPN honnêtement, à tir égal — premier objectif du sujet. Et le même modèle, appliqué aux prochains tirs d'un joueur actif, répond au second.

**À qui ça sert.** À un entraîneur, pour distinguer un joueur qui *choisit* bien ses tirs d'un joueur qui les *exécute* bien — deux qualités différentes. À un analyste, pour comparer des joueurs de postes différents. À un diffuseur, pour afficher une « probabilité de réussite » en direct.

**Le type de modèle.** On ne choisit pas encore l'algorithme (étape de novembre). Mais on sait de quelle famille il sera : **classification supervisée binaire** — une cible à deux valeurs (réussi / raté), des millions d'exemples déjà étiquetés — avec une **probabilité** en sortie plutôt qu'un simple oui/non. Cela suffit à savoir ce que la table doit respecter : des nombres uniquement, pas de colonne qui souffle la réponse, pas de doublons, des tirs comparables entre eux, et un découpage dans le temps pour mesurer honnêtement.

**Les décisions de périmètre.** Entraîner sur **toute la ligue** (2 millions de tirs), pas sur 20 joueurs : plus de données, et une règle graduée vraiment neutre. Restreindre aux **saisons 2015-16 et suivantes** : le basket a changé de nature avec l'explosion du tir à 3 points (la part de 3 points passe de 17 % en 2000 à 38 % en 2019 sur Kaggle, 42 % en 2024-25) ; entraîner sur les années 2000 reviendrait à apprendre un jeu qui n'existe plus. Les 20 joueurs ESPN deviennent un **filtre d'affichage** à la fin, pas une contrainte d'entraînement.

## 3. L'exploration : ce qu'elle nous a appris

Deux explorations ont été menées en parallèle, sur deux jeux de données.

**Kaggle « NBA Shot Locations 1997-2020 »** (Hassan) : 4 729 512 tirs, 22 colonnes, saisons régulières et playoffs. Cinq graphiques avec validation statistique ont établi les faits de base : la réussite chute avec la distance (55,8 % à moins de 8 ft contre 35,9 % au-delà de 24 ft ; test du chi² = 131 645) ; le geste est le facteur le plus discriminant (dunk 90,8 %, tir en suspension 37,2 %) ; la part de tirs à 3 points a doublé, avec une accélération nette à partir de 2013 (+0,54 point par an avant, +2,13 après) ; la réussite baisse du 1er au 4e quart-temps (46,4 % → 43,9 %) et plonge dans la dernière minute (40,8 %) ; et la relation distance-réussite se vérifie joueur par joueur (corrélation −0,73). Mais ce dataset s'arrête en 2020 et ses coordonnées sont imputées au cercle avant 2010 : l'équipe a décidé de **changer de source**.

**GitHub `DomSamangy/NBA_Shots_04_25`** (Tristan) : 4 450 789 tirs, 26 colonnes, 22 saisons régulières de 2003-04 à 2024-25, un fichier par saison. Tristan a rempli le template du mentor colonne par colonne et dressé un tableau « Difficultés & biais » dont chaque ligne propose un traitement. C'est ce dataset qu'on garde, et c'est ce tableau qui devient le cahier des charges du pre-processing.

### Les constats, et ce qu'ils veulent dire

| # | Constat | Source | En clair |
|---|---|---|---|
| A | `EVENT_TYPE` ⇔ `SHOT_MADE` | Tristan | Deux colonnes disent « réussi / raté », l'une en texte (*Made Shot*), l'autre en booléen (`True`/`False`). 0 désaccord sur 4,45 M lignes. L'une des deux est la réponse déguisée. |
| B | Colonnes redondantes | Tristan | `SEASON_2` (« 2015-16 ») = `SEASON_1` (2016) en texte ; `ZONE_ABB` (« LC ») = `ZONE_NAME` (« Left Side Center ») abrégé ; `POSITION` (18 valeurs : PG, SG, SG-PG…) se résume en `POSITION_GROUP` (G = arrière, F = ailier, C = pivot). |
| C | 398 doublons exacts | Tristan | Lignes identiques sur les 26 colonnes : même match, même joueur, même seconde, même geste, mêmes coordonnées, même résultat. Un joueur ne tire pas deux fois à la même seconde au même endroit : double saisie. Kaggle n'en avait aucun. |
| D | Postes manquants | Tristan | `POSITION_GROUP` vide sur **toute** la saison 2024-25 (219 527 lignes) + 7 930 lignes éparses depuis 2017. Kaggle n'avait aucune valeur manquante. |
| E | Rupture de collecte ≤ 2010 | Tristan, confirmé Kaggle | Avant 2010-11, un tir sur quatre a `SHOT_DISTANCE = 0` et des coordonnées posées au cercle : la NBA n'enregistrait pas la position des tirs proches. |
| F | Tirs « Backcourt » | Hassan (Kaggle), retrouvé chez Tristan | *Backcourt* = sa propre moitié de terrain, celle qu'on défend. Un tir déclenché de là part de 42 à 88 pieds (13 à 27 m) : un ballon jeté au buzzer, pas une décision de tir. 2 % de réussite. |
| G | `ACTION_TYPE` : 70 libellés | Tristan et Hassan | « Jump Shot » 745 000 fois, « Running Hook Shot » 5 fois. Trop de catégories, certaines trop rares pour apprendre quoi que ce soit. |
| H | Formats | Tristan et Hassan | `GAME_DATE` est du texte (« 11-12-2024 ») ; le temps restant est éclaté en `MINS_LEFT` + `SECS_LEFT`. |
| I | Pas de variable domicile | Tristan | L'équipe du tireur (`TEAM_NAME`, nom complet) et l'équipe qui reçoit (`HOME_TEAM`, abréviation) sont sous deux formes différentes : rien ne dit directement si le tireur joue chez lui. |
| J | Les saisons ne se ressemblent pas | Hassan (G3), Tristan | Part de 3 points qui double ; saisons écourtées (lockout 2011-12 : propriétaires fermant la ligue faute d'accord salarial ; COVID 2019-20 et 2020-21). |

## 4. Le pre-processing : logique et ordre

L'exploration **regarde** la table pour la comprendre et la mettre en doute. Le pre-processing la **transforme** jusqu'à ce qu'elle soit prête pour un modèle. Un modèle est une machine crédule : elle ne lit que des nombres, croit tout ce qu'on lui montre, et ne distingue pas une information légitime d'une tricherie. Préparer la table, c'est donc la présenter comme à quelqu'un qui ne pose aucune question.

Ça se décompose en quatre gestes, chacun répondant à des constats précis, plus une opération d'organisation :

| Geste | Ce qu'on fait | Constats |
|---|---|---|
| **Nettoyer** (qualité) | retirer les doublons, les tirs non comparables, les saisons d'un autre basket | C, E, F, J |
| **Supprimer** (fuites, redondances) | `EVENT_TYPE`, `SEASON_2`, `ZONE_ABB`, `POSITION` | A, B |
| **Transformer** (formats) | cible en 0/1, date en vraie date, temps en secondes, catégories en colonnes 0/1 | H, G |
| **Enrichir** (nouvelles variables) | famille de geste, temps restant dans le match, domicile, poste imputé, coordonnées corrigées | G, I, D, E |
| **Organiser** | découper train / validation / test **par saison** | J |

**Pourquoi dans cet ordre.** On re-vérifie d'abord qu'on a la bonne table (sinon tout est bâti sur du sable). On nettoie avant de calculer, pour ne pas calculer sur des lignes qu'on va jeter. On supprime ensuite, pour ne plus avoir sous les yeux des colonnes interdites. On convertit avant d'enrichir, parce que les variables dérivées ont besoin de vraies dates et de vrais nombres. On découpe sur la table complète, et on encode en dernier parce que l'encodage dépend de la liste finale des colonnes.

**Une règle.** Chaque suppression et chaque création doit se justifier par une ligne de l'EDA ou du cadrage, et chaque cellule qui retire des lignes imprime l'effectif avant / après : on doit pouvoir réconcilier 4 450 789 → table finale ligne à ligne.

## 5. Ce qu'on a fait, section par section

### 5.0 Re-vérifier avant de toucher

Lecture des 22 fichiers de saison (un zip chacun, laissés compressés : 80 Mo au lieu de 890) et assemblage par **nom de colonne** avec `pd.concat`. Détail qui compte : le fichier 2024-25 n'a que 24 colonnes ; aligner par nom met les postes à *manquant* pour cette saison — c'est l'origine exacte des 219 527 postes manquants de l'EDA. Une concaténation par position aurait décalé toutes les colonnes sans message d'erreur (on l'a vérifié par accident lors d'un premier essai).

Cinq contrôles automatiques comparent la table aux chiffres de Tristan : 4 450 789 × 26, `SHOT_MADE` booléen pur, 45,8 % de réussite, 227 457 postes manquants, rien d'autre de manquant. Les cinq passent. Ces contrôles ont servi dès le premier jour : une version « tout-en-un » du dataset récupérée sur le Drive de la source avait 24 colonnes et 4 443 714 lignes — ce n'était pas la même table, et le notebook l'a dit avant qu'on travaille dessus.

### 5.1 Périmètre : 4 450 789 → 2 095 638 tirs

| Étape | Retirées | Restantes | Pourquoi |
|---|---:|---:|---|
| Saisons avant 2015-16 | 2 350 533 | 2 100 256 | basket moderne (cadrage) ; emporte la rupture de collecte ≤ 2010 (E) |
| Doublons exacts | 98 | 2 100 158 | doubles saisies (C) — on a regardé : Tony Allen, putback raté, 11:30 au 2e quart, mêmes coordonnées, deux fois |
| Backcourt (42-88 ft, 2,3 % de réussite) + 81 « No Shot » | 4 520 | **2 095 638** | désespoirs de fin de période (F), événements sans geste |

On crée `saison_debut` = `SEASON_1` − 1 pour parler comme tout le monde (« saison 2015 » = celle qui commence à l'automne 2015). Les volumes par saison vont de 188 116 (2019-20, COVID) à 219 527 : on raisonnera toujours en taux, jamais en volumes.

### 5.2 Fuites et redondances

Après re-vérification des équivalences sur notre fenêtre (toutes tiennent), suppression de `EVENT_TYPE` (fuite), `SEASON_2`, `ZONE_ABB`, `POSITION`. Le tableau croisé zone × type de tir montre une poignée d'écarts (100 tirs à 2 points dans une zone à 3 points) : un pied sur la ligne. On garde `SHOT_TYPE` comme vérité du barème (l'arbitre a compté 2 ou 3) et `BASIC_ZONE` comme description du lieu.

### 5.3 Conversions

`SHOT_MADE` → 0/1 ; `GAME_DATE` → vraie date (les dates confirment le périmètre saison régulière : 2019-20 finit le 14 août 2020 dans la bulle d'Orlando, 2020-21 commence le 22 décembre) ; `tir_3pts` → 0/1.

### 5.4 Variables dérivées — toutes connues au moment du tir

**Temps.** `temps_restant_qt` (secondes restantes dans le quart-temps) et `temps_restant_match` (secondes restantes dans le match : les quart-temps à venir comptent 720 s chacun ; en prolongation, le temps restant de la prolongation) ; `prolongation` (0/1, 0,6 % des tirs). Vérification : la dernière minute du 4e quart ou d'une prolongation se joue à 42,0 % de réussite contre 46,6 % ailleurs — le constat Kaggle se retrouve sur l'autre dataset.

**Geste.** Un libellé NBA = un geste de base + des qualificatifs (*Driving Floating Bank Jump Shot* = floater, en pénétration, avec la planche). On sépare les deux. `type_geste` en 5 familles : Dunk (ballon claqué dans le cercle), Layup (déposé près du cercle, y compris le finger roll), Floater (tir en cloche à courte distance par-dessus un défenseur), Hook (bras roulé), Jump shot (tout le reste). Le gradient est physiquement sensé : Jump shot 37,8 % → Floater 45,2 % → Hook 48,2 % → Layup 56,0 % → Dunk 89,4 %. Les qualificatifs (*driving*, *pullup*, *tip*, *alley oop*…) ont été testés comme indicateurs 0/1, puis **écartés** : à famille de geste et distance égales, leur effet change de signe (un *pullup* réussit mieux qu'un jump shot simple de même distance, un *tip* moins bien qu'un layup posé), et un modèle entraîné avec et sans ces colonnes obtient le même log-loss. L'information existe, mais elle est déjà dans `type_geste`, la distance et les coordonnées. Chiffres et décision : section 4.2 bis du notebook, et `preprocessing.md`. Les libellés rares ne sont pas supprimés mais regroupés : « Running Hook Shot » (5 fois) est un hook.

**Domicile.** Pas de table de correspondance nom ↔ abréviation dans les données ; on la reconstruit : sur une saison, l'abréviation présente dans 100 % des matchs d'une équipe est la sienne (celles des adversaires n'apparaissent que quelques fois). 300 équipes-saisons, 300 abréviations trouvées, 0 ambiguïté, deux contrôles à 100 %. `tireur_domicile` : 46,9 % de réussite à domicile contre 46,0 % — l'avantage du terrain existe, il est modeste.

**Coordonnées — la découverte du pre-processing.** `LOC_X` (décalage latéral en pieds, 0 = axe du panier), `LOC_Y` (profondeur, 0 = ligne de fond, panier à 5,25) et `SHOT_DISTANCE` décrivent la même chose. Tristan avait mesuré une corrélation de 0,82 entre `SHOT_DISTANCE` et la distance recalculée, attribuée à la rupture d'avant 2011. Sur notre fenêtre elle aurait dû être parfaite ; elle était de 0,74. Saison par saison, le verdict : sur **2019-20, 2020-21 et 2021-22**, les coordonnées sont **10 fois trop petites** (distance recalculée 8,3 fois inférieure, sur 100 % des matchs). Tout indique une conversion d'unités appliquée deux fois à la source. Le contrôle « coordonnées hors terrain = 0 » de l'EDA ne pouvait pas le voir : des valeurs 10 fois trop petites restent dans le terrain. Correction : `LOC_X` × 10 et `LOC_Y` × 10 − 52,5 sur ces trois saisons. Après : corrélation 0,9996, écart moyen 0,48 ft, zéro point hors terrain, et `SHOT_DISTANCE` est exactement la partie entière de la distance recalculée dans 99,8 % des cas. Toute carte de tir sur ces saisons sans correction est fausse ; `SHOT_DISTANCE` et `BASIC_ZONE` ne sont pas touchés.

**Poste.** Supprimer les 219 000 tirs sans poste reviendrait à retirer la saison qu'on veut prédire. Le poste étant quasi stable (86 % des joueurs gardent le même groupe sur dix ans), on impute le **dernier poste connu du même joueur** : 204 208 tirs résolus. Les 21 836 restants (117 joueurs) sont des rookies 2024-25 — Risacher, Castle, Sarr — sans saison antérieure : modalité explicite `Inconnu`, qui est une information en soi. Signal confirmé : pivots 54,3 %, ailiers 46,2 %, arrières 43,9 %.

### 5.5 Clé, table propre, découpage, encodage

**Clé.** Le dataset n'a pas d'identifiant de tir. La clé naturelle (match, quart-temps, seconde, joueur) n'est pas unique : 1 591 collisions — Draymond Green a tenté trois vrais tirs dans la même seconde (layup, tip, tir en suspension, tous ratés, bagarre au rebond). On adopte une clé technique `shot_id` (numéro de ligne après tri chronologique), présente dans les deux fichiers de sortie.

**Trois familles de colonnes.** C'est cette classification qui garantit la neutralité du modèle. Les **identifiants et contexte** (`shot_id`, saison, match, date, équipe, joueur, libellé brut du geste, zones fines) restent dans la table pour l'analyse *après* modélisation, mais ne sont jamais des variables d'entrée. Les **variables explicatives** : 9 numériques (`SHOT_DISTANCE`, `LOC_X`, `LOC_Y`, `tir_3pts`, `QUARTER`, `prolongation`, `temps_restant_qt`, `temps_restant_match`, `tireur_domicile`) et 3 catégorielles (`BASIC_ZONE`, `type_geste`, `POSITION_GROUP`). La **cible** : `SHOT_MADE`.

**Découpage par saison.** Un découpage aléatoire mélangerait des tirs de 2024 dans l'entraînement et de 2016 dans le test : le modèle serait évalué sur un passé qu'il a déjà vu. En production on prédit le futur, donc on découpe dans le temps : `train` = 2015-16 → 2022-23 (1 658 384 tirs, 46,3 % de réussite), `validation` = 2023-24 (218 254, 47,5 %) pour comparer les modèles et régler leurs paramètres, `test` = 2024-25 (219 000, 46,8 %) mesuré une seule fois à la fin — et c'est la saison où les postes sont imputés, donc une mesure en conditions réelles. La part de 3 points continue de monter (35,6 → 39,4 → 42,0 %) : raison de plus pour tester `saison_debut` comme variable dans la variante C du test de fenêtre.

**Encodage : pourquoi et comment.** Un modèle ne lit que des nombres ; `BASIC_ZONE` vaut « Mid-Range » ou « Restricted Area ». Deux façons de traduire. L'encodage **ordinal** (Mid-Range = 1, Restricted Area = 2…) impose un ordre qui n'existe pas : « Restricted Area » n'est pas « deux fois » Mid-Range — faux ici. L'encodage **one-hot** crée une colonne 0/1 par modalité (`BASIC_ZONE_Mid-Range`, `BASIC_ZONE_Restricted Area`…) : pas d'ordre artificiel, lisible, et c'est ce qu'on fait avec `pd.get_dummies`. Coût : 6 + 5 + 4 modalités = 15 colonnes 0/1 ; avec les 53 libellés bruts de geste on en aurait eu 53, d'où l'intérêt du regroupement en familles. Les variables déjà numériques et les indicateurs 0/1 n'ont rien à subir. Au total **24 variables d'entrée**. On n'applique **pas** de standardisation (mise à l'échelle) ici : elle dépend du modèle (nécessaire pour une régression logistique, inutile pour une forêt aléatoire) et doit être ajustée sur `train` seulement — première cellule du notebook de modélisation.

**Sorties.** Deux fichiers Parquet dans `data/processed/` (ignoré par Git, chacun les régénère en exécutant le notebook) : `shots_clean_2015_2025.parquet` (table lisible, 29 colonnes, 35,3 Mo) et `shots_encoded_2015_2025.parquet` (table modèle, 30 colonnes, 28,5 Mo), reliées par `shot_id`. Parquet plutôt que CSV : 5 à 10 fois plus compact, types conservés, lecture instantanée.

## 6. Ce qu'on retient, et ce qui attend

**Trois difficultés rencontrées**, à documenter dans le rapport : la version « Drive » du dataset (24 colonnes, 4 443 714 lignes) qui n'est pas celle de l'EDA — détectée par les contrôles ; le fichier 2024-25 sans postes — compris et traité par imputation ; les coordonnées à la mauvaise échelle sur trois saisons — découvertes et corrigées ici, invisibles pour l'EDA.

**La baseline à battre** : prédire la moyenne de `train`, soit 46,3 % pour tout tir. Tout modèle qui ne fait pas mieux ne sert à rien.

**Prochaine étape (6 novembre) : faite le 6 octobre, voir la section 7.**

**Deux questions pour le mentor.** La liste ESPN de juillet 2024 convient-elle comme définition des « 20 meilleurs » ? Un modèle générique appliqué joueur par joueur répond-il bien à « modéliser la probabilité de réussite pour les joueurs actifs » ? Et une troisième, apparue depuis : quatre des vingt joueurs ESPN (Nash, Kidd, Iverson, Ray Allen) n'ont **aucun** tir dans la fenêtre 2015-2025, trois autres (Bryant, Duncan, Garnett) une seule saison. Sur qui porte la comparaison ?

## 7. La baseline (6 octobre) : l'approche tient

Notebook `notebooks/03_modelisation.ipynb`, compte rendu `output/modelisation.md`. Le problème est une classification supervisée binaire dont on veut la **probabilité**, donc l'arbitre est le **log-loss** (la probabilité prédite est-elle juste ?), avec l'AUC et la courbe de calibration en complément ; l'accuracy est affichée pour information seulement, parce qu'elle exige un seuil et qu'un tir « à 60 % » rate quatre fois sur dix même pour un modèle parfait.

Trois modèles simples, entraînés sur `train` (2015-16 → 2022-23) et jugés sur `validation` (2023-24), le `test` restant scellé :

| Modèle | log-loss | AUC |
|---|---:|---:|
| Plancher : 46,3 % pour tout tir | 0,692 | 0,500 |
| Régression logistique (standardisation ajustée sur train, dans un `Pipeline`) | 0,650 | 0,642 |
| Arbre de décision, profondeur 6 | 0,646 | 0,643 |
| Arbre de décision libre (89 niveaux) | 16,3 | 0,542 |

Ce qu'on en retient. **L'approche tient** : les deux modèles limités battent nettement le plancher et leurs probabilités sont calibrées, quand ils annoncent 60 %, environ 60 % des tirs rentrent. **L'AUC modeste est structurelle** : deux tirs identiques sur les 24 colonnes peuvent avoir deux résultats, le modèle estime ce qu'un tir vaut, pas ce qu'il va donner. **Le sur-apprentissage se voit** : l'arbre libre est parfait sur le train et désastreux sur la validation. **L'arbre limité devance légèrement la régression** parce qu'il combine les variables (« sous le cercle et dunk »), ce qui motive les modèles à base d'arbres des étapes suivantes. La régression logistique est conservée comme référence, sauvegardée dans `models/` avec la liste exacte de ses 24 colonnes ; ses poids se lisent (dunk +0,38, distance −0,31). Les prédictions sur la validation sont gardées dans `data/processed/predictions_validation_baseline.parquet`, reliées par `shot_id`.

Deux observations pour la suite : le tirage au hasard contre le découpage par saison ne diffère que de 0,0007 de log-loss sur cette fenêtre (le jeu change lentement) ; et les modèles sont légèrement pessimistes en moyenne (46 % prédits contre 47,5 % réels en 2023-24), effet époque que la variante `saison_debut` devra traiter en décembre, avec le réglage des paramètres et la forêt aléatoire.