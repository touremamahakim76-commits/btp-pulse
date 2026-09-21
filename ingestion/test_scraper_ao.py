"""Tests du Module 2 — pytest ingestion/ -v  (aucun réseau requis)."""
from __future__ import annotations

import pandas as pd

from sources_ao import (
    COLONNES_AO,
    analyser_pertinence,
    generer_demo_ao,
    _normaliser_record_boamp,
)


def test_analyser_pertinence():
    mots, score = analyser_pertinence(
        "Travaux de maçonnerie et charpente pour la rénovation d'une école",
        categorie="Bâtiment",
    )
    assert "maçonnerie" in mots and "charpente" in mots and "rénovation" in mots
    assert score >= 3

    mots, score = analyser_pertinence("Fourniture de fournitures de bureau", "Fournitures")
    assert score == 0


def test_pertinence_insensible_aux_accents():
    mots, _ = analyser_pertinence("TRAVAUX DE MACONNERIE ET DE COUVERTURE")
    assert "maçonnerie" in mots and "couverture" in mots


def test_demo_ao_schema_et_volume():
    annonces = generer_demo_ao(jours=30)
    assert len(annonces) == 10
    assert set(annonces[0]) == set(COLONNES_AO)
    assert all(a["date_parution"] <= a["date_limite_reponse"] for a in annonces)


def test_normalisation_record_boamp():
    rec = {
        "idweb": "26-12345",
        "objet": "  Construction d'un gymnase — lot gros œuvre  ",
        "nomacheteur": "Commune de Test",
        "code_departement": ["69", "01"],
        "dateparution": "2026-09-01",
        "datelimitereponse": "2026-10-15T12:00:00+00:00",
        "type_marche": ["TRAVAUX"],
        "descripteur_libelle": ["Bâtiment"],
        "url_avis": "https://www.boamp.fr/x",
    }
    out = _normaliser_record_boamp(rec, "2026-09-10T00:00:00")
    assert out["id_source"] == "26-12345"
    assert out["objet"].startswith("Construction")
    assert out["departements"] == "69,01"
    assert out["date_limite_reponse"] == "2026-10-15"
    assert out["type_marche"] == "TRAVAUX"
    assert out["score_pertinence"] >= 1


def test_dedoublonnage_ao(tmp_path, monkeypatch):
    import scraper_appels_offres as s

    monkeypatch.setattr(s, "CSV_PRINCIPAL", tmp_path / "appels_offres.csv")
    monkeypatch.setattr(s, "JSON_PRINCIPAL", tmp_path / "appels_offres.json")
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)

    base = generer_demo_ao(jours=20)
    s.sauvegarder(base)
    df = s.sauvegarder(base)
    assert len(df) == len(base)
    assert not df.duplicated(subset=["id_source"]).any()
