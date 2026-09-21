"""Tests du Module 7 — pytest ml/ -v (aucune base requise, tout en synthétique)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from dataset import COLONNES_FEATURES, construire_dataset_complet, construire_dataset_materiau
from entrainement import entrainer
from predire import dernieres_lignes_par_materiau


def _serie_lineaire(n=60, pente=1.0, base=100.0, freq_jours=30):
    dates = pd.date_range("2020-01-01", periods=n, freq=f"{freq_jours}D")
    prix = base + pente * np.arange(n)
    return pd.DataFrame({"date_releve": dates, "prix": prix})


def test_construire_dataset_materiau_cible_correcte():
    df = _serie_lineaire(n=10, pente=10.0, freq_jours=30)
    out = construire_dataset_materiau(df, horizon_jours=30, n_lags=2)
    # la cible à horizon 30j doit correspondre au relevé suivant (cadence mensuelle)
    ligne = out.iloc[0]
    assert ligne["prix_cible"] == df.iloc[1]["prix"]
    # la toute dernière ligne n'a pas de futur -> cible manquante
    assert pd.isna(out.iloc[-1]["prix_cible"])


def test_dataset_complet_plusieurs_materiaux():
    a = _serie_lineaire(n=20, pente=5.0, base=100.0)
    a["code_materiau"] = "A"
    b = _serie_lineaire(n=20, pente=-2.0, base=500.0)
    b["code_materiau"] = "B"
    df_prix = pd.concat([a, b])[["date_releve", "code_materiau", "prix"]]

    out = construire_dataset_complet(df_prix, horizon_jours=30)
    assert set(out["code_materiau"]) == {"A", "B"}
    assert all(c in out.columns for c in COLONNES_FEATURES)


def test_entrainement_et_prediction_bout_en_bout():
    # séries linéaires bruitées, sur assez de points pour un split 80/20
    rng = np.random.default_rng(0)
    morceaux = []
    for code, pente, base in [("A", 8.0, 100.0), ("B", -3.0, 300.0), ("C", 1.0, 50.0)]:
        s = _serie_lineaire(n=60, pente=pente, base=base)
        s["prix"] = s["prix"] + rng.normal(0, 0.5, len(s))
        s["code_materiau"] = code
        morceaux.append(s)
    df_prix = pd.concat(morceaux)[["date_releve", "code_materiau", "prix"]]

    resultat = entrainer(df_prix, horizon_jours=30)
    assert resultat["mae"] < 20  # tendance quasi linéaire -> devrait bien s'apprendre

    courant = dernieres_lignes_par_materiau(df_prix, horizon_jours=30)
    colonnes = ["code_materiau", *COLONNES_FEATURES]
    preds = resultat["pipeline"].predict(courant[colonnes])
    assert len(preds) == 3
    assert all(np.isfinite(preds))
