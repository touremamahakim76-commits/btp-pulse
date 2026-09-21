"""Schéma BigQuery — Module 5.

Miroir du schéma PostgreSQL (database/schema.sql), en types BigQuery.
Pour chaque table : la liste des colonnes à lire côté Postgres (dans
l'ordre, sans la clé technique `id` de `materiaux_prix`), le schéma
BigQuery correspondant, et — quand c'est pertinent — le champ de
partitionnement par date (bonne pratique pour limiter le volume/coût
des requêtes à l'échelle, même si notre volume actuel est minuscule).
"""
from __future__ import annotations

from google.cloud import bigquery

TABLES: dict[str, dict] = {
    "materiaux": {
        "colonnes_postgres": ["code", "libelle", "unite", "prix_ref"],
        "schema": [
            bigquery.SchemaField("code", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("libelle", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("unite", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("prix_ref", "NUMERIC"),
        ],
        "partition_field": None,
    },
    "materiaux_prix": {
        "colonnes_postgres": [
            "date_releve", "code_materiau", "prix", "indice_base100",
            "source", "horodatage_ingestion",
        ],
        "schema": [
            bigquery.SchemaField("date_releve", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("code_materiau", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("prix", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("indice_base100", "NUMERIC"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("horodatage_ingestion", "TIMESTAMP", mode="REQUIRED"),
        ],
        "partition_field": "date_releve",
    },
    "appels_offres": {
        "colonnes_postgres": [
            "id_source", "objet", "acheteur", "departements", "date_parution",
            "date_limite_reponse", "type_marche", "categorie",
            "mots_cles_trouves", "score_pertinence", "url_avis", "source",
            "horodatage_ingestion",
        ],
        "schema": [
            bigquery.SchemaField("id_source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("objet", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("acheteur", "STRING"),
            bigquery.SchemaField("departements", "STRING"),
            bigquery.SchemaField("date_parution", "DATE"),
            bigquery.SchemaField("date_limite_reponse", "DATE"),
            bigquery.SchemaField("type_marche", "STRING"),
            bigquery.SchemaField("categorie", "STRING"),
            bigquery.SchemaField("mots_cles_trouves", "STRING"),
            bigquery.SchemaField("score_pertinence", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("url_avis", "STRING"),
            bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("horodatage_ingestion", "TIMESTAMP", mode="REQUIRED"),
        ],
        "partition_field": "date_parution",
    },
    "devis_historique": {
        "colonnes_postgres": [
            "id_devis", "date_devis", "client", "type_chantier", "departement",
            "surface_m2", "montant_ht", "statut", "marge_estimee_pct",
            "principaux_materiaux", "commentaire",
        ],
        "schema": [
            bigquery.SchemaField("id_devis", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("date_devis", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("client", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("type_chantier", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("departement", "STRING"),
            bigquery.SchemaField("surface_m2", "NUMERIC"),
            bigquery.SchemaField("montant_ht", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("statut", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("marge_estimee_pct", "NUMERIC"),
            bigquery.SchemaField("principaux_materiaux", "STRING"),
            bigquery.SchemaField("commentaire", "STRING"),
        ],
        "partition_field": "date_devis",
    },
}

# Ordre d'export : `materiaux` avant `materiaux_prix` par cohérence
# fonctionnelle (même si BigQuery n'impose pas de FK).
ORDRE_TABLES = ["materiaux", "materiaux_prix", "appels_offres", "devis_historique"]
