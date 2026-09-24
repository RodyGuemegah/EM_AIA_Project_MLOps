# ADR 0007 — Promotion du modèle réentraîné FD001+FD003 (version 6)

**Date** : 22 septembre 2026 · **Statut** : accepté

## Contexte

L'ADR 0005 a établi que le modèle FD001 (version 4) laisse passer 48 %
des pannes sur FD003, pour un coût multiplié par 5. Un réentraînement
sur FD001 + FD003 réunis a produit la version 6. FD004 a été
volontairement maintenue hors apprentissage, comme flotte de contrôle
jamais vue.

| flotte | v4, seuil 10 | v6, seuil 14 | écart |
|---|---|---|---|
| FD001 (21 moteurs d'examen) | 52 075 $/moteur · 0 % ratées | 53 606 $ · 0 % | +2,9 % |
| FD003 (19 moteurs d'examen) | 257 584 $/moteur · 48 % ratées | 52 938 $ · 0 % | −79,4 % |
| FD004 (249 moteurs, jamais vus) | 480 000 $ · 100 % | 480 000 $ · 100 % | inchangé |

## Décision

La version 6 est promue en production, alias `production` déplacé
manuellement. Le seuil passe de 10 à 14 vols, recalculé conformément
à l'ADR 0001.

L'arbitrage est net : 2,9 % de surcoût sur la flotte d'origine contre
79,4 % d'économie sur la flotte dérivée, sans aucune panne ratée sur
les deux.

## Conséquences

- Le seuil de 14 est l'optimum indépendant de FD001 **et** de FD003 :
  le modèle est cohérent sur les deux régimes, non un compromis moyen.
- La dégradation de RMSE sur FD001 (14,54 → 16,07, soit +10,5 %) est
  trois fois supérieure à la dégradation de coût (+2,9 %). RMSE et coût
  sont décorrélés dans les deux sens — confirmation de l'ADR 0005.
- FD004 reste inutilisable. Le seuil optimal y vaut 1, c'est-à-dire que
  la politique la moins coûteuse consiste à ne pas alerter : le modèle
  n'y apporte aucune valeur. Un élargissement du périmètre
  d'entraînement à FD004 est identifié comme l'évolution suivante.
- `SEUIL_RETENU` passe à 14 dans `src/config.py`. L'API doit être
  redémarrée pour prendre en compte le nouveau modèle (ADR 0002).

## Alternatives écartées

- **Conserver la version 4 et recalibrer le seuil sur FD003.** Il aurait
  fallu alerter 52 vols à l'avance, soit un quart de la vie du moteur.
- **Réentraîner sur les quatre sous-jeux.** Aurait supprimé toute flotte
  de contrôle : impossible alors de distinguer ce que le réentraînement
  corrige de ce qu'il ne corrige pas.
- **Promotion automatique.** Contraire à l'ADR 0004.