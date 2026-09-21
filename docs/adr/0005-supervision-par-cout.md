# ADR 0005 — La supervision de dérive porte sur le coût, pas sur la RMSE

**Date** : 21 septembre 2026 · **Statut** : accepté

## Contexte

Un modèle de durée de vie résiduelle se périme : la flotte évolue, les
conditions d'exploitation changent, les modes de défaillance se
diversifient. Il faut donc superviser sa dégradation en production et
définir à partir de quel niveau elle impose un réentraînement.

La pratique courante consiste à surveiller la métrique d'apprentissage —
ici la RMSE. Le scénario de dérive a été mesuré avant de trancher :
le modèle entraîné sur FD001 (une condition de vol, un mode de
défaillance) a été appliqué sans réentraînement à FD003 (deux modes) et
FD004 (six conditions, deux modes).

| sous-jeu | RMSE | ×RMSE | pannes ratées | coût/moteur | ×coût |
|---|---|---|---|---|---|
| FD001 (référence) | 14,54 | ×1,00 | 0 % | 52 075 $ | ×1,00 |
| FD003 | 16,67 | ×1,15 | **48 %** | 257 584 $ | **×4,95** |
| FD004 | 41,20 | ×2,83 | **100 %** | 480 000 $ | **×9,22** |

Aucune feature n'est manquante sur les trois sous-jeux : la dérive est
distributionnelle, non structurelle.

## Décision

L'indicateur de supervision retenu est le **coût par moteur**, calculé
par `simuler_politique` au seuil en vigueur. La RMSE est conservée comme
indicateur secondaire de diagnostic, jamais comme critère de
déclenchement.

Le réentraînement est déclenché lorsque le coût par moteur dépasse
**deux fois** celui de la référence nominale — soit bien avant le
niveau constaté sur FD003.

## Conséquences

- L'alerte se déclenche sur la grandeur qui intéresse l'exploitant,
  et non sur une grandeur technique.
- Le calcul du coût exige de connaître le RUL réel, donc d'attendre que
  les moteurs supervisés soient arrivés à la panne. La supervision est
  rétrospective, avec le décalage que cela implique. Un indicateur
  avancé sur les distributions d'entrée est nécessaire en complément
  (voir ADR 0006, détection Evidently).
- La référence nominale doit être recalculée à chaque promotion de
  modèle : le seuil d'alerte est relatif, pas absolu.

## Alternatives écartées

- **Surveiller la RMSE.** Mesuré : une dégradation de 15 % de RMSE
  correspond à 48 % de pannes non détectées. Le signal technique
  sous-estime le dommage d'un facteur quatre — il aurait laissé passer
  la dérive de FD003 sans alerte.
- **Recalibrer le seuil au lieu de réentraîner.** Le seuil optimal
  passe de 10 à 52 vols sur FD003, soit un quart de la vie du moteur
  sacrifié par précaution. Sur FD004, l'optimum sort de la plage
  explorée (1 à 60) : aucun seuil de la plage ne rend le modèle
  utilisable. Un seuil ne rattrape pas un modèle périmé.
- **Surveiller le taux d'alertes émises.** Sensible à la composition de
  la flotte autant qu'à la qualité du modèle : une flotte vieillissante
  ferait monter le taux sans aucune dérive.