# Dépannage — `No such artifact: ''` au démarrage du conteneur

**Date** : 21 septembre 2026 · **Statut** : résolu

Compte rendu d'un incident rencontré lors de la conteneurisation de
l'API. Le conteneur refusait de démarrer alors que la même API
fonctionnait en local. Deux causes distinctes se sont superposées ;
c'est ce qui a rendu le diagnostic trompeur.

## Symptôme

```
make docker-run
...
mlflow.exceptions.MlflowException: No such artifact: ''
ERROR:    Application startup failed. Exiting.
```

La trace passe par `local_artifact_repo.py` — c'est l'indice décisif,
et il a été lu trop tard : MLflow cherchait le modèle sur un **chemin
de fichier**, pas par HTTP.

## Fausse piste : le port 5000

Le diagnostic a commencé par « MLflow tourne encore sur le port 5000 et
je n'arrive pas à le tuer ». Vérification faite :

```bash
lsof -nP -iTCP:5000 -sTCP:LISTEN
# ControlCe  12432  frozone  ...  TCP *:5000 (LISTEN)
```

Ce n'était pas MLflow. Sur macOS, le **récepteur AirPlay**
(`ControlCenter`) occupe les ports 5000 et 7000 depuis Monterey, et
répond `403` à toute requête. D'où l'illusion d'un serveur fantôme.

Il ne faut pas tuer ce processus : `launchd` le relance aussitôt et la
barre de menus est perturbée entre-temps. Le projet écoute donc sur
**5001**, décision déjà inscrite dans le `Makefile`.

Le réflexe qui tranche en une commande :

```bash
make port
```

Si la colonne `COMMAND` affiche `Python`, c'est le serveur MLflow et un
`kill <PID>` suffit. Si elle affiche `ControlCe`, c'est le système et
il n'y a rien à faire.

## Cause réelle

Le serveur MLflow était lancé avec :

```
--default-artifact-root ./mlartifacts
```

Cette option indique au serveur : « les artefacts sont à cet
emplacement sur le disque ». MLflow convertit le chemin en absolu et
l'enregistre en base. Le serveur distribue alors des **chemins de
fichiers**, jamais des URL.

Enchaînement au démarrage du conteneur :

1. L'API se connecte à `http://host.docker.internal:5001` — **cette
   partie fonctionnait**, ce qui a brouillé les pistes.
2. Elle demande où trouver `models:/rul-xgboost@production`.
3. Le serveur répond
   `/Users/frozone/.../mlartifacts/1/models/m-9978.../artifacts`.
4. Voyant un chemin local, MLflow bascule sur `local_artifact_repo` et
   n'émet aucune requête HTTP.
5. Ce chemin n'existe pas dans le conteneur → `No such artifact: ''`.

C'est pourquoi `make api` fonctionnait et `make docker-run` échouait :
sur l'hôte le chemin existe, dans le conteneur non. Un conteneur ne
partage pas le système de fichiers de la machine.

## Le piège caché : `artifact_location` est figé

Corriger le `Makefile` ne suffisait pas. L'emplacement des artefacts
est **enregistré à la création de l'expérience** et les nouveaux runs
en héritent — ils n'utilisent pas le réglage courant du serveur.

```sql
SELECT experiment_id, name, artifact_location FROM experiments;
-- 0 | Default    | mlflow-artifacts:/0
-- 1 | rul-moteur | /Users/frozone/.../mlartifacts/1   ← figé
```

Réentraîner dans `rul-moteur` aurait donc reproduit le bug à
l'identique, malgré un serveur correctement configuré. MLflow ne
permet pas de modifier ce champ par son API.

Au total, 14 valeurs réparties sur 6 colonnes contenaient le chemin
absolu : `experiments.artifact_location`, `runs.artifact_uri`,
`model_versions.storage_location`, `logged_models.artifact_location`,
`logged_model_tags.tag_value` et `tags.value`.

## Corrections appliquées

### 1. Le serveur sert les artefacts en HTTP

