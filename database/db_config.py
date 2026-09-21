"""Paramètres de connexion PostgreSQL — Module 3.

Les valeurs par défaut sont celles de database/docker-compose.yml :
tout fonctionne sans configuration après `docker compose up`.

Pour surcharger : créer un fichier database/.env (voir .env.example)
ou exporter les variables PGHOST / PGPORT / PGDATABASE / PGUSER /
PGPASSWORD dans le shell.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- mini-chargeur de .env (pas de dépendance externe) --------------------
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for _ligne in _env_path.read_text(encoding="utf-8").splitlines():
        _ligne = _ligne.strip()
        if _ligne and not _ligne.startswith("#") and "=" in _ligne:
            _cle, _, _val = _ligne.partition("=")
            os.environ.setdefault(_cle.strip(), _val.strip())

PG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "btp_pulse"),
    "user": os.getenv("PGUSER", "btp"),
    "password": os.getenv("PGPASSWORD", "btp_pulse_dev"),
}


def dsn() -> str:
    """Chaîne de connexion pour psycopg2.connect()."""
    return (
        f"host={PG['host']} port={PG['port']} dbname={PG['dbname']} "
        f"user={PG['user']} password={PG['password']}"
    )


def sqlalchemy_url() -> str:
    """URL pour SQLAlchemy / pandas.read_sql (Modules 5, 9)."""
    return (
        f"postgresql+psycopg2://{PG['user']}:{PG['password']}"
        f"@{PG['host']}:{PG['port']}/{PG['dbname']}"
    )
