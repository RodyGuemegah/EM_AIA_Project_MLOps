"""Tests de préparation des données — les deux pièges du projet."""

from __future__ import annotations

import pandas as pd

from src.data.dataset import SEED, select_features, split_par_moteur


def jeu(n_moteurs=20, duree=50):
    """Jeu factice au format silver, réduit au strict nécessaire."""
    return pd.DataFrame([
        {"engine_id": f"M{i}", "time_in_cycles": t,
         "rul": duree - t, "sensor_01": 1.0}
        for i in range(n_moteurs) for t in range(1, duree + 1)
    ])


def test_features_filtrees():
    """Seules les mesures moteur passent.

    Une date ou un aéroport ferait apprendre « les moteurs de janvier
    tombent en panne » — vrai du jeu de données, faux du monde.
    """
    colonnes = [
        "sensor_01", "sensor_01_moy20", "sensor_01_pente", "op_setting_1",
        "engine_id", "rul", "flight_date", "airport_origin",
        "fd_subset", "ingested_at",
    ]
    features = select_features(pd.DataFrame(columns=colonnes))

    assert set(features) == {
        "sensor_01", "sensor_01_moy20", "sensor_01_pente", "op_setting_1"
    }


def test_pas_de_fuite():
    """Aucun moteur ne figure dans les deux jeux.

    LE piège du projet : deux cycles consécutifs d'un même moteur sont
    quasi identiques. Mesuré : RMSE 6,85 par ligne contre 17,50 par
    moteur.
    """
    df = jeu()
    train, test = split_par_moteur(df, test_size=0.2, seed=SEED)

    assert set(train.engine_id) & set(test.engine_id) == set()
    assert test.engine_id.nunique() == 4
    assert len(train) + len(test) == len(df)


def test_split_reproductible():
    """Même graine, même découpage.

    Sans cela, aucune comparaison de modèles n'a de sens (ADR 0006).
    """
    df = jeu()
    a, _ = split_par_moteur(df, test_size=0.2, seed=SEED)
    b, _ = split_par_moteur(df, test_size=0.2, seed=SEED)

    assert set(a.engine_id) == set(b.engine_id)