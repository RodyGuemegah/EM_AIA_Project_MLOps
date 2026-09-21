# ADR 0001 — Le seuil d'alerte est calculé par matrice de coûts

**Date** : 20 septembre 2026 · **Statut** : accepté

## Contexte

Le modèle produit une durée de vie résiduelle estimée. Il faut la
convertir en décision binaire : déposer le moteur, ou le laisser voler.
Cette conversion suppose un seuil. Choisir « 10 vols » à l'intuition
aurait rendu toute la chaîne de décision arbitraire.

Deux erreurs sont possibles, de gravité très inégale :
- alerter trop tard → immobilisation en vol (AOG), 10 000 à 150 000 $
  de l'heure selon l'IATA (2025)
- alerter trop tôt → vols encore sains perdus, ~243 $ pièce

## Décision

Le seuil est obtenu par simulation exhaustive. `threshold.py` balaie les
60 politiques possibles sur le jeu d'examen (20 moteurs), calcule pour
chacune le coût total — pannes ratées, déposes, vols gâchés — et retient
le minimum.

Résultat mesuré : **10 vols**, 0 panne sur 20, 1 041 505 $.
Sans modèle : 9 600 000 $. Soit **89 % d'économie**.

Ces 10 vols se décomposent en 3 vols de délai d'intervention
incompressible et 7 vols de marge absorbant l'optimisme mesuré du
modèle (91 % de surestimation en zone critique).

## Conséquences

- La décision est traçable et rejouable, non arbitraire.
- Le seuil dépend d'hypothèses de coût qui doivent être revues avec le
  métier ; l'analyse de sensibilité montre qu'il reste stable du
  ratio 2 au ratio 50.
- Tout réentraînement impose de recalculer le seuil : le biais du
  modèle change, la marge aussi.

## Alternatives écartées

- **Seuil fixé à dire d'expert.** Non reproductible, indéfendable
  chiffres à l'appui.
- **Optimiser la RMSE seule.** Une métrique technique ne hiérarchise pas
  les deux types d'erreur, alors qu'ils diffèrent d'un facteur 2 000.
- **Seuil par moteur.** Plus fin, mais 20 moteurs d'examen ne suffisent
  pas à calibrer 20 seuils sans surapprentissage.