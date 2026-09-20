"""Seuil de décision : à partir de quel RUL prédit immobilise-t-on un moteur ?

Le modèle produit un nombre. Le seuil le transforme en action. C'est une
décision MÉTIER, pas technique : si SAFRAN révise ses coûts, le seuil bouge
sans qu'on réentraîne quoi que ce soit.

POURQUOI CE TRAVAIL EST NÉCESSAIRE
-----------------------------------
Le modèle surestime le RUL dans 91 % des cas en zone critique : il annonce
plus de temps qu'il n'en reste. Un seuil naïf laisserait donc passer des
pannes. Le décalage compense ce biais mesuré.

LE PIÈGE ÉVITÉ
--------------
Compter seulement les pannes ratées rendrait le seuil le plus haut toujours
optimal — on déposerait des moteurs neufs. Le coût de la VIE GÂCHÉE est donc
inclus : déposer un moteur qui avait 80 vols devant lui, c'est jeter 80 vols
de potentiel payé.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Coûts en dollars. Sources et hypothèses : docs/adr/ADR-seuil.md
# Immobilisation non planifiée : 48 h à 10 000 $/h (borne basse IATA 2025).
COUT_AOG = 480_000
# Dépose planifiée : créneau réservé, moteur de rechange sur place.
COUT_DEPOSE = 50_000

# Vols nécessaires pour organiser l'intervention. En deçà, l'alerte est
# trop tardive pour servir : on la compte comme une panne ratée.
DELAI_INTERVENTION = 3

# Vie moyenne mesurée sur FD001 (médiane 199, moyenne ~206 cycles).
VIE_MOYENNE = 206

# Résultat mesuré par chercher_seuil() sur FD001, jeu d'examen de 20 moteurs.
# Valeur retenue en production. Recalculer après tout réentraînement.
SEUIL_RETENU = 10

SEUILS = range(1, 61)
RATIOS_SENSIBILITE = [1, 2, 5, 10, 20, 50]


def simuler_politique(test: pd.DataFrame, pred, seuil: int) -> dict:

    d = test.assign(_pred=pred)
    ratees = deposes = vols_gaches = 0

    for _, g in d.groupby("engine_id"):
        g = g.sort_values("time_in_cycles")
        alerte = g[g._pred <= seuil]

        if alerte.empty:
            ratees += 1
            continue

        rul_reel = int(alerte.rul.iloc[0])
        if rul_reel <= DELAI_INTERVENTION:
            ratees += 1
        else:
            deposes += 1
            vols_gaches += rul_reel

    return {"seuil": seuil, "ratees": ratees,
            "deposes": deposes, "vols_gaches": vols_gaches}


def cout_total(res: dict, cout_aog=COUT_AOG, cout_depose=COUT_DEPOSE) -> float:

    cout_par_vol = cout_depose / VIE_MOYENNE
    return (res["ratees"] * cout_aog
            + res["deposes"] * cout_depose
            + res["vols_gaches"] * cout_par_vol)


def chercher_seuil(test, pred, cout_aog=COUT_AOG) -> pd.DataFrame:
    """Balaie les seuils candidats et renvoie le tableau complet."""
    lignes = []
    for seuil in SEUILS:
        res = simuler_politique(test, pred, seuil)
        res["cout"] = cout_total(res, cout_aog=cout_aog)
        lignes.append(res)
    return pd.DataFrame(lignes)


def sensibilite(test, pred) -> pd.DataFrame:

    lignes = []
    for ratio in RATIOS_SENSIBILITE:
        tab = chercher_seuil(test, pred, cout_aog=ratio * COUT_DEPOSE)
        meilleur = tab.loc[tab.cout.idxmin()]
        lignes.append({"ratio": ratio, "seuil_optimal": int(meilleur.seuil),
                       "ratees": int(meilleur.ratees)})
    return pd.DataFrame(lignes)

if __name__ == "__main__":
    import joblib
    from src.models.xgboost_model import load_data, MODEL_PATH

    paquet = joblib.load(MODEL_PATH)
    _, test, _ = load_data()
    pred = paquet["model"].predict(test[paquet["features"]])

    tab = chercher_seuil(test, pred)
    print(tab.to_string(index=False))

    meilleur = tab.loc[tab.cout.idxmin()]
    print(f"\nSeuil optimal : {int(meilleur.seuil)} vols")
    print(f"  pannes ratées : {int(meilleur.ratees)}/20")
    print(f"  coût total    : {meilleur.cout:,.0f} $")

    print("\nSensibilité au rapport de coûts :")
    print(sensibilite(test, pred).to_string(index=False))