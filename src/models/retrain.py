"""Réentraînement après dérive : la boucle MLOps qui se referme.

Le module de supervision a établi que le modèle FD001 laisse passer
48 % des pannes sur FD003. Ce module y répond en réapprenant sur
FD001 + FD003 réunis.

FD004 RESTE HORS DE L'APPRENTISSAGE, DÉLIBÉRÉMENT
--------------------------------------------------
Entraîner sur les trois flottes puis constater que tout va bien ne
démontrerait rien. En gardant FD004 inconnue, on sépare deux questions :
ce que le réentraînement CORRIGE (la flotte observée) et ce qu'il ne
corrige pas (une flotte encore jamais vue). La seconde réponse est la
plus utile : elle dit à l'exploitant que superviser reste nécessaire.

CE QUI N'EST PAS FAIT ICI, ET C'EST VOULU
------------------------------------------
Ce module N'ALIAS PAS le nouveau modèle en production. Il enregistre
une version au registre et s'arrête là. La promotion est un acte humain
tracé, après comparaison des métriques (ADR 0004).
"""

from __future__ import annotations

import mlflow
import mlflow.xgboost
import pandas as pd
from mlflow.models import infer_signature

from src.config import MODELE, TRACKING_URI
from src.data.dataset import SEED, load_silver, select_features, split_par_moteur
from src.models.threshold import chercher_seuil
from src.models.xgboost_model import PARAMS, evaluate, train_model
from src.monitoring.drift import evaluer

APPRENTISSAGE = ["FD001", "FD003"]
JAMAIS_VU = "FD004"
EXPERIENCE = "rul-moteur-v2"


def charger(subsets):
    """Réunit plusieurs flottes en un seul jeu.

    concat aligne les colonnes par leur NOM et remplit les absentes par
    NaN : si le silver a supprimé un capteur plat sur FD001 mais pas sur
    FD003, la colonne existe pour l'une et manque pour l'autre. XGBoost
    traite ces NaN nativement — c'est précisément la propriété qui a
    motivé son choix (ADR 0006).
    """
    parts = [load_silver(subset=s, split="train") for s in subsets]
    df = pd.concat(parts, ignore_index=True)
    print(f"{' + '.join(subsets)} : {len(df):,} vols, "
          f"{df.engine_id.nunique()} moteurs, {df.shape[1]} colonnes")
    return df


def run():
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIENCE)

    df = charger(APPRENTISSAGE)

    # Découpage par MOTEUR sur l'ensemble réuni. Les deux flottes sont
    # mélangées avant le tirage : un découpage flotte par flotte
    # risquerait de sur-représenter l'une dans l'examen.
    train, test = split_par_moteur(df, test_size=0.2, seed=SEED)
    features = select_features(train)
    print(f"Apprentissage : {train.engine_id.nunique()} moteurs · "
          f"Examen : {test.engine_id.nunique()} · Features : {len(features)}\n")

    model = train_model(train, features)
    metriques = evaluate(model, test, features, nom="XGBoost réentraîné")

    # LE SEUIL DOIT ÊTRE RECALCULÉ. Un nouveau modèle a un nouveau biais,
    # donc une nouvelle marge nécessaire (ADR 0001). Réutiliser 10
    # appliquerait la marge d'un modèle à un autre.
    pred = model.predict(test[features])
    table = chercher_seuil(test, pred)
    meilleur = table.loc[table.cout.idxmin()]
    seuil = int(meilleur.seuil)
    print(f"\nNouveau seuil optimal : {seuil} vols "
          f"(ancien : 10) — {meilleur.cout:,.0f} $")

    # --- Contrôle sur les trois flottes -------------------------------
    lignes = []
    for s in APPRENTISSAGE:
        # Uniquement les moteurs d'EXAMEN : le modèle a vu les autres.
        part = test[test.fd_subset == s]
        lignes.append(evaluer(s, model, features, seuil=seuil, df=part))

    # FD004 dans son intégralité : aucun de ses moteurs n'a servi.
    lignes.append(evaluer(JAMAIS_VU, model, features, seuil=seuil))

    controle = pd.DataFrame(lignes).set_index("sous_jeu")
    print(f"\n{'=' * 70}\nCONTRÔLE APRÈS RÉENTRAÎNEMENT\n{'=' * 70}")
    print(controle.to_string(float_format=lambda v: f"{v:,.2f}"))

    # --- Enregistrement ------------------------------------------------
    with mlflow.start_run(run_name="reentrainement-FD001-FD003"):
        mlflow.set_tags({
            "scenario": "reentrainement",
            "apprentissage": "+".join(APPRENTISSAGE),
            "jamais_vu": JAMAIS_VU,
        })
        mlflow.log_params({**PARAMS, "n_features": len(features),
                           "seuil_recalcule": seuil})
        mlflow.log_metrics(metriques)
        for ligne in lignes:
            s = ligne["sous_jeu"]
            mlflow.log_metrics({f"{s}_{k}": v for k, v in ligne.items()
                                if k != "sous_jeu"})

        signature = infer_signature(test[features].astype("float64"), pred)
        mlflow.xgboost.log_model(model, name="model", signature=signature,
                                 registered_model_name=MODELE)

    print("\nVersion enregistrée au registre. "
          "L'alias `production` n'a PAS été déplacé (ADR 0004).")
    return controle


if __name__ == "__main__":
    run()