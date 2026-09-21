"""Constantes partagées entre l'entraînement et le service.

Isolées ici pour que l'API n'ait pas à importer le pipeline de données
uniquement pour connaître un seuil. Un module de configuration n'importe
rien : c'est ce qui lui permet d'être importé par tout le monde.
"""

# Résultat mesuré par threshold.chercher_seuil() sur FD001, 20 moteurs
# d'examen. Voir ADR 0001. À recalculer après tout réentraînement.
SEUIL_RETENU = 10

MODELE = "rul-xgboost"
ALIAS = "production"