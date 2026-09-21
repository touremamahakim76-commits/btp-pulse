"""Paramètres de connexion BigQuery — Module 5.

Pour surcharger : créer un fichier warehouse/.env (voir .env.example)
ou exporter les variables dans le shell. `BQ_PROJECT` est obligatoire
(pas de valeur par défaut : impossible de deviner ton projet GCP).
"""
from __future__ import annotations

import os
from pathlib import Path

# --- mini-chargeur de .env (même logique que database/db_config.py) ------
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for _ligne in _env_path.read_text(encoding="utf-8").splitlines():
        _ligne = _ligne.strip()
        if _ligne and not _ligne.startswith("#") and "=" in _ligne:
            _cle, _, _val = _ligne.partition("=")
            os.environ.setdefault(_cle.strip(), _val.strip())

BQ_PROJECT = os.getenv("BQ_PROJECT")
BQ_DATASET = os.getenv("BQ_DATASET", "btp_pulse")
BQ_LOCATION = os.getenv("BQ_LOCATION", "EU")


def verifier_configuration() -> None:
    if not BQ_PROJECT:
        raise RuntimeError(
            "BQ_PROJECT n'est pas défini.\n"
            "→ copie warehouse/.env.example en warehouse/.env et renseigne "
            "l'identifiant de ton projet Google Cloud (BQ_PROJECT=...)."
        )
