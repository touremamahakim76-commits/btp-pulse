"""Module 5 — Export PostgreSQL -> BigQuery (BTP Pulse).

Réplique les tables nettoyées de la base PostgreSQL (Module 3) vers un
data warehouse BigQuery : la brique « entrepôt cloud » de la stack.

Stratégie : réplication complète (WRITE_TRUNCATE) table par table. Aux
volumes du projet (quelques milliers de lignes), un rechargement complet
est largement suffisant, plus simple et plus sûr qu'un MERGE incrémental.
À plus grande échelle, on passerait à un chargement incrémental (MERGE
sur la clé + `horodatage_ingestion`) — présent sur toutes les tables,
la base est prête pour cette évolution.

Prérequis :
  - un projet Google Cloud avec l'API BigQuery activée (le palier
    gratuit suffit très largement : 1 To de requêtes/mois, 10 Go de
    stockage) ;
  - des identifiants : soit `gcloud auth application-default login`,
    soit une clé de compte de service (GOOGLE_APPLICATION_CREDENTIALS) ;
  - la base PostgreSQL du Module 3 démarrée et chargée.

Usage :
  python export.py --init            # crée le dataset + les tables (si absents)
  python export.py                   # exporte toutes les tables
  python export.py --table prix
  python export.py --stats           # compte les lignes côté BigQuery
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import psycopg2

import bq_config
import schema_bq

# --- accès à la config de connexion Postgres du Module 3 ------------------
_DATABASE_DIR = Path(__file__).resolve().parent.parent / "database"
sys.path.insert(0, str(_DATABASE_DIR))
import db_config  # noqa: E402

NOM_TABLE_CLI = {  # alias pratiques en ligne de commande -> nom réel
    "materiaux": "materiaux",
    "prix": "materiaux_prix",
    "ao": "appels_offres",
    "devis": "devis_historique",
}


# =========================================================================
# Lecture PostgreSQL
# =========================================================================
def typer_dataframe(nom_table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Type explicitement les colonnes date / timestamp selon le schéma
    BigQuery, pour que le job de chargement ne devine pas (fonction pure,
    testable sans base ni cloud)."""
    df = df.copy()
    for champ in schema_bq.TABLES[nom_table]["schema"]:
        if champ.name not in df.columns:
            continue
        if champ.field_type == "DATE":
            df[champ.name] = pd.to_datetime(df[champ.name]).dt.date
        elif champ.field_type == "TIMESTAMP":
            df[champ.name] = pd.to_datetime(df[champ.name], utc=True)
    return df


def lire_table_postgres(nom_table: str) -> pd.DataFrame:
    colonnes = schema_bq.TABLES[nom_table]["colonnes_postgres"]
    requete = f"SELECT {', '.join(colonnes)} FROM {nom_table}"
    with psycopg2.connect(db_config.dsn()) as conn:
        df = pd.read_sql(requete, conn)
    return typer_dataframe(nom_table, df)


# =========================================================================
# BigQuery
# =========================================================================
def client_bigquery():
    from google.cloud import bigquery
    bq_config.verifier_configuration()
    return bigquery.Client(project=bq_config.BQ_PROJECT)


def assurer_dataset(client) -> None:
    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    dataset_id = f"{client.project}.{bq_config.BQ_DATASET}"
    try:
        client.get_dataset(dataset_id)
        print(f"  dataset {dataset_id} déjà présent")
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = bq_config.BQ_LOCATION
        client.create_dataset(dataset)
        print(f"  dataset {dataset_id} créé ({bq_config.BQ_LOCATION})")


def exporter_table(client, nom_table: str) -> int:
    from google.cloud import bigquery

    info = schema_bq.TABLES[nom_table]
    df = lire_table_postgres(nom_table)
    table_id = f"{client.project}.{bq_config.BQ_DATASET}.{nom_table}"

    job_config = bigquery.LoadJobConfig(
        schema=info["schema"],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    if info["partition_field"]:
        job_config.time_partitioning = bigquery.TimePartitioning(
            field=info["partition_field"]
        )

    print(f"→ {nom_table} : {len(df)} lignes depuis PostgreSQL")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # attend la fin du job, lève une exception si échec
    print(f"  chargées dans {table_id}")
    return len(df)


def afficher_stats(client) -> None:
    print("\n--- État du data warehouse BigQuery ---")
    for nom_table in schema_bq.ORDRE_TABLES:
        table_id = f"{client.project}.{bq_config.BQ_DATASET}.{nom_table}"
        try:
            table = client.get_table(table_id)
            print(f"  {nom_table:20} {table.num_rows:>7} lignes"
                  f"  (maj {table.modified:%Y-%m-%d %H:%M})")
        except Exception:
            print(f"  {nom_table:20} (absente — lance --init puis l'export)")


# =========================================================================
# CLI
# =========================================================================
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export PostgreSQL -> BigQuery — BTP Pulse")
    p.add_argument("--init", action="store_true", help="crée le dataset s'il n'existe pas")
    p.add_argument("--table", choices=["all", *NOM_TABLE_CLI], default="all")
    p.add_argument("--stats", action="store_true")
    args = p.parse_args(argv)

    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        client = client_bigquery()
    except Exception as exc:
        print(f"ERREUR : connexion à BigQuery impossible.\n{exc}\n"
              "→ vérifie warehouse/.env (BQ_PROJECT) et ton authentification "
              "(gcloud auth application-default login).")
        return 1

    try:
        if args.stats:
            afficher_stats(client)
            return 0

        if args.init:
            print("→ Initialisation du dataset")
            assurer_dataset(client)

        tables = (
            schema_bq.ORDRE_TABLES if args.table == "all"
            else [NOM_TABLE_CLI[args.table]]
        )
        total = 0
        for nom_table in tables:
            total += exporter_table(client, nom_table)

        print(f"\n{total} lignes répliquées vers BigQuery "
              f"({bq_config.BQ_PROJECT}.{bq_config.BQ_DATASET})")
        afficher_stats(client)
    except psycopg2.OperationalError as exc:
        print(f"ERREUR : connexion à PostgreSQL impossible.\n{exc}\n"
              "→ docker compose -f database/docker-compose.yml up -d")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
