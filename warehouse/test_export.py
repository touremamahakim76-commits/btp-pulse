"""Tests du Module 5 — pytest warehouse/ -v

Aucun accès réseau/cloud requis : on teste la cohérence du schéma et
le typage des données (fonctions pures), pas les appels BigQuery.
"""
from __future__ import annotations

import pandas as pd

import schema_bq
from export import NOM_TABLE_CLI, typer_dataframe


def test_schema_coherent_pour_chaque_table():
    for nom_table, info in schema_bq.TABLES.items():
        noms_schema = [c.name for c in info["schema"]]
        assert info["colonnes_postgres"] == noms_schema, (
            f"{nom_table} : colonnes_postgres et schema doivent être "
            "dans le même ordre avec les mêmes noms"
        )
        if info["partition_field"]:
            assert info["partition_field"] in noms_schema


def test_ordre_tables_complet():
    assert set(schema_bq.ORDRE_TABLES) == set(schema_bq.TABLES)
    assert schema_bq.ORDRE_TABLES.index("materiaux") < schema_bq.ORDRE_TABLES.index("materiaux_prix")


def test_alias_cli_couvrent_toutes_les_tables():
    assert set(NOM_TABLE_CLI.values()) == set(schema_bq.TABLES)


def test_typer_dataframe_dates_et_timestamps():
    df = pd.DataFrame({
        "date_releve": ["2026-01-05", "2026-01-12"],
        "code_materiau": ["ACIER_T", "ACIER_T"],
        "prix": [900.0, 910.0],
        "indice_base100": [100.0, 101.1],
        "source": ["eurostat", "eurostat"],
        "horodatage_ingestion": ["2026-01-05T10:00:00", "2026-01-12T10:00:00"],
    })
    out = typer_dataframe("materiaux_prix", df)
    assert all(hasattr(v, "isoformat") for v in out["date_releve"])
    assert pd.api.types.is_datetime64_any_dtype(out["horodatage_ingestion"])
    assert str(out["horodatage_ingestion"].dt.tz) == "UTC"
