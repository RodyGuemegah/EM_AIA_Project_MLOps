"""Tests de la logique de décision.

Aucune dépendance au lac, au registre ni aux données réelles : la
politique de dépose est de l'arithmétique sur un DataFrame. C'est ce
qui permet à la CI de tourner en trente secondes sur une machine nue.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import SEUIL_RETENU
from src.models.threshold import (
    COUT_AOG,
    COUT_DEPOSE,
    DELAI_INTERVENTION,
    VIE_MOYENNE,
    chercher_seuil,
    cout_total,
    simuler_politique,
)

N_MOTEURS = 5
DUREE = 30


def flotte(n=N_MOTEURS, duree=DUREE):
    """Flotte factice : n moteurs allant chacun jusqu'à la panne.

    Le RUL décroît de duree-1 à 0, comme dans le silver.
    """
    return pd.DataFrame([
        {"engine_id": f"M{i}", "time_in_cycles": t, "rul": duree - t}
        for i in range(n) for t in range(1, duree + 1)
    ])


def test_seuil_sous_delai():
    """Un seuil ≤ délai d'intervention ne peut sauver aucun moteur.

    Contrainte physique : on ne dépose pas en 3 vols un moteur auquel
    il en reste 2. Vrai même pour un modèle sans erreur.
    """
    f = flotte()
    parfait = f.rul.to_numpy()

    for seuil in range(1, DELAI_INTERVENTION + 1):
        res = simuler_politique(f, parfait, seuil)
        assert res["deposes"] == 0, f"seuil {seuil} : dépose impossible"
        assert res["ratees"] == N_MOTEURS


def test_seuil_minimal_utile():
    """Juste au-dessus du délai, un modèle parfait sauve tout.

    Borne le problème par le haut : si ce test échoue, c'est la
    simulation qui est fausse, pas le modèle.
    """
    f = flotte()
    res = simuler_politique(f, f.rul.to_numpy(), DELAI_INTERVENTION + 1)

    assert res["ratees"] == 0
    assert res["deposes"] == N_MOTEURS


def test_modele_muet():
    """Un modèle systématiquement optimiste ne déclenche jamais."""
    f = flotte()
    res = simuler_politique(f, [999] * len(f), seuil=SEUIL_RETENU)

    assert res["ratees"] == N_MOTEURS
    assert res["vols_gaches"] == 0


def test_cout_somme():
    """Le coût est une somme vérifiable à la main, pas une boîte noire."""
    res = {"ratees": 2, "deposes": 3, "vols_gaches": 10}
    attendu = 2 * COUT_AOG + 3 * COUT_DEPOSE + 10 * COUT_DEPOSE / VIE_MOYENNE

    assert cout_total(res) == pytest.approx(attendu)


def test_cout_croissant():
    """Passé l'optimum, monter le seuil ne fait que gâcher des vols.

    C'est la branche droite de la courbe en L : strictement
    croissante, sinon le balayage renverrait n'importe quoi.
    """
    f = flotte()
    table = chercher_seuil(f, f.rul.to_numpy())
    sans_ratee = table[table.ratees == 0].sort_values("seuil")

    assert sans_ratee.cout.is_monotonic_increasing


def test_seuil_configure():
    """Garde-fou : SEUIL_RETENU doit rester au-dessus du délai atelier.

    Verrouille l'ADR 0001. En deçà, le système n'émettrait plus que
    des alertes inexploitables.
    """
    assert SEUIL_RETENU > DELAI_INTERVENTION