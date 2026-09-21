"""Constantes partagées entre l'entraînement et le service.

Isolées ici pour que l'API n'ait pas à importer le pipeline de données
uniquement pour connaître un seuil. Un module de configuration n'importe
rien : c'est ce qui lui permet d'être importé par tout le monde.
"""

# Résultat mesuré par threshold.chercher_seuil() sur FD001, 20 moteurs
# d'examen. Voir ADR 0001. À recalculer après tout réentraînement.
import os


SEUIL_RETENU = 10

MODELE = "rul-xgboost"
ALIAS = "production"

# 5001 et non 5000 : macOS réserve le 5000 pour AirPlay Receiver.
# Surchargeable par variable d'environnement — indispensable pour le
# conteneur, où 127.0.0.1 désigne le conteneur lui-même.
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")