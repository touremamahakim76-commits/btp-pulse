"""Module 1 — Scraper des prix des matériaux de construction (BTP Pulse).

Rôle : constituer et tenir à jour un historique hebdomadaire de prix
par matériau. Ces données alimenteront ensuite :
  - Module 6 : tests statistiques (une hausse est-elle significative ?)
  - Module 7 : modèle prédictif de prix à 30 jours
  - Module 13 : alertes Telegram sur variation significative

Sources (option --source) :
  auto     : essaie Eurostat, bascule sur la démo en cas d'échec (défaut)
  eurostat : force la source réelle Eurostat (HTTP, indices de prix)
  demo     : force le générateur de données réalistes (hors-ligne)

Sorties (dossier ingestion/data/) :
  materiaux_prix.csv   : historique complet, dédoublonné, trié
  materiaux_prix.json  : même contenu, pratique pour l'API (Module 9)
  Un instantané daté   : materiaux_prix_AAAAMMJJ.csv (traçabilité)

Exemples :
  python scraper_prix_materiaux.py
  python scraper_prix_materiaux.py --source demo --semaines 156
  python scraper_prix_materiaux.py --source eurostat -v
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

import pandas as pd

from config import DATA_DIR, SEMAINES_HISTORIQUE_DEFAUT
from sources import COLONNES, fetch_eurostat, generer_demo

log = logging.getLogger("btp_pulse")

CSV_PRINCIPAL = DATA_DIR / "materiaux_prix.csv"
JSON_PRINCIPAL = DATA_DIR / "materiaux_prix.json"


# --------------------------------------------------------------------------
# Récupération des relevés selon la source demandée
# --------------------------------------------------------------------------
def collecter(source: str, semaines: int) -> tuple[list[dict], str]:
    """Retourne (relevés, source_effective)."""
    if source in ("auto", "eurostat"):
        try:
            return fetch_eurostat(), "eurostat"
        except Exception as exc:  # réseau, format, indispo…
            if source == "eurostat":
                log.error("Source Eurostat indisponible : %s", exc)
                raise
            log.warning("Eurostat indisponible (%s) — bascule sur la démo", exc)

    return generer_demo(semaines), "demo"


# --------------------------------------------------------------------------
# Fusion / dédoublonnage / sauvegarde
# --------------------------------------------------------------------------
def sauvegarder(nouveaux: list[dict]) -> pd.DataFrame:
    """Fusionne les nouveaux relevés avec l'historique existant.

    Clé d'unicité : (date_releve, code_materiau). En cas de doublon,
    le relevé le plus récemment ingéré gagne.
    """
    df_nouveaux = pd.DataFrame(nouveaux, columns=COLONNES)

    if CSV_PRINCIPAL.exists():
        df_ancien = pd.read_csv(CSV_PRINCIPAL)
        df = pd.concat([df_ancien, df_nouveaux], ignore_index=True)
    else:
        df = df_nouveaux

    avant = len(df)
    df = (
        df.sort_values("horodatage_ingestion")
        .drop_duplicates(subset=["date_releve", "code_materiau"], keep="last")
        .sort_values(["code_materiau", "date_releve"])
        .reset_index(drop=True)
    )
    log.info("Fusion : %d lignes -> %d après dédoublonnage", avant, len(df))

    df.to_csv(CSV_PRINCIPAL, index=False)
    JSON_PRINCIPAL.write_text(
        json.dumps(df.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    instantane = DATA_DIR / f"materiaux_prix_{date.today():%Y%m%d}.csv"
    df_nouveaux.to_csv(instantane, index=False)
    log.info("Écrit : %s, %s, %s", CSV_PRINCIPAL.name, JSON_PRINCIPAL.name, instantane.name)
    return df


# --------------------------------------------------------------------------
# Contrôle qualité rapide
# --------------------------------------------------------------------------
def controle_qualite(df: pd.DataFrame) -> None:
    problemes = []
    if df["prix"].le(0).any():
        problemes.append("prix négatif ou nul détecté")
    if df.duplicated(subset=["date_releve", "code_materiau"]).any():
        problemes.append("doublons résiduels (date, matériau)")
    if df["date_releve"].isna().any():
        problemes.append("dates manquantes")
    for probleme in problemes:
        log.warning("Contrôle qualité : %s", probleme)
    if not problemes:
        log.info("Contrôle qualité : OK")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scraper prix matériaux — BTP Pulse")
    p.add_argument("--source", choices=["auto", "eurostat", "demo"], default="auto",
                   help="source des données (défaut : auto)")
    p.add_argument("--semaines", type=int, default=SEMAINES_HISTORIQUE_DEFAUT,
                   help="profondeur d'historique pour la démo (défaut : 104)")
    p.add_argument("-v", "--verbose", action="store_true", help="logs détaillés")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Démarrage scraping — source demandée : %s", args.source)
    releves, source_effective = collecter(args.source, args.semaines)
    df = sauvegarder(releves)
    controle_qualite(df)

    derniers = (
        df.sort_values("date_releve")
        .groupby("code_materiau")
        .tail(1)
        .loc[:, ["code_materiau", "date_releve", "prix", "unite", "indice_base100"]]
    )
    print(f"\nSource effective : {source_effective}")
    print(f"Historique : {len(df)} relevés | "
          f"{df['date_releve'].min()} -> {df['date_releve'].max()}\n")
    print("Dernier prix connu par matériau :")
    print(derniers.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
