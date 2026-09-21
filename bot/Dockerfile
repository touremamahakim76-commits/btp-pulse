# Module 14 — image du bot d'alerte Telegram
# Contexte de build = la racine du dépôt (a besoin de "database" pour
# db_config.py). Ce n'est pas un service longue durée : on le lance
# ponctuellement (`docker compose run bot`) ou via Airflow (dag_alertes.py).
FROM python:3.11-slim

WORKDIR /opt/btp-pulse

COPY bot/requirements.txt bot/requirements.txt
RUN pip install --no-cache-dir -r bot/requirements.txt

COPY bot ./bot
COPY database ./database

WORKDIR /opt/btp-pulse/bot
CMD ["python", "telegram_alerte.py"]
