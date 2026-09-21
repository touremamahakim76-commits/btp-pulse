# Module 14 — image de l'API FastAPI
# Contexte de build = la RACINE du dépôt (voir docker/docker-compose.yml,
# build.context: ..), pour pouvoir embarquer les modules "database" et
# "rag" dont l'API a besoin (sys.path relatif, cf. api/main.py et api/db.py).
FROM python:3.11-slim

WORKDIR /opt/btp-pulse

COPY api/requirements.txt api/requirements.txt
COPY rag/requirements.txt rag/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt -r rag/requirements.txt

COPY api ./api
COPY database ./database
COPY rag ./rag

WORKDIR /opt/btp-pulse/api
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
