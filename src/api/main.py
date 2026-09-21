"""API de prédiction de durée de vie résiduelle.

Elle réunit les quatre briques du projet en une seule réponse :
le modèle (XGBoost), le registre (MLflow), la décision (seuil de coût)
et l'explication (SHAP).

CE QU'ELLE NE FAIT PAS, ET C'EST VOULU
---------------------------------------
Elle ne charge aucun fichier local. Le modèle vient du registre MLflow
par son ALIAS, jamais par un numéro de version : promouvoir un nouveau
modèle ne demande aucune modification de ce fichier ni redéploiement.

Elle ne recalcule pas le seuil. Le seuil est une décision économique
validée hors ligne, pas un paramètre d'inférence.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import ALIAS, MODELE, SEUIL_RETENU

# Dans un conteneur, 127.0.0.1 désigne le conteneur lui-même,
# L'adresse doit donc être injectable de l'extérieur.
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5001")
N_CAUSES = 3                    # nombre de capteurs remontés au mécanicien

# Rempli au démarrage par lifespan(). Un dict plutôt que des globales
# séparées : on voit tout ce que l'API garde en mémoire.
ETAT: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
  
    mlflow.set_tracking_uri(TRACKING_URI)

    model = mlflow.xgboost.load_model(f"models:/{MODELE}@{ALIAS}")

    # L'ORDRE des colonnes vient du modèle, pas d'une liste écrite à la
    # main. XGBoost ne vérifie pas les noms : deux colonnes permutées
    # donneraient une prédiction fausse, sans aucune erreur.
    features = list(model.get_booster().feature_names)

    version = mlflow.MlflowClient().get_model_version_by_alias(MODELE, ALIAS)

    ETAT.update(
        model=model,
        features=features,
        explainer=shap.TreeExplainer(model),
        version=version.version,
    )
    print(f"Modèle {MODELE} v{version.version} chargé — {len(features)} features")
    yield
    ETAT.clear()


app = FastAPI(
    title="SAFRAN — Maintenance prédictive moteurs",
    description="Estimation de la durée de vie résiduelle et alerte de dépose.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------- schémas

class Requete(BaseModel):
    engine_id: str = Field(default="inconnu", examples=["FD001_train_047"])
    mesures: dict[str, float] = Field(
        description="Features du silver, nom → valeur. Voir GET /model."
    )


class Cause(BaseModel):
    capteur: str
    contribution: float          # en vols. Négatif = raccourcit la vie du moteur.


class Reponse(BaseModel):
    engine_id: str
    rul_estime: float
    alerte: bool
    seuil: int
    causes: list[Cause]
    modele_version: str


# ---------------------------------------------------------------- routes

@app.get("/health")
def health():
    """Sonde de vivacité. Docker et l'ordonnanceur s'en servent."""
    return {"statut": "ok", "modele_charge": bool(ETAT)}


@app.get("/model")
def modele():
    """Contrat d'entrée : ce que l'appelant doit fournir."""
    return {
        "nom": MODELE,
        "version": ETAT["version"],
        "alias": ALIAS,
        "seuil_alerte": SEUIL_RETENU,
        "features_attendues": ETAT["features"],
    }


@app.post("/predict", response_model=Reponse)
def predict(req: Requete):
    features = ETAT["features"]

    # Échouer vite et clairement. Une feature manquante
    # remplacée par zéro produirait une prédiction plausible et fausse —
    manquantes = [f for f in features if f not in req.mesures]
    if manquantes:
        raise HTTPException(
            status_code=422,
            detail=f"{len(manquantes)} feature(s) manquante(s) : {manquantes[:5]}",
        )

    # Reconstruire le DataFrame DANS L'ORDRE du modèle.
    X = pd.DataFrame([[float(req.mesures[f]) for f in features]], columns=features)

    rul = float(ETAT["model"].predict(X)[0])

    # Les contributions SHAP de cette ligne. On remonte les plus fortes
    # en valeur absolue : ce sont celles qui expliquent l'écart à la
    # moyenne de la flotte, dans un sens comme dans l'autre.
    valeurs = ETAT["explainer"](X).values[0]
    ordre = np.abs(valeurs).argsort()[::-1][:N_CAUSES]

    return Reponse(
        engine_id=req.engine_id,
        rul_estime=round(rul, 1),
        alerte=rul < SEUIL_RETENU,
        seuil=SEUIL_RETENU,
        causes=[
            Cause(capteur=features[k], contribution=round(float(valeurs[k]), 2))
            for k in ordre
        ],
        modele_version=ETAT["version"],
    )