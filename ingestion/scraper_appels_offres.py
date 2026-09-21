"""Module 2 — Scraper des appels d'offres publics BTP (BTP Pulse).

Rôle : récupérer chaque jour les nouveaux marchés publics susceptibles
d'intéresser l'entreprise, les filtrer/scorer par mots-clés du secteur,
et tenir un historique dédoublonné. Ces données alimenteront :
  - Module 9  : endpoint API « appels d'offres filtrés »
  - Module 13 : alerte Telegram sur nouvel appel d'offres pertinent

Source : BOAMP open data (API Opendatasoft, sans authentification).

Sources (option --source) :
  auto  : essaie le BOAMP, bascule sur la démo en cas d'échec (défaut)
  boamp : force la source réelle
  demo  : force le jeu d'annonces fictives (hors-ligne)

Sorties (dossier ingestion/data/) :
  appels_offres.csv / .json  : historique complet, dédoublonné, trié
  appels_offres_AAAAMMJJ.csv : instantané du jour

Exemples :
  python scraper_appels_offres.py
  python scraper_appels_offres.py --jours 15 --departements 69,01,38
  python scraper_appels_offres.py --tous-types -v
  python scraper_appels_offres.py --source demo
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

import pandas as pd

from config import BOAMP_JOURS_DEFAUT, DATA_DIR, SCORE_MIN_PERTINENCE
from sources_ao import COLONNES_AO, fetch_boamp, generer_demo_ao

log = logging.getLogger("btp_pulse")

CSV_PRINCIPAL = DATA_DIR / "appels_offres.csv"
JSON_PRINCIPAL = DATA_DIR / "appels_offres.json"


def collecter(source: str, jours: int, departements: list[str] | None,
              tous_types: bool) -> tuple[list[dict], str]:
    if source in ("auto", "boamp"):
        try:
            return fetch_boamp(jours, departements, tous_types), "boamp"
        except Exception as exc:
            if source == "boamp":
                log.error("Source BOAMP indisponible : %s", exc)
                raise
            log.warning("BOAMP indisponible (%s) — bascule sur la démo", exc)
    return generer_demo_ao(jours), "demo"


def filtrer_pertinence(annonces: list[dict], tous_types: bool) -> list[dict]:
    """Ne garde que les annonces réellement liées au BTP.

    - si on a déjà filtré sur `type_marche = TRAVAUX` côté API, on garde
      tout (mais on trie par score) ;
    - en mode `--tous-types`, on exige un score minimal de mots-clés.
    """
    if tous_types:
        retenues = [a for a in annonces if a["score_pertinence"] >= SCORE_MIN_PERTINENCE]
        log.info("Filtre pertinence : %d / %d annonces retenues",
                 len(retenues), len(annonces))
        return retenues
    return annonces


def sauvegarder(nouvelles: list[dict]) -> pd.DataFrame:
    """Fusionne avec l'historique. Clé d'unicité : id_source."""
    df_nouv = pd.DataFrame(nouvelles, columns=COLONNES_AO)

    if CSV_PRINCIPAL.exists():
        df = pd.concat([pd.read_csv(CSV_PRINCIPAL), df_nouv], ignore_index=True)
    else:
        df = df_nouv

    avant = len(df)
    df = (
        df.sort_values("horodatage_ingestion")
        .drop_duplicates(subset=["id_source"], keep="last")
        .sort_values(["date_parution", "score_pertinence"], ascending=[False, False])
        .reset_index(drop=True)
    )
    log.info("Fusion : %d lignes -> %d après dédoublonnage", avant, len(df))

    df.to_csv(CSV_PRINCIPAL, index=False)
    JSON_PRINCIPAL.write_text(
        json.dumps(df.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    instantane = DATA_DIR / f"appels_offres_{date.today():%Y%m%d}.csv"
    df_nouv.to_csv(instantane, index=False)
    log.info("Écrit : %s, %s, %s", CSV_PRINCIPAL.name, JSON_PRINCIPAL.name, instantane.name)
    return df


def controle_qualite(df: pd.DataFrame) -> None:
    problemes = []
    if df["id_source"].isna().any():
        problemes.append("identifiant source manquant")
    if df.duplicated(subset=["id_source"]).any():
        problemes.append("doublons résiduels (id_source)")
    if df["date_parution"].isna().any():
        problemes.append("date de parution manquante")
    for p in problemes:
        log.warning("Contrôle qualité : %s", p)
    if not problemes:
        log.info("Contrôle qualité : OK")


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Scraper appels d'offres BTP — BTP Pulse")
    p.add_argument("--source", choices=["auto", "boamp", "demo"], default="auto")
    p.add_argument("--jours", type=int, default=BOAMP_JOURS_DEFAUT,
                   help=f"profondeur en jours de parution (défaut : {BOAMP_JOURS_DEFAUT})")
    p.add_argument("--departements", type=str, default=None,
                   help="codes département séparés par des virgules, ex. 69,01,38")
    p.add_argument("--tous-types", action="store_true",
                   help="ne pas restreindre aux marchés de travaux ; "
                        "filtrer uniquement sur les mots-clés BTP")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    departements = (
        [d.strip() for d in args.departements.split(",") if d.strip()]
        if args.departements else None
    )

    log.info("Démarrage scraping appels d'offres — source : %s | %d jours%s",
             args.source, args.jours,
             f" | départements {departements}" if departements else "")

    annonces, source_effective = collecter(args.source, args.jours,
                                           departements, args.tous_types)
    annonces = filtrer_pertinence(annonces, args.tous_types)
    df = sauvegarder(annonces)
    controle_qualite(df)

    print(f"\nSource effective : {source_effective}")
    print(f"Historique : {len(df)} appels d'offres | "
          f"parutions {df['date_parution'].min()} -> {df['date_parution'].max()}")
    top = df.head(10)[["date_parution", "departements", "score_pertinence", "objet"]]
    print("\n10 annonces les plus récentes :")
    for _, r in top.iterrows():
        objet = (r["objet"][:90] + "…") if len(str(r["objet"])) > 90 else r["objet"]
        print(f"  {r['date_parution']} [{r['departements']:>8}] score {r['score_pertinence']}  {objet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
