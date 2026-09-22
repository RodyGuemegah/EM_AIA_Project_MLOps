"""Scénario de dérive : le modèle FD001 confronté à d'autres flottes.

Le modèle en production a été entraîné sur FD001 — une condition de vol,
un mode de défaillance. On l'applique tel quel à FD003 (deux modes) et
FD004 (six conditions, deux modes), sans réentraînement.

Transposition métier : un modèle calibré sur une flotte court-courrier
en climat tempéré, appliqué à du long-courrier en zone désertique.
C'est ce qui arrive en production quand la flotte évolue.

CE QUI EST MESURÉ, ET POURQUOI DANS CET ORDRE
----------------------------------------------
1. la dérive de SCHÉMA  : combien de features manquent
2. la dérive de PERFORMANCE : RMSE, MAE
3. la dérive de DÉCISION : pannes ratées au seuil de 10
4. le COÛT en dollars, ramené au moteur

Les trois premières sont techniques. La quatrième est la seule qui
permette d'arbitrer un réentraînement.
"""

from __future__ import annotations
import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.config import ALIAS, MODELE, SEUIL_RETENU, TRACKING_URI
from src.data.dataset import SEED, load_silver, split_par_moteur
from src.models.threshold import chercher_seuil, cout_total, simuler_politique

SUBSETS = ["FD001", "FD003", "FD004"]
EXPERIENCE = "rul-moteur-v2"


def charger_modele():
    """Le modèle EN PRODUCTION, pas un modèle réentraîné pour l'occasion.

    On mesure la dérive de ce qui est réellement déployé. Reconstruire
    un modèle ici mesurerait autre chose.
    """
    mlflow.set_tracking_uri(TRACKING_URI)
    model = mlflow.xgboost.load_model(f"models:/{MODELE}@{ALIAS}")
    return model, list(model.get_booster().feature_names)


def evaluer(subset, model, features, seuil=SEUIL_RETENU, df=None):
    if df is None:
        df = load_silver(subset=subset, split="train")
        if subset == "FD001":
            _, df = split_par_moteur(df, test_size=0.2, seed=SEED)

    # crée en NaN celles qui manquent. XGBoost les traite nativement :
    # chaque nœud a appris une direction par défaut pour les manquants.
    manquantes = [f for f in features if f not in df.columns]
    X = df.reindex(columns=features)

    pred = model.predict(X)
    reel = df.rul.to_numpy()

    # Dérive de DÉCISION, au seuil calibré sur FD001. C'est le point
    # central : on n'a pas le droit de recalibrer avant d'avoir constaté.
    res = simuler_politique(df, pred, seuil=seuil)
    n_moteurs = df.engine_id.nunique()

    # Le coût doit être ramené AU MOTEUR : FD001 compte 20 moteurs
    # d'examen, FD004 en compte plus de 200. Comparer des totaux
    # comparerait des tailles de flotte, pas des qualités de modèle.
    cout = cout_total(res)

    # Et pour mesurer l'ampleur du décalage : quel seuil AURAIT été
    # optimal sur cette flotte ?
    table = chercher_seuil(df, pred)
    meilleur = table.loc[table.cout.idxmin()]

    return {
        "sous_jeu": subset,
        "moteurs": n_moteurs,
        "features_manquantes": len(manquantes),
        "rmse": float(np.sqrt(mean_squared_error(reel, pred))),
        "mae": float(mean_absolute_error(reel, pred)),
        "ratees": int(res["ratees"]),
        "cout_par_moteur": cout / n_moteurs,
        "seuil_ideal": int(meilleur.seuil),
    }


def run():
    model, features = charger_modele()
    print(f"Modèle {MODELE}@{ALIAS} — {len(features)} features attendues\n")

    lignes = [evaluer(s, model, features) for s in SUBSETS]
    table = pd.DataFrame(lignes).set_index("sous_jeu")

    # Dégradation relative à la référence FD001.
    ref = table.loc["FD001"]
    table["rmse_x"] = (table.rmse / ref.rmse).round(2)
    table["cout_x"] = (table.cout_par_moteur / ref.cout_par_moteur).round(2)
    table["taux_ratees_%"] = (100 * table.ratees / table.moteurs).round(1)

    print(table.to_string(float_format=lambda v: f"{v:,.2f}"))

    # Chaque sous-jeu devient un run comparable au nominal dans MLflow.
    mlflow.set_experiment(EXPERIENCE)
    for ligne in lignes:
        with mlflow.start_run(run_name=f"derive-{ligne['sous_jeu']}"):
            mlflow.set_tags({
                "scenario": "derive",
                "sous_jeu": ligne["sous_jeu"],
                "modele_source": f"{MODELE}@{ALIAS}",
            })
            mlflow.log_params({
                "seuil_applique": SEUIL_RETENU,
                "features_manquantes": ligne["features_manquantes"],
            })
            mlflow.log_metrics({
                k: v for k, v in ligne.items()
                if k not in ("sous_jeu", "features_manquantes")
            })

    return table


if __name__ == "__main__":
    run()