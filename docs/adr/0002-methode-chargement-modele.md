# ADR 0002 — Le modèle est chargé au démarrage de l'API, pas par requête

**Date** : 20 septembre 2026 · **Statut** : accepté

## Contexte

L'API doit charger trois objets coûteux : le modèle XGBoost depuis le
registre MLflow, l'ordre des features, et l'explainer SHAP. Les
construire à chaque requête porterait la latence à environ 2 secondes.

## Décision

Chargement unique dans le `lifespan` de FastAPI, conservé en mémoire
dans un dictionnaire `ETAT`. Latence d'inférence ramenée à quelques
millisecondes.

## Conséquences

- Le démarrage du service prend quelques secondes : à prendre en compte
  dans la sonde de vivacité et les délais d'orchestration.
- Changer de modèle impose un redémarrage du service. Acceptable : la
  promotion d'un modèle est un acte rare et planifié (voir ADR 0004).
- La mémoire du processus est occupée en permanence par le modèle.

## Alternatives écartées

- **Chargement paresseux à la première requête.** Reporte le coût sans
  le supprimer, et rend la première requête anormalement lente.
- **Rechargement périodique automatique.** Ajoute un comportement non
  déterministe : deux requêtes simultanées pourraient être servies par
  deux modèles différents.