"""Module 9 — Accès base de données pour l'API (BTP Pulse).

Un petit pool de connexions PostgreSQL (SimpleConnectionPool) plutôt
qu'une connexion par requête HTTP : plus réaliste pour une API qui
sert plusieurs clients, sans la complexité d'un pool async.
"""
from __future__ import annotations

import sys
from pathlib import Path

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402

_pool: pool.SimpleConnectionPool | None = None


def get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 10, db_config.dsn())
    return _pool


def requete(sql: str, params: tuple = ()) -> list[dict]:
    """Exécute une requête SELECT et renvoie une liste de dicts."""
    p = get_pool()
    conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        p.putconn(conn)
