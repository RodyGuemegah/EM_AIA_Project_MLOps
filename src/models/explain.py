"""Explicabilité du modèle par valeurs de Shapley.

Le seuil dit QUAND alerter. Ce module dit POURQUOI.

Deux lectures, deux usages :
  - globale : sur quels capteurs le modèle s'appuie-t-il ? Contrôle de
    plausibilité physique, et argument de soutenance.
  - locale  : pourquoi CE moteur alerte-t-il ? C'est ce qui rend l'alerte
    exploitable par un mécanicien, et ce qu'exige l'AI Act à l'article 13
    (transparence envers l'utilisateur d'un système à haut risque).

POURQUOI TreeExplainer ET PAS KernelExplainer
----------------------------------------------
KernelExplainer est universel : il traite le modèle en boîte noire et
approxime les contributions par échantillonnage. Coûteux et approximatif.
TreeExplainer exploite la structure des arbres : il parcourt les chemins
de décision et calcule les valeurs de Shapley de façon EXACTE, en temps
polynomial. XGBoost étant un ensemble d'arbres, on aurait tort de s'en
priver.

Ce module NE RÉENTRAÎNE PAS. Il charge le modèle livré — même objet que
celui qu'interrogera l'API. Expliquer un autre modèle que celui déployé
n'aurait aucun sens.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")          # pas d'affichage : on écrit des fichiers
import matplotlib.pyplot as plt
import shap

from src.data.dataset import SEED, load_silver, split_par_moteur

MODEL_PATH = Path("models/xgboost.joblib")
FIGURES = Path("docs/figures")
N_ECHANTILLON = 2000           # borne le calcul, sans changer la conclusion


def load_data():

    bundle = joblib.load(MODEL_PATH)
    df = load_silver(subset=bundle["subset"], split="train")
    _, test = split_par_moteur(df, test_size=0.2, seed=SEED)
    return bundle["model"], test, bundle["features"]


def calculate(model, test, features):

    X = test[features]
    if len(X) > N_ECHANTILLON:
        X = X.sample(N_ECHANTILLON, random_state=SEED)

    explainer = shap.TreeExplainer(model)
    return explainer(X), X


def figure_globale(valeurs):

    FIGURES.mkdir(parents=True, exist_ok=True)

    shap.plots.bar(valeurs, max_display=15, show=False)
    plt.title("Contribution moyenne des capteurs à la prédiction de RUL")
    plt.tight_layout()
    plt.savefig(FIGURES / "shap_global.png", dpi=150)
    plt.close()

    # Le beeswarm ajoute ce que la barre masque : le SENS. Chaque point est
    # un vol ; sa couleur est la valeur du capteur, sa position horizontale
    # sa contribution. On y lit « capteur haut → RUL bas », qui est la
    # relation physique qu'on cherche à vérifier.
    shap.plots.beeswarm(valeurs, max_display=15, show=False)
    plt.title("Sens de l'influence : valeur du capteur vs effet sur le RUL")
    plt.tight_layout()
    plt.savefig(FIGURES / "shap_beeswarm.png", dpi=150)
    plt.close()


def figure_locale(valeurs, X, model, features):

    i = int(model.predict(X).argmin())     # position, pas index pandas

    shap.plots.waterfall(valeurs[i], max_display=12, show=False)
    plt.title("Pourquoi ce moteur déclenche-t-il l'alerte ?")
    plt.tight_layout()
    plt.savefig(FIGURES / "shap_local.png", dpi=150)
    plt.close()
    return i


def run():
    model, test, features = load_data()
    valeurs, X = calculate(model, test, features)

    figure_globale(valeurs)
    i = figure_locale(valeurs, X, model, features)

    # Classement en clair, pour le copier dans la note de synthèse.
    import numpy as np
    ordre = np.abs(valeurs.values).mean(axis=0).argsort()[::-1][:10]
    print(f"{'capteur':<28}{'contribution moy.':>18}")
    print("-" * 46)
    for k in ordre:
        print(f"{features[k]:<28}{np.abs(valeurs.values[:, k]).mean():>17.2f}v")

    print(f"\nMoteur expliqué en local : RUL prédit {model.predict(X)[i]:.1f} vols")
    print(f"Figures écrites dans {FIGURES}/")


if __name__ == "__main__":
    run()