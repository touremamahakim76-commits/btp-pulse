"""DAG quotidien — Module 13 : tests statistiques + alertes Telegram.

Planning : tous les jours à 8h (après les DAGs de scraping/chargement).
Enchaîne :
  1. tests_statistiques -> réutilise le Module 6 (t-test sur les prix)
  2. alerte_telegram     -> réutilise le Module 13 (variations
                            significatives + nouveaux AO pertinents)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from _common import notifier_echec


def tester_variations_prix(**_context) -> None:
    import psycopg2
    import db_config
    from tests_statistiques import executer_tous

    conn = psycopg2.connect(db_config.dsn())
    try:
        resultats = executer_tous(conn)
        print(f"{len(resultats)} matériaux testés.")
    finally:
        conn.close()


def envoyer_alertes(**_context) -> None:
    import psycopg2
    import db_config
    from telegram_alerte import executer

    conn = psycopg2.connect(db_config.dsn())
    try:
        executer(conn, depuis_heures=26, score_min=6)
    finally:
        conn.close()


default_args = {
    "owner": "btp-pulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notifier_echec,
}

with DAG(
    dag_id="btp_pulse_alertes",
    description="Tests statistiques quotidiens + alertes Telegram (Modules 6 et 13)",
    default_args=default_args,
    schedule="0 8 * * *",           # tous les jours à 8h, après les scrapers
    start_date=datetime(2026, 1, 5),
    catchup=False,
    max_active_runs=1,
    tags=["btp-pulse", "alertes", "quotidien"],
) as dag:

    t_tests = PythonOperator(task_id="tests_statistiques", python_callable=tester_variations_prix)
    t_alerte = PythonOperator(task_id="alerte_telegram", python_callable=envoyer_alertes)

    t_tests >> t_alerte
