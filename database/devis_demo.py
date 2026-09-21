"""Génération d'un historique de devis fictifs mais réalistes — Module 3.

Ces devis n'existent pas : ils servent de données de démonstration pour
  - le chatbot RAG (Module 8) — les `commentaire` sont écrits pour ça ;
  - l'endpoint API « historique devis » (Module 9) ;
  - les analyses de taux de réussite et de marge.

Reproductible : même `seed` => mêmes devis.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

COLONNES_DEVIS = [
    "id_devis", "date_devis", "client", "type_chantier", "departement",
    "surface_m2", "montant_ht", "statut", "marge_estimee_pct",
    "principaux_materiaux", "commentaire",
]

CLIENTS = [
    "Mairie de Meximieux", "Communauté de communes de la Plaine de l'Ain",
    "OPH de l'Ain", "SCI Les Terrasses", "Conseil départemental de l'Ain",
    "Rhône Habitat Promotion", "Clinique du Parc", "SDIS 01",
    "Coopérative agricole de Bresse", "Hôtel des Dombes",
    "Syndicat des eaux Veyle-Ain", "EHPAD Les Cèdres", "Lycée du Bugey",
    "Ville de Bourg-en-Bresse", "Foncière Léman", "Grand Lyon Habitat",
]

DEPARTEMENTS = ["01", "01", "01", "69", "69", "38", "73", "74", "71"]

# type de chantier -> (prix moyen € HT au m², dispersion, matériaux clés)
TYPES_CHANTIER: dict[str, tuple[float, float, list[str]]] = {
    "Maison individuelle":       (1650, 0.14, ["béton", "parpaing", "bois", "isolant", "placo"]),
    "Logement collectif":        (1900, 0.12, ["béton", "acier", "isolant", "placo", "PVC"]),
    "Réhabilitation lourde":     (1400, 0.22, ["placo", "isolant", "bois", "menuiserie", "PVC"]),
    "Bâtiment tertiaire":        (1750, 0.15, ["béton", "acier", "verre", "isolant"]),
    "Extension / surélévation":  (2100, 0.18, ["bois", "acier", "isolant", "placo"]),
    "VRD / voirie":              (95,   0.25, ["enrobé", "béton", "PVC"]),
    "Toiture / couverture":      (185,  0.20, ["bois", "isolant", "cuivre"]),
    "Génie civil":               (2600, 0.20, ["béton", "acier"]),
}

# fourchettes de surface (m²) par type
SURFACES: dict[str, tuple[int, int]] = {
    "Maison individuelle":      (90, 240),
    "Logement collectif":       (700, 4200),
    "Réhabilitation lourde":    (300, 2600),
    "Bâtiment tertiaire":       (250, 3200),
    "Extension / surélévation": (40, 180),
    "VRD / voirie":             (600, 9000),
    "Toiture / couverture":     (150, 1800),
    "Génie civil":              (200, 2500),
}

_MODE_CONSULT = [
    "Appel d'offres ouvert.", "Consultation restreinte.",
    "Marché à procédure adaptée (MAPA).", "Demande de devis directe du client.",
    "Marché négocié après appel d'offres infructueux.",
]
# Deux formes d'article par matériau, pour accorder correctement selon
# la préposition qui précède dans le gabarit : "sur le béton" (pas de
# contraction) mais "le prix du béton" (de + le -> du). Un simple
# gabarit "l'{m}" donnait des horreurs comme "indexée sur l'béton" ou
# "prix de le béton".
_ARTICLE = {
    "béton": "le béton", "parpaing": "le parpaing", "bois": "le bois",
    "isolant": "l'isolant", "placo": "le placo", "acier": "l'acier",
    "PVC": "le PVC", "verre": "le verre", "cuivre": "le cuivre",
    "enrobé": "l'enrobé", "menuiserie": "la menuiserie", "zinc": "le zinc",
}
_ARTICLE_DE = {  # forme contractée après "de"
    "béton": "du béton", "parpaing": "du parpaing", "bois": "du bois",
    "isolant": "de l'isolant", "placo": "du placo", "acier": "de l'acier",
    "PVC": "du PVC", "verre": "du verre", "cuivre": "du cuivre",
    "enrobé": "de l'enrobé", "menuiserie": "de la menuiserie", "zinc": "du zinc",
}


def _avec_article(materiau: str) -> str:
    return _ARTICLE.get(materiau, f"le {materiau}")


def _avec_article_de(materiau: str) -> str:
    return _ARTICLE_DE.get(materiau, f"du {materiau}")


_NOTE_MATERIAU = [
    "Forte tension sur le prix {m_de} au moment du chiffrage.",
    "Devis sécurisé par un accord-cadre fournisseur sur {m}.",
    "Délais d'approvisionnement {m_de} annoncés à 8 semaines.",
    "Prix {m_de} revu à la hausse entre l'étude et la remise de l'offre.",
    "Clause de révision de prix indexée sur {m}.",
]
_ISSUE = {
    "gagné": [
        "Offre retenue, mieux-disante sur le critère technique.",
        "Retenu malgré un prix 3 % au-dessus du moins-disant, grâce aux références.",
        "Marché attribué : meilleur délai d'exécution proposé.",
        "Retenu après négociation, remise commerciale de 2 %.",
    ],
    "perdu": [
        "Écarté : offre 6 % au-dessus du moins-disant.",
        "Non retenu, délai d'exécution jugé trop long.",
        "Perdu face à un concurrent local mieux implanté.",
        "Offre non conforme sur un lot, dossier rejeté.",
    ],
    "en cours": [
        "Analyse des offres en cours par le maître d'ouvrage.",
        "Négociation en cours sur le poste gros œuvre.",
        "En attente de la décision de la commission d'appel d'offres.",
    ],
}


def _commentaire(rng: random.Random, type_chantier: str, ville_client: str,
                 surface: float, materiaux: list[str], statut: str) -> str:
    m = rng.choice(materiaux)
    bouts = [
        rng.choice(_MODE_CONSULT),
        f"{type_chantier} de {surface:.0f} m² pour {ville_client}.",
        rng.choice(_NOTE_MATERIAU).format(m=_avec_article(m), m_de=_avec_article_de(m)),
        rng.choice(_ISSUE[statut]),
    ]
    return " ".join(bouts)


def generer_devis(n: int = 120, seed: int = 42,
                  fin: date | None = None) -> list[dict]:
    """Génère `n` devis répartis sur les ~3 dernières années."""
    rng = random.Random(seed)
    fin = fin or date.today()
    types = list(TYPES_CHANTIER)
    devis: list[dict] = []

    for i in range(n):
        type_chantier = rng.choice(types)
        prix_m2, dispersion, materiaux = TYPES_CHANTIER[type_chantier]
        surf_min, surf_max = SURFACES[type_chantier]
        surface = round(rng.uniform(surf_min, surf_max), 1)

        # prix au m² bruité (loi log-normale ~ multiplicatif)
        prix_m2_reel = prix_m2 * rng.lognormvariate(0, dispersion)
        montant = round(surface * prix_m2_reel, 2)

        statut = rng.choices(
            ["gagné", "perdu", "en cours"], weights=[0.42, 0.44, 0.14]
        )[0]
        # marge plus serrée quand on perd (on a sous-coté ou concurrence dure)
        marge = rng.gauss(9 if statut == "gagné" else 6.5, 3)
        marge = round(min(18.0, max(1.0, marge)), 1)

        d = fin - timedelta(days=rng.randint(15, 365 * 3))
        client = rng.choice(CLIENTS)
        principaux = ", ".join(rng.sample(materiaux, k=min(3, len(materiaux))))

        devis.append({
            "id_devis": f"DV-{d:%Y%m}-{i:03d}",
            "date_devis": d.isoformat(),
            "client": client,
            "type_chantier": type_chantier,
            "departement": rng.choice(DEPARTEMENTS),
            "surface_m2": surface,
            "montant_ht": montant,
            "statut": statut,
            "marge_estimee_pct": marge,
            "principaux_materiaux": principaux,
            "commentaire": _commentaire(rng, type_chantier, client, surface,
                                        materiaux, statut),
        })

    devis.sort(key=lambda x: x["date_devis"])
    return devis
