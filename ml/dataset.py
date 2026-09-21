"""Module 7 — Construction du jeu de données d'entraînement (BTP Pulse).

Fonction PURE (pandas in/out), testable sans base de données.

Pour chaque matériau, on construit des features à partir de l'historique
(prix courant, 3 derniers relevés, moyenne mobile, tendance temporelle)
et une cible = le prix réel observé au moins `horizon_jours` plus tard
(recherche du prochain relevé disponible par `merge_asof`, robuste à
une cadence irrégulière : mensuelle pour Eurostat, hebdomadaire pour
la démo).

Les lignes les plus récentes n'ont pas encore de cible connue (le futur
n'existe pas dans l'historique) : ce sont justement celles qu'on utilise
pour la PRÉDICTION en production (predire.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def construire_dataset_materiau(
    df_mat: pd.DataFrame, horizon_jours: int = 30, n_lags: int = 3
) -> pd.DataFrame:
    """`df_mat` : colonnes `date_releve`, `prix` pour UN matériau.

    Renvoie le même dataframe enrichi de colonnes `lag1..lagN`,
    `moy_mobile_3`, `tendance`, `prix_cible` (NaN si aucun relevé futur
    disponible à l'horizon demandé).
    """
    d = df_mat.sort_values("date_releve").reset_index(drop=True).copy()
    d["date_releve"] = pd.to_datetime(d["date_releve"])

    for k in range(1, n_lags + 1):
        d[f"lag{k}"] = d["prix"].shift(k)
    d["moy_mobile_3"] = d["prix"].rolling(3).mean()
    d["tendance"] = range(len(d))

    # Passage au log : les matériaux vont de 1,35 € (parpaing) à 9 800 €
    # (cuivre), 3 ordres de grandeur d'écart. Un modèle entraîné sur le
    # prix brut laisserait les matériaux chers dominer l'erreur globale
    # et biaiserait les coefficients partagés (tendance, moyenne mobile)
    # pour les matériaux bon marché. En log, une variation relative de
    # 5 % pèse pareil pour tout le monde.
    for col in ["prix", *[f"lag{k}" for k in range(1, n_lags + 1)], "moy_mobile_3"]:
        d[f"{col}_log"] = np.log(d[col])

    futur = d[["date_releve", "prix"]].rename(
        columns={"date_releve": "date_f", "prix": "prix_f"}
    )
    d["date_cible"] = d["date_releve"] + pd.to_timedelta(horizon_jours, unit="D")
    d = pd.merge_asof(
        d.sort_values("date_cible"),
        futur.sort_values("date_f"),
        left_on="date_cible", right_on="date_f", direction="forward",
    )
    d = d.sort_values("date_releve").reset_index(drop=True)
    d["prix_cible"] = d["prix_f"]
    d["prix_cible_log"] = np.log(d["prix_cible"])
    return d.drop(columns=["date_f"])


# Features en log (cf. commentaire ci-dessus) + tendance temporelle brute
# (un décalage d'indice, pas un prix : pas besoin de log).
COLONNES_FEATURES = ["prix_log", "lag1_log", "lag2_log", "lag3_log",
                     "moy_mobile_3_log", "tendance"]


def construire_dataset_complet(
    df_prix: pd.DataFrame, horizon_jours: int = 30, n_lags: int = 3
) -> pd.DataFrame:
    """`df_prix` : colonnes `date_releve`, `code_materiau`, `prix`, tous
    matériaux confondus. Concatène le dataset matériau par matériau."""
    morceaux = []
    for code, groupe in df_prix.groupby("code_materiau"):
        d = construire_dataset_materiau(
            groupe[["date_releve", "prix"]], horizon_jours, n_lags
        )
        d["code_materiau"] = code
        morceaux.append(d)
    return pd.concat(morceaux, ignore_index=True)
