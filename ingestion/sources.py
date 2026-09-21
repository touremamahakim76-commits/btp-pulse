"""Sources de données pour le scraping des prix matériaux — BTP Pulse.

Deux fonctions publiques :

    fetch_eurostat(...)       -> récupère des indices de prix réels sur
                                 l'API Eurostat (HTTP, JSON-stat).
    generer_demo(...)         -> génère un historique de prix réaliste,
                                 hors-ligne et reproductible.

Le scraper (scraper_prix_materiaux.py) décide laquelle utiliser selon
l'option --source.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np
import requests

from config import (
    EUROSTAT_DEPUIS,
    EUROSTAT_NACE,
    EUROSTAT_PARAMS_FIXES,
    EUROSTAT_URL,
    HTTP_HEADERS,
    HTTP_TIMEOUT,
    MATERIAUX,
    MATERIAUX_CHOC,
    SEED_DEMO,
)

log = logging.getLogger("btp_pulse.sources")

# Colonnes normalisées produites par les deux sources.
COLONNES = [
    "date_releve",         # date ISO du relevé (lundi de la semaine)
    "code_materiau",
    "libelle",
    "unite",
    "prix",                # € HT
    "indice_base100",      # prix rapporté au prix de référence
    "source",              # "insee" | "demo"
    "horodatage_ingestion",
]

_PRIX_REF = {m["code"]: m for m in MATERIAUX}


# ==========================================================================
# 1. Source réelle : Eurostat
# ==========================================================================
def _parse_jsonstat(payload: dict) -> list[tuple[date, float]]:
    """Extrait les couples (date, indice) d'une réponse JSON-stat Eurostat.

    Comme on filtre sur une seule branche / un seul pays / une seule
    unité, la seule dimension qui varie est le temps. `value` est un
    dictionnaire {position -> indice} ; on relie chaque position à son
    libellé de période via `dimension.time.category.index`.
    """
    time_index: dict[str, int] = payload["dimension"]["time"]["category"]["index"]
    position_vers_periode = {pos: periode for periode, pos in time_index.items()}

    points: list[tuple[date, float]] = []
    for position_str, indice in payload.get("value", {}).items():
        if not isinstance(indice, (int, float)):
            continue
        periode = position_vers_periode.get(int(position_str))
        if not periode:
            continue
        # périodes mensuelles "AAAA-MM" -> 1er du mois
        d = datetime.strptime(periode, "%Y-%m").date()
        points.append((d, float(indice)))
    return sorted(points)


def fetch_eurostat(session: requests.Session | None = None,
                   depuis: str = EUROSTAT_DEPUIS) -> list[dict]:
    """Récupère l'indice de prix Eurostat de chaque matériau.

    Une requête HTTP par branche NACE distincte (mise en cache pour les
    matériaux qui partagent une branche). Lève une exception si rien
    n'a pu être récupéré -> le scraper bascule alors sur la démo.
    """
    session = session or requests.Session()
    horodatage = datetime.now().isoformat(timespec="seconds")
    cache_par_nace: dict[str, list[tuple[date, float]]] = {}
    releves: list[dict] = []

    for mat in MATERIAUX:
        code = mat["code"]
        nace = EUROSTAT_NACE.get(code)
        if not nace:
            continue

        if nace not in cache_par_nace:
            params = {**EUROSTAT_PARAMS_FIXES, "nace_r2": nace,
                      "sinceTimePeriod": depuis}
            log.info("Eurostat : téléchargement branche %s (%s)", nace, code)
            reponse = session.get(EUROSTAT_URL, params=params,
                                  headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            reponse.raise_for_status()
            cache_par_nace[nace] = _parse_jsonstat(reponse.json())

        points = cache_par_nace[nace]
        if not points:
            log.warning("Eurostat : branche %s sans donnée, matériau %s ignoré",
                        nace, code)
            continue

        # Conversion indice -> prix € : on rebase la série pour que
        # l'indice le plus récent corresponde au prix de référence
        # (= « prix marché actuel »).
        indice_recent = points[-1][1]
        decimales = 2 if mat["prix_ref"] < 50 else (1 if mat["prix_ref"] < 500 else 0)
        for d, indice in points:
            prix = round(mat["prix_ref"] * indice / indice_recent, decimales)
            releves.append(
                {
                    "date_releve": d.isoformat(),
                    "code_materiau": code,
                    "libelle": mat["libelle"],
                    "unite": mat["unite"],
                    "prix": prix,
                    "indice_base100": round(indice / points[0][1] * 100, 2),
                    "source": "eurostat",
                    "horodatage_ingestion": horodatage,
                }
            )

    if not releves:
        raise RuntimeError("Aucune série Eurostat exploitable")
    log.info("Eurostat : %d relevés récupérés (%d branches)",
             len(releves), len(cache_par_nace))
    return releves


# ==========================================================================
# 2. Source de démonstration (hors-ligne, reproductible)
# ==========================================================================
def _lundi_de_la_semaine(d: date) -> date:
    return d - timedelta(days=d.weekday())


def generer_demo(semaines: int, seed: int = SEED_DEMO,
                 fin: date | None = None) -> list[dict]:
    """Génère `semaines` relevés hebdomadaires par matériau.

    Modèle : marche aléatoire géométrique (rendements log normaux) avec
      - une légère dérive haussière (~2 %/an) ;
      - une volatilité propre à chaque matériau (cf. config) ;
      - un choc d'approvisionnement injecté pour certains matériaux
        (flambée puis reflux partiel), pour rendre l'historique
        crédible et donner « du grain » aux Modules 6 et 7.
    """
    rng = np.random.default_rng(seed)
    fin = _lundi_de_la_semaine(fin or date.today())
    dates = [fin - timedelta(weeks=(semaines - 1 - i)) for i in range(semaines)]
    horodatage = datetime.now().isoformat(timespec="seconds")

    derive_hebdo = 0.02 / 52.0
    releves: list[dict] = []

    for mat in MATERIAUX:
        vol = mat["volatilite"]
        rendements = rng.normal(loc=derive_hebdo, scale=vol, size=semaines)

        trajectoire = mat["prix_ref"] * np.exp(np.cumsum(rendements))

        # Choc d'approvisionnement : flambée type 2021-2022 (montée franche
        # puis reflux partiel). On l'applique en multiplicatif sur la
        # trajectoire : bosse gaussienne culminant à +35 %, centrée aux
        # deux tiers de l'historique.
        if mat["code"] in MATERIAUX_CHOC:
            idx = np.arange(semaines)
            centre = semaines * 0.62
            largeur = max(5.0, semaines * 0.10)
            bosse = np.exp(-0.5 * ((idx - centre) / largeur) ** 2)
            trajectoire = trajectoire * (1.0 + 0.35 * bosse)

        decimales = 2 if mat["prix_ref"] < 50 else (1 if mat["prix_ref"] < 500 else 0)
        for d, prix in zip(dates, trajectoire):
            prix = round(float(prix), decimales)
            releves.append(
                {
                    "date_releve": d.isoformat(),
                    "code_materiau": mat["code"],
                    "libelle": mat["libelle"],
                    "unite": mat["unite"],
                    "prix": prix,
                    "indice_base100": round(prix / mat["prix_ref"] * 100, 2),
                    "source": "demo",
                    "horodatage_ingestion": horodatage,
                }
            )

    log.info("Démo : %d relevés générés (%d matériaux x %d semaines)",
             len(releves), len(MATERIAUX), semaines)
    return releves
