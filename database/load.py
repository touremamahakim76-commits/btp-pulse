"""Module 3 — Chargement des données nettoyées dans PostgreSQL.

Enchaîne : lecture des fichiers du Module 1 / Module 2 -> nettoyage
(cleaning.py) -> insertion idempotente en base (upsert).

Prérequis : la base tourne (docker compose -f database/docker-compose.yml up -d).

Usage :
  python load.py --init                 # (ré)applique schema.sql
  python load.py                        # charge tout (référentiel, prix, AO, devis)
  python load.py --table prix
  python load.py --table ao
  python load.py --table devis --nb-devis 200
  python load.py --stats                # affiche juste l'état de la base

Chargement idempotent : on peut relancer autant de fois qu'on veut.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

import db_config
import cleaning
from devis_demo import COLONNES_DEVIS, generer_devis

# --- accès à la configuration du Module 1 (liste des matériaux) -----------
_INGESTION = Path(__file__).resolve().parent.parent / "ingestion"
sys.path.insert(0, str(_INGESTION))
import config as ingestion_config  # noqa: E402

DATA_DIR = _INGESTION / "data"
CSV_PRIX = DATA_DIR / "materiaux_prix.csv"
CSV_AO = DATA_DIR / "appels_offres.csv"
CSV_DEVIS = DATA_DIR / "devis_historique.csv"
SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"


# =========================================================================
# Utilitaires
# =========================================================================
def connexion():
    return psycopg2.connect(db_config.dsn())


def _upsert(cur, table: str, colonnes: list[str], lignes: list[tuple],
            cle_conflit: str, maj: list[str]) -> int:
    """INSERT ... ON CONFLICT (cle) DO UPDATE SET ... — renvoie le nb de lignes."""
    if not lignes:
        return 0
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in maj)
    requete = (
        f"INSERT INTO {table} ({', '.join(colonnes)}) VALUES %s "
        f"ON CONFLICT ({cle_conflit}) DO UPDATE SET {set_clause}"
    )
    execute_values(cur, requete, lignes)
    return len(lignes)


# =========================================================================
# Étapes de chargement
# =========================================================================
def appliquer_schema(conn) -> None:
    print("→ Application de schema.sql")
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.commit()
    print("  OK")


def charger_referentiel(conn) -> None:
    """Table `materiaux` : depuis la config du Module 1, complétée par les
    codes réellement présents dans le CSV de prix."""
    print("→ Référentiel matériaux")
    ref: dict[str, dict] = {
        m["code"]: {"code": m["code"], "libelle": m["libelle"],
                    "unite": m["unite"], "prix_ref": m["prix_ref"]}
        for m in ingestion_config.MATERIAUX
    }
    if CSV_PRIX.exists():
        df = pd.read_csv(CSV_PRIX)
        for _, r in df[["code_materiau", "libelle", "unite"]].drop_duplicates().iterrows():
            ref.setdefault(r["code_materiau"], {
                "code": r["code_materiau"], "libelle": r["libelle"],
                "unite": r["unite"], "prix_ref": None})

    lignes = [(v["code"], v["libelle"], v["unite"], v["prix_ref"]) for v in ref.values()]
    with conn.cursor() as cur:
        n = _upsert(cur, "materiaux",
                    ["code", "libelle", "unite", "prix_ref"], lignes,
                    "code", ["libelle", "unite", "prix_ref"])
    conn.commit()
    print(f"  {n} matériaux")


def charger_prix(conn) -> None:
    print("→ Prix des matériaux")
    if not CSV_PRIX.exists():
        print(f"  (ignoré : {CSV_PRIX} absent — lance d'abord le Module 1)")
        return
    df = pd.read_csv(CSV_PRIX)
    prix_ref = {m["code"]: m["prix_ref"] for m in ingestion_config.MATERIAUX}
    df, rap = cleaning.nettoyer_prix(df, prix_ref)
    cleaning.afficher_rapport("prix", rap)

    lignes = [
        (r["date_releve"], r["code_materiau"], r["prix"],
         r.get("indice_base100"), r["source"], r["horodatage_ingestion"])
        for _, r in df.iterrows()
    ]
    with conn.cursor() as cur:
        n = _upsert(
            cur, "materiaux_prix",
            ["date_releve", "code_materiau", "prix", "indice_base100",
             "source", "horodatage_ingestion"],
            lignes, "date_releve, code_materiau",
            ["prix", "indice_base100", "source", "horodatage_ingestion"],
        )
    conn.commit()
    print(f"  {n} relevés chargés")


def charger_ao(conn) -> None:
    print("→ Appels d'offres")
    if not CSV_AO.exists():
        print(f"  (ignoré : {CSV_AO} absent — lance d'abord le Module 2)")
        return
    df = pd.read_csv(CSV_AO)
    df, rap = cleaning.nettoyer_appels_offres(df)
    cleaning.afficher_rapport("appels_offres", rap)

    cols = ["id_source", "objet", "acheteur", "departements", "date_parution",
            "date_limite_reponse", "type_marche", "categorie",
            "mots_cles_trouves", "score_pertinence", "url_avis",
            "source", "horodatage_ingestion"]
    lignes = [tuple(None if pd.isna(r[c]) else r[c] for c in cols)
              for _, r in df.iterrows()]
    with conn.cursor() as cur:
        n = _upsert(cur, "appels_offres", cols, lignes, "id_source",
                    [c for c in cols if c != "id_source"])
    conn.commit()
    print(f"  {n} appels d'offres chargés")


def charger_devis(conn, nb: int) -> None:
    print(f"→ Devis de démonstration ({nb})")
    devis = generer_devis(nb)
    df = pd.DataFrame(devis, columns=COLONNES_DEVIS)
    df, rap = cleaning.nettoyer_devis(df)
    cleaning.afficher_rapport("devis", rap)

    # trace CSV pour les modules suivants (RAG, API)
    df.to_csv(CSV_DEVIS, index=False)

    lignes = [tuple(r[c] for c in COLONNES_DEVIS) for _, r in df.iterrows()]
    with conn.cursor() as cur:
        n = _upsert(cur, "devis_historique", COLONNES_DEVIS, lignes,
                    "id_devis", [c for c in COLONNES_DEVIS if c != "id_devis"])
    conn.commit()
    print(f"  {n} devis chargés  (copie : {CSV_DEVIS.relative_to(_INGESTION.parent)})")


def afficher_stats(conn) -> None:
    print("\n--- État de la base ---")
    with conn.cursor() as cur:
        for table in ("materiaux", "materiaux_prix", "appels_offres", "devis_historique"):
            cur.execute(f"SELECT count(*) FROM {table}")
            print(f"  {table:20} {cur.fetchone()[0]:>7} lignes")

        cur.execute("SELECT code_materiau, date_releve, prix, indice_base100 "
                    "FROM v_dernier_prix_materiau ORDER BY code_materiau")
        rows = cur.fetchall()
    if rows:
        print("\n  Dernier prix connu (vue v_dernier_prix_materiau) :")
        for code, d, prix, idx in rows:
            print(f"    {code:12} {d}  {float(prix):>10.2f}  (indice {float(idx):.1f})")


# =========================================================================
# CLI
# =========================================================================
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Chargement PostgreSQL — BTP Pulse")
    p.add_argument("--init", action="store_true", help="(ré)applique schema.sql")
    p.add_argument("--table", choices=["all", "materiaux", "prix", "ao", "devis"],
                   default="all")
    p.add_argument("--nb-devis", type=int, default=120)
    p.add_argument("--stats", action="store_true", help="affiche l'état de la base et sort")
    args = p.parse_args(argv)

    # Console Windows : forcer l'UTF-8 pour les accents et les flèches.
    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        conn = connexion()
    except psycopg2.OperationalError as exc:
        print(f"ERREUR : impossible de se connecter à PostgreSQL.\n{exc}\n"
              "→ Démarre la base : "
              "docker compose -f database/docker-compose.yml up -d")
        return 1

    try:
        if args.init:
            appliquer_schema(conn)

        if args.stats:
            # --stats : affiche l'état et sort (schéma déjà appliqué si --init
            # était présent), sans (re)charger les tables.
            afficher_stats(conn)
            return 0

        if args.table in ("all", "materiaux"):
            charger_referentiel(conn)
        if args.table in ("all", "prix"):
            charger_prix(conn)
        if args.table in ("all", "ao"):
            charger_ao(conn)
        if args.table in ("all", "devis"):
            charger_devis(conn, args.nb_devis)

        afficher_stats(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
