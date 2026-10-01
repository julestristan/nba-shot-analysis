# Rapport d'Exploration des Données

**Nombre de lignes dans la table :** Lignes   : 4,729,512
**Nombre de colonnes dans la table :** Colonnes : 22

| N° | Nom de la colonne | Description | Disponibilité a priori | Type | NA % | Gestion des NA | Distribution des valeurs | Remarques |
|---|---|---|---|---|---|---|---|---|
| 1 | Game ID | Identifiant du match | Oui | int64 | 0 | Aucune | 28 817 valeurs distinctes | Identifiant, pas une quantité |
| 2 | Game Event ID | Numéro de l'événement dans le match | Oui | int64 | 0 | Aucune | 899 valeurs distinctes | (Game ID, Game Event ID) = clé unique du tir (0 doublon, cellule 4) |
| 3 | Player ID | Identifiant du joueur | Oui | int64 | 0 | Aucune | 2 152 valeurs distinctes | Identifiant |
| 4 | Player Name | Nom du joueur | Oui | object | 0 | Aucune | 2 143 valeurs distinctes | 9 noms portés par 2 joueurs (homonymes) ; aucun des 25 ESPN concerné → utiliser Player ID |
| 5 | Team ID | Identifiant de l'équipe du tireur | Oui | int64 | 0 | Aucune | 30 valeurs distinctes | Identifiant stable ; clé de jointure avec les autres tables Kaggle |
| 6 | Team Name | Nom de l'équipe | Oui | object | 0 | Aucune | 37 valeurs distinctes | 6 franchises renommées ou déménagées (Seattle→OKC, Vancouver→Memphis, NJ→Brooklyn, Hornets/Bobcats/Pelicans, LA Clippers) → utiliser Team ID (cellule 10) |
| 7 | Period | Quart-temps ; 5 à 8 = prolongations | Oui | int64 | 0 | Aucune | 1 : 26,2 % · 2 : 24,9 % · 3 : 24,5 % · 4 : 23,6 % · 5 : 0,6 % · 6 : 0,1 % · 7, 8 : < 0,1 % | Prolongations = 0,7 % des tirs, à regrouper |
| 8 | Minutes Remaining | Minutes restantes dans le quart-temps | Oui | int64 | 0 | Aucune | min 0, médiane 5, moy 5,3, max 12 | 12 = quart-temps de 12 min |
| 9 | Seconds Remaining | Secondes restantes dans la minute | Oui | int64 | 0 | Aucune | min 0, médiane 29, moy 28,7, max 59 | À combiner avec Minutes pour un temps restant total |
| 10 | Action Type | Type de geste (Jump Shot, Layup, Dunk…) | Oui (décrit le geste tenté) | object | 0 | Aucune | 70 catégories, très déséquilibrées : Jump Shot 54 % ; 25 catégories < 5 000 tirs ; réussite de 34,5 % (Jump Shot) à 97,6 % (Slam Dunk) | À regrouper en familles ; « No Shot » (278 lignes) incohérent → exclure ; annotation partiellement liée au résultat pour les dunks (cellule 9) |
| 11 | Shot Type | Tir à 2 ou 3 points | Oui | object | 0 | Aucune | 2PT 76,2 % · 3PT 23,8 % | Binaire |
| 12 | Shot Zone Basic | Zone du terrain | Oui | object | 0 | Aucune | Restricted Area 31,8 % · Mid-Range 30,0 % · Above the Break 3 17,5 % · In The Paint (Non-RA) 14,5 % · Left Corner 3 3,1 % · Right Corner 3 2,9 % · Backcourt 0,2 % | Backcourt = tirs désespérés, cas à part |
| 13 | Shot Zone Area | Côté du terrain | Oui | object | 0 | Aucune | Center 52,8 % · Left Side 13,0 % · Right Side 12,0 % · Right Side Center 11,1 % · Left Side Center 10,9 % · Back Court 0,2 % | Symétrie gauche/droite ; redondant en partie avec X Location |
| 14 | Shot Zone Range | Tranche de distance | Oui | object | 0 | Aucune | < 8 ft 41,0 % · 24+ ft 23,5 % · 16-24 ft 19,5 % · 8-16 ft 15,8 % · Back Court 0,2 % | Version discrétisée de Shot Distance (bornes vérifiées, cellule 7) |
| 15 | Shot Distance | Distance au panier, en pieds | Oui | int64 | 0 | Aucune | min 0, Q1 2, médiane 13, moy 12,1, Q3 21, max 89 | Unité vérifiée par Zone Range et par X/Y (cellule 7) ; > 47 = autre moitié de terrain |
| 16 | X Location | Coordonnée latérale, 1/10 pied, panier à l'origine | Oui | int64 | 0 | Aucune | −250 à 250, médiane 0, moy −1,3 | Négatif = gauche ; ±250 = 50 pieds = largeur du terrain |
| 17 | Y Location | Coordonnée en profondeur, 1/10 pied | Oui | int64 | 0 | Aucune | −52 à 884, médiane 38, moy 76,3 | Négatif = derrière le panier ; distribution asymétrique (beaucoup de tirs près du panier) |
| 18 | Shot Made Flag | Résultat du tir : 1 réussi, 0 raté | Non — c'est la cible | int64 | 0 | Aucune | 1 : 45,2 % (2 136 714) · 0 : 54,8 % (2 592 798) | Variable à expliquer (objectif 1) et à prédire (objectif 2) |
| 19 | Game Date | Date du match | Oui | int64 → converti en date | 0 | Aucune | 1997-10-31 → 2020-03-11 ; 23 saisons ; 3 saisons incomplètes : 1998-99 (lock-out), 2011-12 (lock-out), 2019-20 (COVID) | Stockée en AAAAMMJJ, convertie (cellule 6) ; colonne Saison dérivée (cellule 8) ; saisons 1997-1999 hors périmètre XXIe siècle |
| 20 | Home Team | Équipe à domicile (abréviation) | Oui | object | 0 | Aucune | 36 valeurs distinctes | Servira à créer la variable domicile/extérieur |
| 21 | Away Team | Équipe à l'extérieur (abréviation) | Oui | object | 0 | Aucune | 36 valeurs distinctes | idem |
| 22 | Season Type | Saison régulière / playoffs | Oui | object | 0 | Aucune | Regular Season 94,0 % · Playoffs 6,0 % | Binaire |