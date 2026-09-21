# Module 4 — image Airflow pour BTP Pulse
# Ajoute au-dessus de l'image officielle les libs dont nos scripts
# d'ingestion et de chargement ont besoin (Modules 1, 2, 3).
FROM apache/airflow:2.10.5-python3.11

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
