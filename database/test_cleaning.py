"""Tests du Module 3 — pytest database/ -v  (aucune base requise).

On teste les fonctions de nettoyage (pures) et le générateur de devis.
"""
from __future__ import annotations

import pandas as pd

import cleaning
from devis_demo import COLONNES_DEVIS, generer_devis


def _df_prix():
    return pd.DataFrame([
        # ok
        {"date_releve": "2026-01-05", "code_materiau": "ACIER_T", "prix": 900,
         "indice_base100": 100, "source": "demo", "horodatage_ingestion": "2026-01-05T10:00:00"},
        # doublon (même date+matériau), plus récent -> gagne
        {"date_releve": "2026-01-05", "code_materiau": "ACIER_T", "prix": 950,
         "indice_base100": 105, "source": "demo", "horodatage_ingestion": "2026-01-06T10:00:00"},
        # prix négatif
        {"date_releve": "2026-01-12", "code_materiau": "ACIER_T", "prix": -5,
         "indice_base100": 0, "source": "demo", "horodatage_ingestion": "2026-01-12T10:00:00"},
        # valeur manquante (prix nul/None)
        {"date_releve": "2026-01-19", "code_materiau": "ACIER_T", "prix": None,
         "indice_base100": None, "source": "demo", "horodatage_ingestion": "2026-01-19T10:00:00"},
        # aberrant (x100 vs prix_ref 950)
        {"date_releve": "2026-01-26", "code_materiau": "ACIER_T", "prix": 95000,
         "indice_base100": 9999, "source": "demo", "horodatage_ingestion": "2026-01-26T10:00:00"},
        # date invalide
        {"date_releve": "pas-une-date", "code_materiau": "ACIER_T", "prix": 940,
         "indice_base100": 99, "source": "demo", "horodatage_ingestion": "2026-01-30T10:00:00"},
    ])


def test_nettoyer_prix():
    df, rap = cleaning.nettoyer_prix(_df_prix(), prix_ref={"ACIER_T": 950.0})
    assert len(df) == 1
    assert df.iloc[0]["prix"] == 950  # le doublon le plus récent
    assert rap["retirees"]["doublon"] == 1
    assert rap["retirees"]["prix_negatif_ou_nul"] == 1
    assert rap["retirees"]["valeur_aberrante"] == 1
    assert rap["retirees"]["valeurs_manquantes"] == 1
    assert rap["retirees"]["date_ou_prix_invalide"] == 1


def test_nettoyer_appels_offres_dates_et_doublons():
    df = pd.DataFrame([
        {"id_source": "A1", "objet": "Travaux  de   maçonnerie", "acheteur": " Mairie ",
         "categorie": "Bâtiment", "mots_cles_trouves": "maçonnerie", "score_pertinence": "3",
         "date_parution": "2026-03-10", "date_limite_reponse": "2026-02-01",  # incohérent
         "type_marche": "TRAVAUX", "url_avis": "x", "source": "boamp",
         "horodatage_ingestion": "2026-03-10T10:00:00"},
        {"id_source": "A1", "objet": "Travaux de maçonnerie (v2)", "acheteur": "Mairie",
         "categorie": "Bâtiment", "mots_cles_trouves": "maçonnerie", "score_pertinence": "4",
         "date_parution": "2026-03-11", "date_limite_reponse": "2026-04-15",
         "type_marche": "TRAVAUX", "url_avis": "x", "source": "boamp",
         "horodatage_ingestion": "2026-03-12T10:00:00"},
        {"id_source": None, "objet": "sans id", "score_pertinence": 0,
         "date_parution": "2026-03-01", "date_limite_reponse": None,
         "acheteur": None, "categorie": None, "mots_cles_trouves": None,
         "type_marche": "TRAVAUX", "url_avis": None, "source": "boamp",
         "horodatage_ingestion": "2026-03-01T10:00:00"},
    ])
    out, rap = cleaning.nettoyer_appels_offres(df)
    assert len(out) == 1
    assert out.iloc[0]["objet"] == "Travaux de maçonnerie (v2)"  # espaces normalisés + plus récent
    assert rap["retirees"]["sans_id_ou_objet"] == 1
    assert rap["retirees"]["doublon"] == 1
    assert rap["retirees"]["date_limite_incoherente_corrigee"] == 1


def test_generer_devis_valide_et_reproductible():
    d1 = generer_devis(n=80, seed=7)
    d2 = generer_devis(n=80, seed=7)
    assert d1 == d2
    assert len(d1) == 80
    assert set(d1[0]) == set(COLONNES_DEVIS)
    assert all(x["montant_ht"] > 0 for x in d1)
    assert all(x["statut"] in {"gagné", "perdu", "en cours"} for x in d1)
    assert all(1.0 <= x["marge_estimee_pct"] <= 18.0 for x in d1)

    df, rap = cleaning.nettoyer_devis(pd.DataFrame(d1))
    assert rap["lignes_sortie"] == 80
