"""DAG quotidien — Module 4 : appels d'offres publics.

Planning : tous les jours à 7h00.
Enchaîne :
  1. scraper_ao  -> réutilise le Module 2 (BOAMP, repli démo)
  2. charger_ao  -> réutilise le Module 3 (nettoyage + upsert PostgreSQL)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from _common import notifier_echec


def scraper_ao(**_context) -> None:
    import scraper_appels_offres
    code = scraper_appels_offres.main(["--source", "auto", "--jours", "7"])
    if code != 0:
        raise RuntimeError(f"scraper_appels_offres a échoué (code {code})")


def charger_ao(**_context) -> None:
    import load as db_load
    code = db_load.main(["--table", "ao"])
    if code != 0:
        raise RuntimeError(f"load.py --table ao a échoué (code {code})")


default_args = {
    "owner": "btp-pulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notifier_echec,
}

with DAG(
    dag_id="btp_pulse_appels_offres",
    description="Scraping quotidien des appels d'offres BTP (BOAMP) + chargement PostgreSQL",
    default_args=default_args,
    schedule="0 7 * * *",           # tous les jours à 7h
    start_date=datetime(2026, 1, 5),
    catchup=False,
    max_active_runs=1,
    tags=["btp-pulse", "appels-offres", "quotidien"],
) as dag:

    t_scraper = PythonOperator(task_id="scraper_ao", python_callable=scraper_ao)
    t_charger = PythonOperator(task_id="charger_ao", python_callable=charger_ao)

    t_scraper >> t_charger
