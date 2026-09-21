"""Module 13 — Bot d'alerte Telegram (BTP Pulse).

Deux déclencheurs :
  - une variation de prix jugée SIGNIFICATIVE par le test statistique
    du Module 6 (pas du bruit) ;
  - un nouvel appel d'offres pertinent (score élevé, Module 2) ingéré
    récemment.

Sans TELEGRAM_BOT_TOKEN configuré, le bot ne plante pas : il imprime
le message qu'il aurait envoyé (mode « dry-run »), pour rester
démontrable sans compte Telegram.

Usage :
  python telegram_alerte.py                  # vérifie et alerte si besoin
  python telegram_alerte.py --depuis-heures 48
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402

import bot_config


# =========================================================================
# Formatage (fonctions pures, testables sans base ni réseau)
# =========================================================================
def formater_message_prix(resultats: list[dict]) -> str | None:
    if not resultats:
        return None
    lignes = ["🔔 *Variations de prix significatives*"]
    for r in resultats:
        signe = "+" if r["variation_pct"] >= 0 else ""
        lignes.append(
            f"• *{r['code_materiau']}* : {signe}{r['variation_pct']:.1f}% "
            f"(p={r['p_value']:.4f})"
        )
    return "\n".join(lignes)


MAX_LIGNES_MESSAGE = 10  # Telegram limite un message à 4096 caractères


def formater_message_ao(annonces: list[dict]) -> str | None:
    if not annonces:
        return None
    lignes = ["📢 *Nouveaux appels d'offres pertinents*"]
    for a in annonces[:MAX_LIGNES_MESSAGE]:
        lignes.append(
            f"• [{a['score_pertinence']}] {a['objet'][:80]} "
            f"({a['departements']}, limite {a['date_limite_reponse']})"
        )
    reste = len(annonces) - MAX_LIGNES_MESSAGE
    if reste > 0:
        lignes.append(f"… et {reste} autre(s) — voir le dashboard pour la liste complète.")
    return "\n".join(lignes)


# =========================================================================
# Requêtes PostgreSQL
# =========================================================================
def prix_significatifs_recents(conn, depuis_heures: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (code_materiau)
                   code_materiau, variation_pct, p_value, date_test
            FROM resultats_tests_statistiques
            WHERE significatif
            ORDER BY code_materiau, date_test DESC
            """
        )
        colonnes = [d[0] for d in cur.description]
        lignes = [dict(zip(colonnes, r)) for r in cur.fetchall()]
    from datetime import datetime, timedelta, timezone
    seuil = datetime.now(timezone.utc) - timedelta(hours=depuis_heures)
    return [r for r in lignes if r["date_test"] >= seuil]


def appels_offres_recents(conn, depuis_heures: int, score_min: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT objet, departements, date_limite_reponse, score_pertinence
            FROM appels_offres
            WHERE score_pertinence >= %s
              AND horodatage_ingestion >= now() - (%s || ' hours')::interval
            ORDER BY score_pertinence DESC
            """,
            (score_min, depuis_heures),
        )
        colonnes = [d[0] for d in cur.description]
        return [dict(zip(colonnes, r)) for r in cur.fetchall()]


# =========================================================================
# Envoi
# =========================================================================
def envoyer_message(texte: str) -> bool:
    """Envoie sur Telegram si configuré, sinon affiche (dry-run).

    Renvoie True si un envoi RÉEL a eu lieu.
    """
    if not (bot_config.TELEGRAM_BOT_TOKEN and bot_config.TELEGRAM_CHAT_ID):
        print("(dry-run — TELEGRAM_BOT_TOKEN/CHAT_ID absents)")
        print(texte)
        print()
        return False

    url = bot_config.TELEGRAM_API.format(token=bot_config.TELEGRAM_BOT_TOKEN)
    reponse = requests.post(
        url, json={"chat_id": bot_config.TELEGRAM_CHAT_ID, "text": texte,
                   "parse_mode": "Markdown"},
        timeout=15,
    )
    reponse.raise_for_status()
    return True


def executer(conn, depuis_heures: int, score_min: int) -> int:
    n_envoyes = 0
    msg_prix = formater_message_prix(prix_significatifs_recents(conn, depuis_heures))
    if msg_prix:
        envoyer_message(msg_prix)
        n_envoyes += 1

    msg_ao = formater_message_ao(appels_offres_recents(conn, depuis_heures, score_min))
    if msg_ao:
        envoyer_message(msg_ao)
        n_envoyes += 1

    if n_envoyes == 0:
        print("Rien à signaler (aucune variation significative récente, "
              "aucun nouvel appel d'offres pertinent).")
    return n_envoyes


# =========================================================================
# CLI
# =========================================================================
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bot d'alerte Telegram — BTP Pulse")
    p.add_argument("--depuis-heures", type=int, default=26,
                   help="fenêtre de fraîcheur des événements à signaler")
    p.add_argument("--score-min", type=int, default=bot_config.SCORE_MIN_ALERTE)
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
        executer(conn, args.depuis_heures, args.score_min)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
