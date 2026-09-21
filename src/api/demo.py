from __future__ import annotations

import json

import requests

from src.data.dataset import load_silver, split_par_moteur, SEED

API = "http://127.0.0.1:8000"

def calling(ligne, features):
    "transforme une ligne de dataframe en JSON et l'envoie à l'API"
    response = requests.post(
        f"{API}/predict",
        json={
            "engine_id": str(ligne.engine_id),
            "mesures": {f: float(ligne[f]) for f in features},
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def main():
    features = requests.get(f"{API}/model").json()["features_attendues"]
    df = load_silver(subset="FD001", split="train")
    _, test = split_par_moteur(df, test_size=0.2, seed=SEED)


    cas = {
        "MOTEUR EN FIN DE VIE": test.loc[test.rul.idxmin()],
        "MOTEUR JEUNE":         test.loc[test.rul.idxmax()],
    }

    for title, ligne in cas.items():
        res = calling(ligne, features)
        print(f"\n{'=' * 58}\n{title}\n{'=' * 58}")
        print(f"RUL réel      : {ligne.rul:.0f} vols   ← la vérité terrain")
        print(f"RUL prédit    : {res['rul_estime']} vols")
        print(f"Alerte        : {'OUI' if res['alerte'] else 'non'} "
              f"(seuil {res['seuil']})")
        print(f"Modèle        : version {res['modele_version']}")
        if res["causes"]:
            print("Causes principales :")
            for c in res["causes"]:
                sens = "raccourcit" if c["contribution"] < 0 else "prolonge"
                print(f"   {c['capteur']:<24}{c['contribution']:>8.2f}v  ({sens})")


if __name__ == "__main__":
    main()