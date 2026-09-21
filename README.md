# safran-mlops — durée de vie résiduelle des moteurs

API de prédiction de la durée de vie résiduelle (RUL) de moteurs
d'avion, servie depuis un registre de modèles MLflow.

Elle réunit quatre briques en une seule réponse : le modèle (XGBoost),
le registre (MLflow), la décision (seuil par matrice de coûts) et
l'explication (SHAP).

## Prérequis

| Élément | Détail |
|---|---|
| Python | 3.11, environnement virtuel dans `.venv/` |
| Lac de données | MinIO, conteneur `safran-minio`, ports 9000/9001 |
| Fichier `.env` | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` |
| Docker | pour construire et lancer l'image de l'API |

Les données silver viennent du projet voisin **safran-data-platform** :
le conteneur MinIO monte son dossier `data/minio`. Sans ce conteneur,
`make train` échoue dès la lecture du dataset.

## Démarrage depuis un clone neuf

`mlflow.db` et `mlartifacts/` sont volontairement exclus de Git. Un
dépôt fraîchement cloné n'a donc **ni registre ni modèle** : il faut
entraîner une première fois avant de pouvoir servir quoi que ce soit.
L'API ne démarre pas sans modèle en registre — c'est un choix assumé
(ADR 0003), pas un défaut.

### 1. Environnement

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Créer un fichier `.env` à la racine :

```
MINIO_ROOT_USER=<identifiant>
MINIO_ROOT_PASSWORD=<mot de passe>
```

Vérifier que le lac répond :

```bash
docker ps | grep safran-minio
```

### 2. Serveur MLflow — à laisser tourner

Dans un terminal dédié, qui ne rendra pas la main :

```bash
make mlflow
```

Interface : <http://127.0.0.1:5001>

Le port est **5001 et non 5000** : sur macOS, le récepteur AirPlay
occupe déjà 5000 et répond `403`, ce qui donne l'illusion qu'un
serveur tourne.

### 3. Premier entraînement

Dans un second terminal :

```bash
make train
```

Le run crée l'expérience `rul-moteur-v2`, enregistre métriques,
figures SHAP et table des seuils, puis dépose une **version** du modèle
`rul-xgboost` au registre.

### 4. Poser l'alias `production` — étape manuelle obligatoire

`experiment.py` enregistre une version, il ne la promeut jamais. C'est
une décision humaine et tracée (ADR 0004). Tant que l'alias n'est pas
posé, l'API refusera de démarrer.

Par l'interface : onglet *Models* → `rul-xgboost` → la version voulue →
ajouter l'alias `production`.

Ou en ligne de commande, en ajustant le numéro de version :

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5001 .venv/bin/python -c \
  "from mlflow import MlflowClient; \
   MlflowClient().set_registered_model_alias('rul-xgboost','production',1)"
```

### 5. Lancer l'API

En local :

```bash
make api          # http://127.0.0.1:8000
```

Ou en conteneur :

```bash
make docker-build
make docker-run
```

Vérification :

```bash
curl http://127.0.0.1:8000/health    # {"statut":"ok","modele_charge":true}
curl http://127.0.0.1:8000/model     # version servie, alias, seuil
```

## Commandes

| Commande | Rôle |
|---|---|
| `make mlflow` | Serveur de suivi + registre, port 5001 |
| `make train` | Un run complet : métriques, artefacts, version au registre |
| `make api` | API locale sur le port 8000, rechargement à chaud |
| `make port` | Qui occupe le port MLflow — utile en cas de conflit |
| `make docker-build` | Construit l'image `safran-api:1.0` |
| `make docker-run` | Lance l'API en conteneur |

## Après chaque réentraînement

1. Comparer dans MLflow la RMSE **et** le coût (`cout_optimal_usd`) avec
   la version en place.
2. Si la nouvelle version est retenue, y déplacer l'alias `production`.
3. Redémarrer l'API : le modèle est chargé une fois au démarrage, pas à
   chaque requête (ADR 0002).
4. Recalculer `SEUIL_RETENU` dans `src/config.py` si le seuil optimal du
   nouveau run diffère.

Oublier l'étape 2 fait servir l'ancien modèle **sans aucune erreur
visible** : l'API démarre normalement. Le champ `version` de `/model`
est le seul moyen de s'en apercevoir.

## Décisions d'architecture

Les ADR sont dans [docs/adr/](docs/adr/) :

| ADR | Sujet |
|---|---|
| 0001 | Le seuil d'alerte est calculé par matrice de coûts |
| 0002 | Le modèle est chargé au démarrage de l'API, pas par requête |
| 0003 | L'API résout le modèle par alias, jamais par numéro de version |
| 0004 | L'entraînement est automatisé, la promotion ne l'est pas |

## Dépannage

Les pièges déjà rencontrés et résolus sont documentés dans
[docs/depannage-artefacts-docker.md](docs/depannage-artefacts-docker.md) :
port 5000 occupé par AirPlay, et surtout `No such artifact: ''` au
démarrage du conteneur.
