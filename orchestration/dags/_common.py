"""Utilitaires partagés entre les DAGs BTP Pulse — Module 4.

Ajoute les dossiers des Modules 1/2/3 au chemin d'import Python (ils ne
sont pas des paquets pip, juste du code monté dans le conteneur) et
fournit un callback d'échec commun.
"""
from __future__ import annotations

import logging
import sys

for _dossier in ("/opt/airflow/ingestion", "/opt/airflow/database",
                "/opt/airflow/analytics", "/opt/airflow/bot"):
    if _dossier not in sys.path:
        sys.path.insert(0, _dossier)

log = logging.getLogger("btp_pulse.airflow")


def notifier_echec(context: dict) -> None:
    """Callback appelé par Airflow quand une tâche échoue définitivement
    (après épuisement des retries) : log clair + alerte Telegram
    (Module 13 ; dry-run silencieux si le bot n'est pas configuré)."""
    ti = context["task_instance"]
    message = (
        f"ÉCHEC — dag={ti.dag_id} tâche={ti.task_id} "
        f"run={context.get('run_id')} : {context.get('exception')}"
    )
    log.error(message)
    try:
        from telegram_alerte import envoyer_message
        envoyer_message(f"🚨 *Échec pipeline BTP Pulse*\n{message}")
    except Exception as exc:  # ne jamais faire échouer le callback lui-même
        log.warning("Alerte Telegram non envoyée : %s", exc)
