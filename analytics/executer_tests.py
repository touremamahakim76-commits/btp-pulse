"""Module 6 — CLI : exécute le test de significativité pour tous les
matériaux et enregistre les résultats en base.

Usage :
  python executer_tests.py
  python executer_tests.py --jours-recents 150 --jours-reference 365 --alpha 0.05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402
import psycopg2  # noqa: E402

from tests_statistiques import executer_tous


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tests statistiques de prix — BTP Pulse")
    p.add_argument("--jours-recents", type=int, default=150)
    p.add_argument("--jours-reference", type=int, default=365)
    p.add_argument("--alpha", type=float, default=0.05)
    args = p.parse_args(argv)

    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        conn = psycopg2.connect(db_config.dsn())
    except psycopg2.OperationalError as exc:
        print(f"ERREUR : connexion à PostgreSQL impossible.\n{exc}\n"
              "→ docker compose -f database/docker-compose.yml up -d")
        return 1

    try:
        resultats = executer_tous(conn, args.jours_recents, args.jours_reference, args.alpha)
    finally:
        conn.close()

    if not resultats:
        print("Aucun matériau n'a assez d'historique pour ce test "
              "(essaie des fenêtres plus larges).")
        return 0

    print(f"{len(resultats)} matériaux testés (seuil α={args.alpha})\n")
    print(f"{'matériau':14} {'n_rec':>6} {'n_réf':>6} {'variation':>10} "
          f"{'p_value':>10}  significatif ?")
    for r in sorted(resultats, key=lambda x: x["p_value"]):
        marque = "OUI — alerte" if r["significatif"] else "non (bruit)"
        print(f"{r['code_materiau']:14} {r['n_recents']:>6} {r['n_reference']:>6} "
              f"{r['variation_pct']:>9.1f}% {r['p_value']:>10.5f}  {marque}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
