"""Sources de données pour le scraping des appels d'offres — BTP Pulse.

    fetch_boamp(...)     -> récupère les avis de marchés publics réels
                            via l'API open data du BOAMP.
    generer_demo_ao(...) -> jeu d'appels d'offres fictifs mais réalistes,
                            hors-ligne et reproductible.

Toutes deux renvoient des dictionnaires au format COLONNES_AO.
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import date, datetime, timedelta

import requests

from config import (
    BOAMP_OFFSET_MAX,
    BOAMP_PAGE,
    BOAMP_TYPE_MARCHE,
    BOAMP_URL,
    HTTP_HEADERS,
    HTTP_TIMEOUT,
    MOTS_CLES_BTP,
    SEED_DEMO,
)

log = logging.getLogger("btp_pulse.sources_ao")

COLONNES_AO = [
    "id_source",             # identifiant BOAMP (idweb)
    "objet",                 # description du marché
    "acheteur",              # organisme acheteur
    "departements",          # codes département, séparés par des virgules
    "date_parution",
    "date_limite_reponse",
    "type_marche",           # TRAVAUX / SERVICES / FOURNITURES
    "categorie",             # descripteur BOAMP (ex. « Voirie et réseaux divers »)
    "mots_cles_trouves",     # mots-clés BTP repérés dans l'objet
    "score_pertinence",      # entier : plus c'est haut, plus c'est pertinent
    "url_avis",
    "source",                # "boamp" | "demo"
    "horodatage_ingestion",
]


# --------------------------------------------------------------------------
# Utilitaires texte
# --------------------------------------------------------------------------
def _sans_accents(texte: str) -> str:
    """minuscule + suppression des accents, pour une recherche tolérante."""
    texte = (texte or "").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae")
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


_MOTS_CLES_NORM = [(_sans_accents(m), m) for m in MOTS_CLES_BTP]


def _dept_boamp(code: str) -> str:
    """Normalise un code département vers le format BOAMP (sans zéro initial)."""
    code = code.strip().upper()
    if len(code) == 2 and code[0] == "0" and code[1].isdigit():
        return code[1]
    return code


def analyser_pertinence(objet: str, categorie: str = "") -> tuple[list[str], int]:
    """Repère les mots-clés BTP et calcule un score de pertinence.

    Score = nombre de mots-clés distincts trouvés dans l'objet
            + 1 si un mot-clé apparaît aussi dans la catégorie BOAMP.
    """
    champ = _sans_accents(f"{objet} {categorie}")
    trouves = sorted({original for norm, original in _MOTS_CLES_NORM if norm in champ})
    score = len(trouves)
    cat_norm = _sans_accents(categorie)
    if any(norm in cat_norm for norm, _ in _MOTS_CLES_NORM):
        score += 1
    return trouves, score


# --------------------------------------------------------------------------
# 1. Source réelle : BOAMP (open data)
# --------------------------------------------------------------------------
def _normaliser_record_boamp(rec: dict, horodatage: str) -> dict:
    objet = rec.get("objet") or ""
    categories = rec.get("descripteur_libelle") or []
    categorie = ", ".join(categories) if isinstance(categories, list) else str(categories)
    type_marche = rec.get("type_marche") or []
    type_marche = type_marche[0] if isinstance(type_marche, list) and type_marche else (type_marche or "")
    departements = rec.get("code_departement") or []
    departements = ",".join(map(str, departements)) if isinstance(departements, list) else str(departements)

    mots_cles, score = analyser_pertinence(objet, categorie)

    return {
        "id_source": rec.get("idweb") or rec.get("id"),
        "objet": objet.strip(),
        "acheteur": (rec.get("nomacheteur") or "").strip(),
        "departements": departements,
        "date_parution": rec.get("dateparution"),
        "date_limite_reponse": (rec.get("datelimitereponse") or "")[:10] or None,
        "type_marche": type_marche,
        "categorie": categorie,
        "mots_cles_trouves": ", ".join(mots_cles),
        "score_pertinence": score,
        "url_avis": rec.get("url_avis"),
        "source": "boamp",
        "horodatage_ingestion": horodatage,
    }


def fetch_boamp(jours: int, departements: list[str] | None = None,
                tous_types: bool = False,
                session: requests.Session | None = None) -> list[dict]:
    """Récupère les avis BOAMP parus dans les `jours` derniers jours.

    - par défaut, on ne garde que les marchés de travaux
      (`type_marche = TRAVAUX`) ;
    - avec `tous_types=True`, on récupère tous les types et on filtrera
      ensuite sur les mots-clés BTP (fait par le scraper) ;
    - `departements` : liste de codes INSEE pour restreindre la zone.

    Lève une exception si l'API est injoignable -> bascule sur la démo.
    """
    session = session or requests.Session()
    horodatage = datetime.now().isoformat(timespec="seconds")
    depuis = (date.today() - timedelta(days=jours)).isoformat()

    clauses = [f'dateparution >= "{depuis}"']
    if not tous_types:
        clauses.append(f'type_marche = "{BOAMP_TYPE_MARCHE}"')
    if departements:
        # Le BOAMP stocke les départements SANS zéro initial ("1" et non "01").
        codes = [_dept_boamp(d) for d in departements]
        ou_dept = " or ".join(f'code_departement = "{c}"' for c in codes)
        clauses.append(f"({ou_dept})")
    where = " and ".join(clauses)

    records: list[dict] = []
    offset = 0
    while offset <= BOAMP_OFFSET_MAX:
        params = {
            "where": where,
            "order_by": "dateparution desc",
            "limit": BOAMP_PAGE,
            "offset": offset,
        }
        log.info("BOAMP : requête offset=%d", offset)
        reponse = session.get(BOAMP_URL, params=params, headers=HTTP_HEADERS,
                              timeout=HTTP_TIMEOUT)
        reponse.raise_for_status()
        page = reponse.json()
        lot = page.get("results", [])
        if not lot:
            break
        records.extend(_normaliser_record_boamp(r, horodatage) for r in lot)
        if len(lot) < BOAMP_PAGE:
            break
        offset += BOAMP_PAGE

    if not records:
        raise RuntimeError("BOAMP : aucune annonce récupérée")
    log.info("BOAMP : %d annonces récupérées", len(records))
    return records


# --------------------------------------------------------------------------
# 2. Source de démonstration (hors-ligne)
# --------------------------------------------------------------------------
_MODELES_DEMO = [
    ("Construction d'un groupe scolaire — lot gros œuvre / maçonnerie", "Commune de Saint-Genis", "69", "TRAVAUX", "Bâtiment"),
    ("Réhabilitation thermique de 42 logements sociaux — isolation et menuiserie", "OPH Grand Est", "67", "TRAVAUX", "Bâtiment"),
    ("Travaux de voirie et réseaux divers (VRD) — ZAC des Coteaux", "Métropole de Lyon", "69", "TRAVAUX", "Voirie et réseaux divers"),
    ("Charpente et couverture de la halle des sports", "Communauté de communes du Val", "38", "TRAVAUX", "Bâtiment"),
    ("Assainissement — extension du réseau d'eaux usées", "Syndicat des eaux", "01", "TRAVAUX", "Voirie et réseaux divers"),
    ("Fourniture de mobilier de bureau", "Conseil départemental", "75", "FOURNITURES", "Fournitures diverses"),
    ("Démolition d'un ancien bâtiment industriel et désamiantage", "EPF Île-de-France", "93", "TRAVAUX", "Bâtiment"),
    ("Rénovation de la toiture-terrasse et étanchéité du centre technique", "Ville de Bourg", "01", "TRAVAUX", "Bâtiment"),
    ("Mission de maîtrise d'œuvre pour la construction d'une médiathèque", "Commune de Meximieux", "01", "SERVICES", "Prestations intellectuelles"),
    ("Terrassement et gros œuvre — extension d'un EHPAD", "CCAS de Nantua", "01", "TRAVAUX", "Bâtiment"),
]


def generer_demo_ao(jours: int, seed: int = SEED_DEMO) -> list[dict]:
    """Génère des appels d'offres fictifs répartis sur `jours` jours."""
    import random

    rng = random.Random(seed)
    horodatage = datetime.now().isoformat(timespec="seconds")
    annonces: list[dict] = []

    for i, (objet, acheteur, dept, type_marche, categorie) in enumerate(_MODELES_DEMO):
        parution = date.today() - timedelta(days=rng.randint(0, max(1, jours - 1)))
        limite = parution + timedelta(days=rng.randint(21, 45))
        mots_cles, score = analyser_pertinence(objet, categorie)
        annonces.append({
            "id_source": f"DEMO-{parution:%Y%m%d}-{i:02d}",
            "objet": objet,
            "acheteur": acheteur,
            "departements": dept,
            "date_parution": parution.isoformat(),
            "date_limite_reponse": limite.isoformat(),
            "type_marche": type_marche,
            "categorie": categorie,
            "mots_cles_trouves": ", ".join(mots_cles),
            "score_pertinence": score,
            "url_avis": "https://www.boamp.fr/  (donnée de démonstration)",
            "source": "demo",
            "horodatage_ingestion": horodatage,
        })

    log.info("Démo : %d appels d'offres générés", len(annonces))
    return annonces
