"""Modèle XGBoost sur les features d'historique du silver.

C'est le modèle livré. Il se compare au témoin — régression linéaire sur
capteurs bruts, RMSE 21,98 — dans des conditions identiques : mêmes moteurs
FD001, même graine, mêmes 20 moteurs d'examen. Seules les features changent :
15 contre 87.

CE QUI N'EST PAS FAIT ICI, ET C'EST VOULU
------------------------------------------
Pas de plafonnement du RUL : le silver l'applique déjà à 125.
Pas de normalisation : les arbres de décision n'en ont pas besoin. Ils
découpent sur des seuils, l'échelle des variables leur est indifférente.
C'est un avantage face à la régression linéaire, dont les coefficients
étaient incomparables entre eux faute d'échelle commune.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from src.data.dataset import SEED, load_silver, select_features, split_par_moteur

MODEL_PATH = Path("models/xgboost.joblib")

PARAMS = {
    "n_estimators": 100,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": SEED,
    "n_jobs": -1,
}

def load_data(subset="FD001"):

    df = load_silver(subset=subset, split="train")

    assert df.rul.max() <= 125, f"RUL non plafonnée en amont : max {df.rul.max()}"

    train, test = split_par_moteur(df, test_size=0.2, seed=SEED)
    features = select_features(train)
    return train, test, features 

def train_model(train, features):
    
    model = XGBRegressor(**PARAMS)
    model.fit(train[features], train["rul"])
    return model

def evaluate(model, test, features, temoin_rmse=21.98, nom="XGBoost"):
    
    pred = model.predict(test[features])
    reel = test["rul"].to_numpy()

    rmse = float(np.sqrt(mean_squared_error(reel, pred)))
    mae = float(mean_absolute_error(reel, pred))

    print(f"{'':22}{'RMSE':>8}{'MAE':>8}")
    print(f"{'Témoin (linéaire)':<22}{temoin_rmse:>8.2f}{'':>8}")
    print(f"{nom:<22}{rmse:>8.2f}{mae:>8.2f}")
    print(f"{'Gain':<22}{temoin_rmse - rmse:>+8.2f}"
          f"  ({100 * (temoin_rmse - rmse) / temoin_rmse:+.0f} %)")

    # Erreur par tranche de RUL — la lecture métier.
    # `erreur` est SIGNÉE : positive = le modèle surestime le RUL, donc
    # annonce plus de temps qu'il n'en reste. C'est le faux négatif.
    erreur = pred - reel
    print(f"\n{'RUL réel restant':<24}{'n':>7}{'erreur moy.':>14}{'surestime':>12}")
    print("-" * 57)
    for bas, haut, nom in [
        (0, 10, "0-10 vols (imminent)"),
        (10, 25, "10-25 vols"),
        (25, 50, "25-50 vols"),
        (50, 126, "50+ (moteur jeune)"),
    ]:
        m = (reel >= bas) & (reel < haut)
        if not m.any():
            continue
        print(f"{nom:<24}{m.sum():>7}{np.abs(erreur[m]).mean():>13.1f}v"
              f"{100 * (erreur[m] > 0).mean():>11.0f}%")

    return {"rmse": rmse, "mae": mae}

def run (subset="FD001"):
    """Enchaîne tout et sauvegarde le modèle avec son contexte."""
    train, test, features = load_data(subset)

    print(f"Apprentissage : {train.engine_id.nunique()} moteurs, {len(train):,} vols")
    print(f"Examen        : {test.engine_id.nunique()} moteurs, {len(test):,} vols")
    print(f"Features      : {len(features)}\n")

    model = train_model(train, features)
    metriques = evaluate(model, test, features)

    # On sauvegarde le modèle ET tout ce qu'il faut pour le rejouer.
    # Sans la liste des features dans l'ORDRE, l'API ne saurait pas quelles
    # colonnes envoyer — et XGBoost calculerait un résultat faux sans prévenir.
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": features,
            "params": PARAMS,
            "seed": SEED,
            "subset": subset,
            **metriques,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
        MODEL_PATH,
    )
    print(f"\nModèle sauvegardé : {MODEL_PATH}")
    return metriques


if __name__ == "__main__":
    run() 