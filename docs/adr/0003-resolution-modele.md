# ADR 0003 — L'API résout le modèle par alias, jamais par numéro de version

**Date** : 20 septembre 2026 · **Statut** : accepté

## Contexte

Le registre MLflow versionne les modèles (1, 2, 3…). L'API doit en
désigner un. Écrire un numéro en dur imposerait de modifier et
redéployer le code à chaque réentraînement.

## Décision

L'API charge `models:/rul-xgboost@production`. L'alias `production` est
une étiquette déplaçable, posée sur la version en service.

## Conséquences

- Promouvoir un nouveau modèle ne demande aucune modification de code
  ni nouveau déploiement : on déplace l'alias, on redémarre le service.
- La version réellement servie est exposée dans chaque réponse de l'API
  (`modele_version`), ce qui préserve la traçabilité malgré l'indirection.
- Une dépendance opérationnelle est introduite : si le registre MLflow
  est indisponible, l'API ne démarre pas.

## Alternatives écartées

- **Numéro de version en dur.** Couple le code au cycle de vie du modèle.
- **Toujours la dernière version.** Un entraînement dégradé partirait
  automatiquement en production.
- **Fichier `.joblib` local.** Aucune traçabilité, aucun versionnement,
  et rien ne garantit que le fichier servi soit celui qui a été évalué.