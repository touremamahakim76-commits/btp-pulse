"""Configuration centrale du module d'ingestion — BTP Pulse.

Ce fichier regroupe tout ce qui est « métier » et susceptible de bouger :
  - la liste des matériaux de construction suivis ;
  - les mots-clés du secteur BTP (réutilisés au Module 2 pour filtrer
    les appels d'offres) ;
  - les paramètres des sources de données (INSEE) et du HTTP.

Aucune logique ici : uniquement des constantes, pour qu'on puisse
ajuster le périmètre sans toucher au code du scraper.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Dossiers
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------
# Matériaux suivis
# --------------------------------------------------------------------------
# `prix_ref` = prix indicatif € HT à la date de conception du projet.
# Il sert de base au générateur de données de démo ET de garde-fou
# de cohérence (on rejette une valeur scrappée aberrante, ex. x10).
MATERIAUX: list[dict] = [
    {"code": "BETON_M3",   "libelle": "Béton prêt à l'emploi C25/30",     "unite": "m3",    "prix_ref": 130.0,  "volatilite": 0.004},
    {"code": "ACIER_T",    "libelle": "Acier à béton (ferraillage HA)",   "unite": "tonne", "prix_ref": 950.0,  "volatilite": 0.011},
    {"code": "CIMENT_T",   "libelle": "Ciment CEM II 32,5 R",             "unite": "tonne", "prix_ref": 165.0,  "volatilite": 0.005},
    {"code": "BOIS_M3",    "libelle": "Bois de charpente sapin/épicéa",   "unite": "m3",    "prix_ref": 480.0,  "volatilite": 0.012},
    {"code": "PARPAING_U", "libelle": "Bloc béton creux 20x20x50",        "unite": "unité", "prix_ref": 1.35,   "volatilite": 0.003},
    {"code": "ISOLANT_M2", "libelle": "Laine de verre 100 mm",            "unite": "m2",    "prix_ref": 7.80,   "volatilite": 0.006},
    {"code": "CUIVRE_T",   "libelle": "Tube cuivre (plomberie)",          "unite": "tonne", "prix_ref": 9800.0, "volatilite": 0.014},
    {"code": "PVC_ML",     "libelle": "Tube PVC évacuation Ø100",         "unite": "ml",    "prix_ref": 6.20,   "volatilite": 0.007},
    {"code": "BITUME_T",   "libelle": "Enrobé bitumineux (BBSG)",         "unite": "tonne", "prix_ref": 95.0,   "volatilite": 0.008},
    {"code": "PLACO_M2",   "libelle": "Plaque de plâtre BA13",            "unite": "m2",    "prix_ref": 5.90,   "volatilite": 0.004},
]

# Matériaux ayant subi un « choc d'approvisionnement » dans l'historique
# de démo (flambée type 2021-2022 sur le bois, l'acier, le cuivre).
MATERIAUX_CHOC = {"BOIS_M3", "ACIER_T", "CUIVRE_T"}

# --------------------------------------------------------------------------
# Mots-clés secteur BTP (utilisés au Module 2)
# --------------------------------------------------------------------------
MOTS_CLES_BTP: list[str] = [
    "construction", "bâtiment", "gros œuvre", "second œuvre", "rénovation",
    "réhabilitation", "réfection", "aménagement", "extension", "travaux",
    "voirie", "vrd", "terrassement", "maçonnerie", "charpente", "couverture",
    "étanchéité", "plomberie", "électricité", "isolation", "menuiserie",
    "démolition", "génie civil", "réseaux", "réseau", "assainissement",
    "enrobé", "toiture",
]

# --------------------------------------------------------------------------
# Source réelle : Eurostat — indices de prix à la production dans l'industrie
# --------------------------------------------------------------------------
# Jeu de données `sts_inpp_m` (Producer prices in industry, monthly).
# API REST publique, sans authentification, réponse JSON-stat.
# On récupère l'indice mensuel (base 2021 = 100) de la branche
# industrielle qui produit chaque matériau, pour la France (geo=FR).
EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inpp_m"
)
EUROSTAT_PARAMS_FIXES = {
    "format": "JSON",
    "lang": "EN",
    "geo": "FR",
    "s_adj": "NSA",       # non corrigé des variations saisonnières
    "unit": "I21",        # indice base 2021 = 100
    "indic_bt": "PRC_PRR",  # prix à la production
}
EUROSTAT_DEPUIS = "2019-01"  # début de l'historique demandé à Eurostat

# Code matériau interne -> code de branche NACE Rev. 2 chez Eurostat.
# Plusieurs matériaux partagent une branche (ex. C23 = « autres produits
# minéraux non métalliques » couvre ciment, béton, plâtre : les sous-
# branches C235/C236 sont confidentielles pour la France).
EUROSTAT_NACE: dict[str, str] = {
    "BETON_M3":   "C23",   # autres produits minéraux non métalliques
    "CIMENT_T":   "C23",
    "PARPAING_U": "C23",
    "PLACO_M2":   "C23",
    "ISOLANT_M2": "C231",  # verre et articles en verre
    "ACIER_T":    "C241",  # sidérurgie (fer, acier, ferro-alliages)
    "CUIVRE_T":   "C244",  # métaux non ferreux
    "BOIS_M3":    "C16",   # travail du bois
    "PVC_ML":     "C222",  # produits en plastique
    "BITUME_T":   "C19",   # cokéfaction et raffinage (produits pétroliers)
}

HTTP_HEADERS = {
    "User-Agent": "BTP-Pulse/0.1 (projet portfolio data ; usage non commercial)",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
HTTP_TIMEOUT = 20  # secondes

# --------------------------------------------------------------------------
# Module 2 — Appels d'offres : BOAMP (open data)
# --------------------------------------------------------------------------
# Le BOAMP (Bulletin officiel des annonces de marchés publics) est
# diffusé en open data via une API Opendatasoft « Explore v2.1 ».
# Publique, sans authentification, réponse JSON.
BOAMP_URL = (
    "https://boamp-datadila.opendatasoft.com/api/explore/v2.1"
    "/catalog/datasets/boamp/records"
)
BOAMP_PAGE = 100              # nb max d'enregistrements par requête (limite ODS)
BOAMP_OFFSET_MAX = 9900       # ODS refuse offset + limit > 10000
BOAMP_JOURS_DEFAUT = 30       # profondeur par défaut (jours de parution)
BOAMP_TYPE_MARCHE = "TRAVAUX"  # on cible les marchés de travaux

# Nombre minimal de mots-clés BTP dans l'objet pour retenir une annonce
# quand on n'a PAS filtré sur le type de marché (--tous-types).
SCORE_MIN_PERTINENCE = 1

# --------------------------------------------------------------------------
# Paramètres de l'historique
# --------------------------------------------------------------------------
SEMAINES_HISTORIQUE_DEFAUT = 104  # 2 ans de relevés hebdomadaires
SEED_DEMO = 42                    # reproductibilité des données de démo
