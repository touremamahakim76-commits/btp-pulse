"""Module 7 — Prédiction du prix à 30 jours (BTP Pulse).

Charge le modèle entraîné (entrainement.py), calcule les features à
partir du DERNIER relevé connu de chaque matériau, prédit le prix à
l'horizon appris, et enregistre le résultat dans `predictions_prix`.

Usage :
  python predire.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402

from dataset import COLONNES_FEATURES, construire_dataset_complet

MODELE_DIR = Path(__file__).resolve().parent / "modele"
FICHIER_MODELE = MODELE_DIR / "modele_prix.joblib"
FICHIER_METADATA = MODELE_DIR / "metadata.json"


def dernieres_lignes_par_materiau(df_prix: pd.DataFrame, horizon_jours: int) -> pd.DataFrame:
    dataset = construire_dataset_complet(df_prix, horizon_jours=horizon_jours)
    dataset = dataset.dropna(subset=COLONNES_FEATURES)
    idx_dernier = dataset.groupby("code_materiau")["date_releve"].idxmax()
    return dataset.loc[idx_dernier].reset_index(drop=True)


def predire(conn, pipeline, horizon_jours: int, mae: float | None,
           nom_modele: str) -> pd.DataFrame:
    from sqlalchemy import create_engine
    moteur = create_engine(db_config.sqlalchemy_url())
    df_prix = pd.read_sql(
        "SELECT date_releve, code_materiau, prix FROM materiaux_prix ORDER BY date_releve",
        moteur,
    )
    courant = dernieres_lignes_par_materiau(df_prix, horizon_jours)
    colonnes = ["code_materiau", *COLONNES_FEATURES]
    # le pipeline prédit log(prix) (cf. entrainement.py) -> on repasse en €
    courant["prix_predit"] = np.exp(pipeline.predict(courant[colonnes]))
    courant["prix_actuel"] = courant["prix"]
    courant["variation_pct_predite"] = round(
        100 * (courant["prix_predit"] - courant["prix_actuel"]) / courant["prix_actuel"], 2
    )
    courant["modele"] = nom_modele
    courant["mae_validation"] = mae
    courant["horizon_jours"] = horizon_jours
    return courant[["code_materiau", "prix_actuel", "prix_predit",
                    "variation_pct_predite", "modele", "mae_validation", "horizon_jours"]]


def enregistrer(conn, df_predictions: pd.DataFrame) -> None:
    with conn.cursor() as cur:
        for _, r in df_predictions.iterrows():
            cur.execute(
                """
                INSERT INTO predictions_prix
                    (code_materiau, horizon_jours, prix_actuel, prix_predit,
                     variation_pct_predite, modele, mae_validation)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (r["code_materiau"], int(r["horizon_jours"]), float(r["prix_actuel"]),
                 float(r["prix_predit"]), float(r["variation_pct_predite"]),
                 r["modele"], None if pd.isna(r["mae_validation"]) else float(r["mae_validation"])),
            )
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    if not FICHIER_MODELE.exists():
        print("ERREUR : aucun modèle entraîné.\n→ python entrainement.py")
        return 1

    pipeline = joblib.load(FICHIER_MODELE)
    meta = json.loads(FICHIER_METADATA.read_text(encoding="utf-8"))

    try:
        conn = psycopg2.connect(db_config.dsn())
    except psycopg2.OperationalError as exc:
        print(f"ERREUR : connexion PostgreSQL impossible.\n{exc}")
        return 1

    try:
        df = predire(conn, pipeline, meta["horizon_jours"], meta["mae"], meta["nom_modele"])
        enregistrer(conn, df)
    finally:
        conn.close()

    print(f"Prédictions à {meta['horizon_jours']} jours (modèle {meta['nom_modele']}, "
          f"MAE validation ≈ {meta['mae']:.2f}) :\n")
    print(df.drop(columns=["modele", "mae_validation", "horizon_jours"])
          .to_string(index=False, formatters={
              "prix_actuel": "{:.2f}".format, "prix_predit": "{:.2f}".format,
              "variation_pct_predite": "{:+.1f}%".format,
          }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
