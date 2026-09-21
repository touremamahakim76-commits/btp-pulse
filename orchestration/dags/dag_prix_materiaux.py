"""DAG hebdomadaire — Module 4 : prix des matériaux.

Planning : tous les lundis à 6h00.
Enchaîne :
  1. scraper_prix  -> réutilise le Module 1 (Eurostat, repli démo)
  2. charger_prix  -> réutilise le Module 3 (nettoyage + upsert PostgreSQL)

Le code des Modules 1 et 3 n'est pas dupliqué : on l'importe et on
appelle directement ses fonctions `main()`. Airflow n'est qu'un chef
d'orchestre qui planifie, journalise et relance en cas d'échec.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from _common import notifier_echec  # ajoute aussi ingestion/ et database/ au sys.path


def scraper_prix(**_context) -> None:
    import scraper_prix_materiaux
    code = scraper_prix_materiaux.main(["--source", "auto"])
    if code != 0:
        raise RuntimeError(f"scraper_prix_materiaux a échoué (code {code})")


def charger_prix(**_context) -> None:
    import load as db_load
    code = db_load.main(["--table", "prix"])
    if code != 0:
        raise RuntimeError(f"load.py --table prix a échoué (code {code})")


default_args = {
    "owner": "btp-pulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notifier_echec,
}

with DAG(
    dag_id="btp_pulse_prix_materiaux",
    description="Scraping hebdomadaire des prix matériaux (Eurostat) + chargement PostgreSQL",
    default_args=default_args,
    schedule="0 6 * * 1",           # tous les lundis à 6h
    start_date=datetime(2026, 1, 5),
    catchup=False,
    max_active_runs=1,
    tags=["btp-pulse", "prix", "hebdomadaire"],
) as dag:

    t_scraper = PythonOperator(task_id="scraper_prix", python_callable=scraper_prix)
    t_charger = PythonOperator(task_id="charger_prix", python_callable=charger_prix)

    t_scraper >> t_charger