Dans le `Makefile`, `--default-artifact-root` est remplacé par
`--artifacts-destination`, qui conserve le même dossier de stockage
mais fait distribuer des URI `mlflow-artifacts:/…` que le client
télécharge via le serveur :

```make
mlflow:
	$(MLFLOW) server \
	  --host 0.0.0.0 --port $(MLFLOW_PORT) \
	  --backend-store-uri sqlite:///mlflow.db \
	  --artifacts-destination ./mlartifacts \
	  --serve-artifacts \
	  --allowed-hosts "localhost,127.0.0.1,host.docker.internal,…"
```

`--host 0.0.0.0` et non `127.0.0.1` : le conteneur joint l'hôte par
`host.docker.internal`, et `--allowed-hosts` doit l'autoriser
explicitement, sinon MLflow rejette l'en-tête `Host`.

### 2. Une nouvelle expérience

`EXPERIENCE` est passée à `rul-moteur-v2` dans
[`src/tracking/experiment.py`](../src/tracking/experiment.py). Créée
sous le serveur corrigé, elle reçoit `mlflow-artifacts:/2`, et la
version 4 du modèle hérite d'une URI servie en HTTP :

```
mlflow-artifacts:/2/models/m-3924cab766134192a6e91170a0862c9c/artifacts
```

L'alternative — réécrire les 14 valeurs en base — aurait préservé
l'historique dans une seule expérience et réparé les versions 1 à 3.
Les fichiers étant déjà au bon endroit sur le disque, il ne s'agissait
que d'une substitution de chaîne. Elle a été écartée pour ne pas
toucher directement à la base de suivi.

### 3. L'alias déplacé

L'API charge le modèle par son alias (ADR 0003). L'alias `production`
pointait encore sur la version 3, celle au chemin absolu : sans ce
dernier geste, le conteneur aurait échoué exactement de la même façon.

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5001 .venv/bin/python -c \
  "from mlflow import MlflowClient; \
   MlflowClient().set_registered_model_alias('rul-xgboost','production',4)"
```

## Vérification

Le démarrage du conteneur affiche désormais le téléchargement des
artefacts — la preuve que le transfert passe bien par HTTP :

```
Downloading artifacts: 100%|██████████| 5/5
Modèle rul-xgboost v4 chargé — 87 features
INFO:     Application startup complete.
```

```bash
curl http://127.0.0.1:8000/health   # {"statut":"ok","modele_charge":true}
curl http://127.0.0.1:8000/model    # version 4, alias production, seuil 10
```

Trois requêtes en base pour contrôler l'état à tout moment :

```bash
sqlite3 mlflow.db "SELECT experiment_id, name, artifact_location FROM experiments;"
sqlite3 mlflow.db "SELECT version, storage_location FROM model_versions ORDER BY version DESC;"
sqlite3 mlflow.db "SELECT alias, version FROM registered_model_aliases;"
```

Toute valeur commençant par `/Users/` signale un artefact qui ne sera
pas lisible depuis un conteneur.

## Ce qui reste

**L'expérience `rul-moteur` (id 1) et les versions 1 à 3** conservent
leurs chemins absolus. Elles ne gênent plus rien puisque l'alias pointe
ailleurs, mais resteront inutilisables depuis un conteneur. À archiver
si l'on veut un registre propre, ou à conserver comme trace de
l'historique.

**`.PHONY`** ne liste pas `docker-build` ni `docker-run`. Sans
conséquence aujourd'hui, mais si un fichier portant l'un de ces noms
apparaissait à la racine, `make` considérerait la cible à jour.

## Leçon

Une erreur d'artefact dans un conteneur n'est presque jamais un
problème de réseau. Si le client a reçu une réponse du serveur, la
connexion fonctionne : c'est le **contenu** de cette réponse — un
chemin local au lieu d'une URL — qu'il faut regarder. Et le
comportement d'un serveur MLflow ne suffit pas à le décrire : une
partie de la configuration est gravée en base au moment où
l'expérience est créée.
