"""Suivi d'expériences et registre de modèles (MLflow).

Ce module N'ENTRAÎNE RIEN. Il orchestre les modules existants et
enregistre ce qu'ils produisent. Un module de suivi qui réentraînerait
à sa façon décrirait un modèle différent de celui qu'on livre : le
cahier de laboratoire doit décrire l'expérience réelle.

CE QU'IL ENREGISTRE, ET POURQUOI CHAQUE CHOSE
----------------------------------------------
paramètres  : pour rejouer le run à l'identique
métriques   : RMSE/MAE (technique) ET coût en dollars (métier).
              Les deux, parce qu'un modèle se juge sur les deux.
artefacts   : figures SHAP + table des seuils — les preuves visuelles
modèle      : versionné dans le REGISTRE, avec sa signature d'entrée.
              C'est ce que l'API ira chercher : plus jamais un chemin
              de fichier en dur.
"""

from __future__ import annotations

from pathlib import Path

import mlflow
import mlflow.xgboost
from mlflow.models import infer_signature

from src.models.xgboost_model import PARAMS, evaluate, load_data, train_model
from src.models.threshold import chercher_seuil

TRACKING_URI = "http://127.0.0.1:5000"
EXPERIENCE = "rul-moteur"          # le classeur
MODELE = "rul-xgboost"             # le nom dans le registre
FIGURES = Path("docs/figures")
TABLE_SEUILS = Path("docs/seuils_couts.csv")


def run(subset="FD001"):
    # set_experiment CRÉE le classeur s'il n'existe pas, le réutilise sinon.
    # Sans lui, tout atterrirait dans "Default" — ingérable dès le 3e run.
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIENCE)

    train, test, features = load_data(subset)

    # Tout ce qui est DANS le bloc appartient au run. À la sortie, MLflow
    # le ferme et l'horodate. En cas d'exception, il le marque FAILED —
    # un essai raté reste tracé, c'est le principe du cahier.
    with mlflow.start_run(run_name=f"xgboost-{subset}"):

        # --- Les réglages -------------------------------------------------
        mlflow.log_params(PARAMS)
        mlflow.log_params({
            "subset": subset,
            "n_features": len(features),
            "moteurs_train": train.engine_id.nunique(),
            "moteurs_test": test.engine_id.nunique(),
        })

        # Les tags ne sont pas des paramètres : ils servent à FILTRER dans
        # l'interface ("montre-moi tous les runs de type nominal").
        mlflow.set_tags({
            "modele": "xgboost",
            "scenario": "nominal",       # deviendra "derive" demain
            "temoin_rmse": 21.98,
        })

        # --- L'entraînement, délégué --------------------------------------
        model = train_model(train, features)
        metriques = evaluate(model, test, features)
        mlflow.log_metrics(metriques)

        # --- La lecture métier --------------------------------------------
        # Une RMSE ne parle à personne en comité de direction. Un coût, si.
        pred = model.predict(test[features])
        table = chercher_seuil(test, pred)
        meilleur = table.loc[table.cout.idxmin()]

        mlflow.log_metrics({
            "seuil_optimal": float(meilleur.seuil),
            "cout_optimal_usd": float(meilleur.cout),
            "pannes_ratees": float(meilleur.ratees),
            "cout_sans_modele_usd": float(table.cout.max()),
        })

        # --- Les preuves ---------------------------------------------------
        TABLE_SEUILS.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(TABLE_SEUILS, index=False)
        mlflow.log_artifact(str(TABLE_SEUILS))

        if FIGURES.exists():
            mlflow.log_artifacts(str(FIGURES), artifact_path="shap")

        # --- Le modèle, versionné ------------------------------------------
        # La SIGNATURE est le contrat d'entrée : noms et types des colonnes
        # attendues. Sans elle, l'API pourrait envoyer les features dans le
        # mauvais ordre et XGBoost répondrait un chiffre faux sans broncher.
        # C'est exactement le risque qu'on avait paré en sauvegardant
        # `features` dans le joblib — MLflow le fait proprement.
        signature = infer_signature(test[features].astype("float64"), pred)

        mlflow.xgboost.log_model(
            model,
            name="model",
            signature=signature,
            registered_model_name=MODELE,   # ← crée une VERSION au registre
        )

        print(f"\nRun enregistré. Seuil {meilleur.seuil:.0f} — "
              f"{meilleur.cout:,.0f} $ — {meilleur.ratees:.0f} panne(s) ratée(s)")
        print(f"Interface : {TRACKING_URI}")


if __name__ == "__main__":
    run()