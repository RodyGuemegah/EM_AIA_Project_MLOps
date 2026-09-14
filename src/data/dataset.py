"""Chargement des données d'entraînement depuis la couche silver.

Le silver est produit par `safran-data-platform`. Ce dépôt en est un
CLIENT : il lit le lac, il ne l'alimente jamais.
"""


from __future__ import annotations

import pandas as pd
import pyarrow.parquet as pq
from sklearn.model_selection import GroupShuffleSplit
from src.storage import get_lake_filesystem, lake_path

DATASET = "engine_features"
RUL_CAP = 125
SEED = 42

def load_silver(subset="FD001", split="train", columns=None, filesystem=None) -> pd.DataFrame:
    """Lit le silver depuis le lac.

    `fd_subset` et `split` sont des COLONNES du dataset, pas des dossiers :
    on les filtre, on ne les met pas dans le chemin.
    """
    if filesystem is None:
        filesystem = get_lake_filesystem()

    filtres = []
    if subset is not None:
        filtres.append(("fd_subset", "=", subset))
    if split is not None:
        filtres.append(("split", "=", split))

    table = pq.read_table(
        lake_path("silver", DATASET),
        filesystem=filesystem,
        columns=columns,
        filters=filtres or None,
    )
    # rolling() suit l'ordre des lignes : sans ce tri, tout calcul
    # séquentiel en aval serait faux.
    return table.to_pandas().sort_values(["engine_id", "time_in_cycles"]).reset_index(drop=True)

def split_par_moteur(df, test_size=0.2, seed=SEED):
    """80 % des moteurs pour apprendre, 20 % pour l'examen.

    JAMAIS ligne par ligne : deux cycles consécutifs du même moteur sont
    quasi identiques. Mesuré : RMSE 6,85 par ligne contre 17,50 par moteur.
    """
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    idx_train, idx_test = next(gss.split(df, groups=df["engine_id"]))
    return df.iloc[idx_train], df.iloc[idx_test]

def select_features(df) -> list[str]:
    """Calcule la liste des colonnes admissibles pour le modèle.

    RÈGLE : le modèle ne reçoit que ce qu'un CAPTEUR a mesuré sur le moteur.
    Le préfixe attrape les mesures brutes ET leurs dérivées d'historique
    (`_moy20`, `_pente`, `_derive`) — ajouter une quatrième dérivée ne
    demandera aucune modification ici.

    Sont exclus, et chaque exclusion est mesurée ou raisonnée :
      - les dates      : +21 % d'erreur en conditions de production
      - les identifiants : le modèle mémoriserait au lieu de généraliser
      - les aéroports  : 0,5 % d'importance, tirés au hasard donc bruit
      - la traçabilité : décrit le fichier, pas le moteur
    """
    return [c for c in df.columns if c.startswith(("sensor_", "op_setting_"))]