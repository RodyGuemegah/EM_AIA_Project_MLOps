# ADR 0004 — L'entraînement est automatisé, la promotion ne l'est pas

**Date** : 20 septembre 2026 · **Statut** : accepté

## Contexte

Le pipeline d'entraînement peut être déclenché automatiquement, en
particulier lors d'une alerte de dérive. Se pose alors la question de
savoir si le modèle produit doit partir seul en production.

## Décision

La promotion — le déplacement de l'alias `production` — reste un acte
humain, réalisé après comparaison dans MLflow des métriques technique
(RMSE) **et** économique (coût du seuil optimal) avec la version en place.
`experiment.py` enregistre et versionne, il ne promeut jamais.

## Conséquences

- Un modèle dégradé ne peut pas atteindre la production sans décision
  explicite et tracée.
- Le délai de mise en production dépend de la disponibilité d'un humain.
  Acceptable au regard du domaine : une dérive s'installe sur des
  semaines, pas sur des heures.
- Impose de maintenir un critère de comparaison lisible — c'est le rôle
  de la métrique `cout_optimal_usd` enregistrée à chaque run.

## Alternatives écartées

- **Promotion automatique si RMSE inférieure.** Une RMSE meilleure sur
  la moyenne peut masquer une dégradation en zone critique, seule zone
  qui compte pour la décision de dépose.
- **Promotion automatique avec retour arrière.** Suppose une supervision
  en production qui n'existe pas dans le périmètre du projet.