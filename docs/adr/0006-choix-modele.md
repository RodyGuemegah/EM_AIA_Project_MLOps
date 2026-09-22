# ADR 0006 — XGBoost retenu pour sa robustesse, non pour sa performance

**Date** : 22 septembre 2026 · **Statut** : accepté

## Contexte

Trois familles de modèles ont été évaluées sur FD001, à conditions
identiques : mêmes 80 moteurs d'apprentissage, mêmes 20 moteurs
d'examen, même graine, mêmes 87 features.

| modèle | RMSE | seuil optimal | coût | pannes ratées |
|---|---|---|---|---|
| Régression linéaire (témoin) | 21,98 | — | — | — |
| Random Forest | 14,78 | 11 | 1 048 301 $ | 0 / 20 |
| XGBoost | 14,54 | 10 | 1 041 505 $ | 0 / 20 |

Chaque modèle a reçu la configuration propre à sa famille : profondeur
libre pour Random Forest, dont les arbres sont conçus pour être profonds
et dont le vote corrige le surapprentissage ; profondeur 6 et
apprentissage progressif pour XGBoost.

## Décision

XGBoost est retenu.

L'écart avec Random Forest — 1,6 % de RMSE, 0,65 % de coût, zéro panne
ratée des deux côtés — **n'est pas significatif sur 20 moteurs
d'examen**. Random Forest est même légèrement meilleur en zone critique
(erreur 3,6 vols contre 3,7, surestimation 84 % contre 91 %).

Le choix repose donc sur un critère d'exploitation : **XGBoost traite
nativement les valeurs manquantes**, chaque nœud ayant appris une
direction par défaut. `RandomForestRegressor` lève une exception.

Or le module de supervision aligne les colonnes des flottes entrantes
sur celles du modèle et produit des `NaN` lorsqu'une feature manque —
c'est précisément le mécanisme de détection de dérive de schéma
(ADR 0005). Avec Random Forest, le service cesserait de répondre au
moment même où la supervision devrait l'alerter.

## Conséquences

- La justification du modèle est explicitement opérationnelle, non
  métrique. Un gain de performance de Random Forest ne remettrait pas
  le choix en cause tant que la contrainte de robustesse tient.
- L'écart de performance étant dans le bruit, une réévaluation sur un
  jeu d'examen plus large (validation croisée par groupes) serait
  nécessaire avant toute conclusion sur la supériorité d'une famille.
- La régression linéaire est conservée comme témoin permanent dans
  `evaluate()` : elle détecte les régressions grossières.

## Alternatives écartées

- **Conclure à la supériorité de XGBoost sur la RMSE.** Surinterprétation
  d'un écart de 0,24 vol mesuré sur 20 moteurs.
- **Random Forest.** Écarté sur le critère de robustesse aux valeurs
  manquantes, non sur la performance.
- **Réseau de neurones récurrent (LSTM).** Écarté en amont : la
  volumétrie disponible (16 000 vols d'apprentissage) ne justifie pas
  le coût d'entraînement et d'explicabilité. Les features d'historique
  (`_moy20`, `_pente`, `_derive`) apportent la mémoire temporelle sans
  architecture séquentielle.