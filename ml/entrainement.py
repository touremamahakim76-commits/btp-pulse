"""Module 7 — Entraînement du modèle prédictif de prix (BTP Pulse).

Un seul modèle combiné (le matériau est une feature catégorielle
one-hot) plutôt qu'un modèle par matériau : plus simple à maintenir,
et les matériaux corrélés (ex. tous les métaux) s'enrichissent
mutuellement.

Découpage train/test TEMPOREL (pas aléatoire) : on entraîne sur le
passé, on valide sur les relevés les plus récents. Un split aléatoire
mélangerait des dates voisines entre train et test et biaiserait
l'évaluation (fuite d'information).

Usage :
  python entrainement.py                       # horizon 30 jours (défaut)
  python entrainement.py --horizon-jours 60
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psycopg2
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402

from dataset import COLONNES_FEATURES, construire_dataset_complet

MODELE_DIR = Path(__file__).resolve().parent / "modele"
MODELE_DIR.mkdir(exist_ok=True)
FICHIER_MODELE = MODELE_DIR / "modele_prix.joblib"
FICHIER_METADATA = MODELE_DIR / "metadata.json"


def _pipeline(modele) -> Pipeline:
    pretraitement = ColumnTransformer(
        transformers=[
            ("materiau", OneHotEncoder(handle_unknown="ignore"), ["code_materiau"]),
        ],
        remainder="passthrough",
    )
    return Pipeline([("pretraitement", pretraitement), ("modele", modele)])


def entrainer(df_prix: pd.DataFrame, horizon_jours: int) -> dict:
    dataset = construire_dataset_complet(df_prix, horizon_jours=horizon_jours)

    # lignes exploitables pour l'entraînement : features complètes + cible connue
    entrainable = dataset.dropna(subset=[*COLONNES_FEATURES, "prix_cible_log"])
    if len(entrainable) < 20:
        raise RuntimeError(
            f"Pas assez de données entraînables ({len(entrainable)} lignes) "
            "pour un split train/test fiable."
        )

    seuil_date = entrainable["date_releve"].quantile(0.8)
    train = entrainable[entrainable["date_releve"] <= seuil_date]
    test = entrainable[entrainable["date_releve"] > seuil_date]
    if len(test) < 5:  # filet de sécurité si peu de matériaux/relevés
        train, test = entrainable.iloc[: -max(5, len(entrainable) // 5)], entrainable.iloc[-max(5, len(entrainable) // 5):]

    # On entraîne en LOG du prix (cf. dataset.py) : le pipeline apprend
    # à prédire log(prix_cible). On reconvertit avec exp() pour évaluer
    # et publier l'erreur en € — parlant pour le métier — plutôt qu'en
    # log, illisible.
    colonnes = ["code_materiau", *COLONNES_FEATURES]
    X_train, y_train = train[colonnes], train["prix_cible_log"]
    X_test, y_test_log = test[colonnes], test["prix_cible_log"]
    y_test = test["prix_cible"]

    candidats = {
        "regression_lineaire": _pipeline(LinearRegression()),
        "foret_aleatoire": _pipeline(RandomForestRegressor(n_estimators=300, random_state=42)),
    }

    resultats = {}
    for nom, pipe in candidats.items():
        pipe.fit(X_train, y_train)
        preds_log = pipe.predict(X_test)
        preds = np.exp(preds_log)
        resultats[nom] = {
            "pipeline": pipe,
            "mae": float(mean_absolute_error(y_test, preds)),
            "mape": float(np.mean(np.abs((preds - y_test) / y_test)) * 100),
            "r2": float(r2_score(y_test_log, preds_log)) if len(set(y_test_log)) > 1 else None,
        }
        print(f"  {nom:20} MAE={resultats[nom]['mae']:.3f} €  "
              f"MAPE={resultats[nom]['mape']:.2f}%  R²(log)={resultats[nom]['r2']}")

    # Sélection sur l'erreur RELATIVE (MAPE) : un modèle qui se trompe de
    # 50 € sur du cuivre à 9 800 € (0,5 %) est meilleur que 50 € sur du
    # parpaing à 1,35 € (3 700 %) — la MAE seule mélangerait les échelles.
    meilleur_nom = min(resultats, key=lambda n: resultats[n]["mape"])
    meilleur = resultats[meilleur_nom]
    print(f"→ Modèle retenu : {meilleur_nom} (MAPE={meilleur['mape']:.2f}%)")

    return {
        "pipeline": meilleur["pipeline"],
        "nom_modele": meilleur_nom,
        "mae": meilleur["mae"],
        "mape": meilleur["mape"],
        "r2": meilleur["r2"],
        "n_train": len(train),
        "n_test": len(test),
        "horizon_jours": horizon_jours,
        "colonnes": colonnes,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Entraînement modèle prix — BTP Pulse")
    p.add_argument("--horizon-jours", type=int, default=30)
    args = p.parse_args(argv)

    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        conn = psycopg2.connect(db_config.dsn())
    except psycopg2.OperationalError as exc:
        print(f"ERREUR : connexion PostgreSQL impossible.\n{exc}")
        return 1

    try:
        from sqlalchemy import create_engine
        moteur = create_engine(db_config.sqlalchemy_url())
        df_prix = pd.read_sql(
            "SELECT date_releve, code_materiau, prix FROM materiaux_prix ORDER BY date_releve",
            moteur,
        )
    finally:
        conn.close()

    print(f"Entraînement sur {len(df_prix)} relevés, horizon = {args.horizon_jours} jours\n")
    resultat = entrainer(df_prix, args.horizon_jours)

    joblib.dump(resultat["pipeline"], FICHIER_MODELE)
    FICHIER_METADATA.write_text(json.dumps({
        "nom_modele": resultat["nom_modele"],
        "mae": resultat["mae"],
        "mape": resultat["mape"],
        "r2": resultat["r2"],
        "n_train": resultat["n_train"],
        "n_test": resultat["n_test"],
        "horizon_jours": resultat["horizon_jours"],
        "colonnes": resultat["colonnes"],
        "date_entrainement": datetime.now().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")

    print(f"\nModèle sauvegardé : {FICHIER_MODELE.relative_to(MODELE_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
