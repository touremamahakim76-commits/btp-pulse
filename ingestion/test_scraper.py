"""Tests du Module 1 — exécuter avec :  pytest ingestion/ -v

Ces tests ne dépendent d'aucun réseau : ils portent sur le générateur
de démo et sur la logique de fusion/dédoublonnage.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sources import COLONNES, generer_demo, _parse_jsonstat
from config import MATERIAUX


def test_demo_volume_et_schema():
    releves = generer_demo(semaines=52)
    assert len(releves) == len(MATERIAUX) * 52
    assert set(releves[0].keys()) == set(COLONNES)


def test_demo_prix_positifs_et_dates_hebdo():
    releves = generer_demo(semaines=30)
    assert all(r["prix"] > 0 for r in releves)
    dates_beton = sorted({r["date_releve"] for r in releves
                          if r["code_materiau"] == "BETON_M3"})
    ecarts = [
        (pd.Timestamp(b) - pd.Timestamp(a)).days
        for a, b in zip(dates_beton, dates_beton[1:])
    ]
    assert set(ecarts) == {7}  # relevés strictement hebdomadaires


def test_demo_reproductible():
    assert generer_demo(semaines=20, seed=1) == generer_demo(semaines=20, seed=1)
    assert generer_demo(semaines=20, seed=1) != generer_demo(semaines=20, seed=2)


def test_parse_jsonstat_eurostat():
    # Réponse JSON-stat Eurostat réduite : 3 mois, une valeur manquante.
    payload = {
        "value": {"0": 120.0, "2": 125.5},  # position 1 absente
        "dimension": {"time": {"category": {"index": {
            "2024-01": 0, "2024-02": 1, "2024-03": 2}}}},
    }
    points = _parse_jsonstat(payload)
    assert [p[0].isoformat() for p in points] == ["2024-01-01", "2024-03-01"]
    assert [p[1] for p in points] == [120.0, 125.5]


def test_dedoublonnage(tmp_path, monkeypatch):
    import scraper_prix_materiaux as s

    csv_test = tmp_path / "materiaux_prix.csv"
    monkeypatch.setattr(s, "CSV_PRINCIPAL", csv_test)
    monkeypatch.setattr(s, "JSON_PRINCIPAL", tmp_path / "materiaux_prix.json")
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)

    base = generer_demo(semaines=10)
    s.sauvegarder(base)
    df = s.sauvegarder(base)  # ré-insertion des mêmes relevés

    assert not df.duplicated(subset=["date_releve", "code_materiau"]).any()
    assert len(df) == len(base)
