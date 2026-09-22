
from __future__ import annotations

import mlflow
from mlflow.metrics import mae, rmse, rmse
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src.config import TRACKING_URI
from src.data.dataset import SEED
from src.models.threshold import chercher_seuil
from src.models.xgboost_model import PARAMS, evaluate, load_data, train_model

EXPERIENCE = "rul-moteur-v2"

PARAMS_RF = {
    "n_estimators": 100,        # même nombre d'arbres que XGBoost
    "max_depth": None,          # profondeur libre : le régime naturel de RF
    "min_samples_leaf": 2,      # garde-fou léger contre le surapprentissage
    "random_state": SEED,
    "n_jobs": -1,
}


def train_rf(train, features):
    model = RandomForestRegressor(**PARAMS_RF)
    model.fit(train[features], train["rul"])
    return model


def measure(nom, model, test, features):
    """Métriques techniques ET économiques, dans les mêmes conditions."""
    print(f"\n{'=' * 58}\n{nom}\n{'=' * 58}")
    metriques = evaluate(model, test, features, nom=nom)

    # Le coût est le juge de paix : deux modèles de RMSE voisine peuvent
    # coûter très différemment selon leur comportement PRÈS DE LA PANNE.
    pred = model.predict(test[features])
    table = chercher_seuil(test, pred)
    meilleur = table.loc[table.cout.idxmin()]

    metriques.update(
        seuil_optimal=float(meilleur.seuil),
        cout_optimal_usd=float(meilleur.cout),
        pannes_ratees=float(meilleur.ratees),
    )
    print(f"\nSeuil optimal : {meilleur.seuil:.0f} vols — "
          f"{meilleur.cout:,.0f} $ — {meilleur.ratees:.0f} panne(s) ratée(s)")
    return metriques


def run(subset="FD001"):
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIENCE)

    train, test, features = load_data(subset)
    print(f"{train.engine_id.nunique()} moteurs d'apprentissage, "
          f"{test.engine_id.nunique()} d'examen, {len(features)} features")

    resultats = {}
    for nom, entraineur, params in [
        ("XGBoost", train_model, PARAMS),
        ("Random Forest", train_rf, PARAMS_RF),
    ]:
        model = entraineur(train, features)
        metriques = measure(nom, model, test, features)
        resultats[nom] = metriques

        # Un run par modèle, dans la même expérience : MLflow les affiche
        # côte à côte, et le tag permet de les filtrer.
        with mlflow.start_run(run_name=f"comparaison-{nom.lower().replace(' ', '-')}"):
            mlflow.set_tags({"scenario": "comparaison", "modele": nom})
            mlflow.log_params({str(k): v for k, v in params.items()})
            mlflow.log_metrics(metriques)

    # Verdict
    table = pd.DataFrame(resultats).T
    print(f"\n{'=' * 58}\nVERDICT\n{'=' * 58}")
    print(table[["rmse", "mae", "seuil_optimal",
                 "cout_optimal_usd", "pannes_ratees"]].to_string(
        float_format=lambda v: f"{v:,.2f}"))

    gagnant = table.cout_optimal_usd.idxmin()
    print(f"\nCoût le plus faible : {gagnant}")
    return table

if __name__ == "__main__":
    run()