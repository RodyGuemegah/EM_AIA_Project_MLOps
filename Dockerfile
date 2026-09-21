# Image officielle Python, variante "slim" : Debian minimal, ~120 Mo
# contre ~1 Go pour l'image complète. Version FIGÉE : "3.11" et non
# "3", pour que l'image soit reproductible dans six mois.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# `brew install libomp`
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt .
RUN pip install --upgrade pip && pip install -r requirements-api.txt

COPY src/ ./src/

# Jamais root. Si le service est compromis, l'attaquant hérite des
# droits du processus.
RUN useradd --create-home --uid 1000 apiuser
USER apiuser

EXPOSE 8000

# Docker interroge la sonde et marque le conteneur "unhealthy" s'il ne
# répond plus. start-period couvre le chargement du modèle (ADR 0002).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# 0.0.0.0 et non 127.0.0.1 : sinon le serveur n'écoute que l'intérieur
# du conteneur et le port publié ne mène nulle part.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]