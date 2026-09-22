# Raccourcis du projet. Les options de mlflow ne sont pas optionnelles :
# sans --backend-store-uri, MLflow cherche ./mlruns (inexistant ici) et
# affiche une interface vide au lieu de nos runs.

PY := .venv/bin/python
MLFLOW := .venv/bin/mlflow

# 5001 et non 5000 : le Récepteur AirPlay de macOS occupe déjà 5000.
MLFLOW_PORT ?= 5001
export MLFLOW_TRACKING_URI := http://127.0.0.1:$(MLFLOW_PORT)

.PHONY: mlflow train api port docker-build docker-run lint test

## Serveur de suivi + registre. À laisser tourner dans son propre terminal.
mlflow:
	$(MLFLOW) server \
	  --host 0.0.0.0 --port $(MLFLOW_PORT) \
	  --backend-store-uri sqlite:///mlflow.db \
	  --artifacts-destination ./mlartifacts \
	  --serve-artifacts \
	  --allowed-hosts "localhost,127.0.0.1,host.docker.internal,localhost:$(MLFLOW_PORT),127.0.0.1:$(MLFLOW_PORT),host.docker.internal:$(MLFLOW_PORT)"

## Un run complet : entraînement, métriques, artefacts, version au registre.
train:
	$(PY) -m src.tracking.experiment

## L'API de prédiction. Elle lit le registre, donc `make mlflow` d'abord.
api:
	$(PY) -m uvicorn src.api.main:app --reload --port 8000

## Qui occupe le port MLflow ? Utile quand le serveur refuse de démarrer.
port:
	@lsof -nP -iTCP:$(MLFLOW_PORT) -sTCP:LISTEN || echo "$(MLFLOW_PORT) libre"

## Fabrique l'image de l'API.
docker-build:
	docker build -t safran-api:1.0 .

## Lance l'API en conteneur. host-gateway résout l'hôte en IPv4 :
## sans lui, la connexion part en IPv6 et échoue (Errno 101).
docker-run:
	docker run --rm -p 8000:8000 \
	  --add-host=host.docker.internal:host-gateway \
	  -e MLFLOW_TRACKING_URI=http://host.docker.internal:$(MLFLOW_PORT) \
	  --name rul-api safran-api:1.0

## Qualité de code. Avant les tests : un import mort se voit.
lint:
	.venv/bin/ruff check src tests

## Suite de tests hors-ligne — ne nécessite ni MinIO ni MLflow.
test:
	$(PY) -m pytest -q