"""Module 6 — Tests statistiques de significativité (BTP Pulse).

Question métier : le prix d'un matériau vient de bouger — est-ce un
vrai mouvement de marché, ou du bruit statistique ? On ne veut pas
déclencher une alerte (Module 13) ou faire confiance à une prédiction
(Module 7) sur une variation qui n'est pas significative.

Méthode : test t de Welch (variances inégales) comparant la moyenne
des prix de la période récente à celle de la période de référence
précédente. H0 : les deux périodes ont la même moyenne. On rejette H0
(variation jugée significative) si p_value < seuil_alpha.

Fenêtres par défaut : 150 jours (récent) vs 365 jours (référence).
Les séries Eurostat sont mensuelles avec ~2 mois de retard de
publication ; des fenêtres plus courtes (ex. 30/90 jours, plus
adaptées à une source quotidienne) laisseraient trop peu de points
pour un test valide (minimum 2 par échantillon).

`calculer_test_variation` est une fonction PURE (listes de dates/prix
en entrée) — testable sans base de données. `tester_materiau_depuis_db`
et `executer_tous` font l'interface avec PostgreSQL.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))


# =========================================================================
# Fonction pure — testable sans base de données
# =========================================================================
def calculer_test_variation(
    dates: list[date],
    prix: list[float],
    jours_recents: int = 150,
    jours_reference: int = 365,
    alpha: float = 0.05,
    aujourdhui: date | None = None,
) -> dict | None:
    """Compare la période récente à la période de référence qui la précède.

    Renvoie None si l'une des deux périodes contient moins de 2 points
    (le test n'a pas de sens statistique en dessous).
    """
    aujourdhui = aujourdhui or date.today()
    debut_recent = aujourdhui - timedelta(days=jours_recents)
    debut_reference = debut_recent - timedelta(days=jours_reference)

    echantillon_recent = [p for d, p in zip(dates, prix) if d > debut_recent]
    echantillon_reference = [
        p for d, p in zip(dates, prix) if debut_reference < d <= debut_recent
    ]

    if len(echantillon_recent) < 2 or len(echantillon_reference) < 2:
        return None

    t_stat, p_value = stats.ttest_ind(
        echantillon_recent, echantillon_reference, equal_var=False
    )
    moyenne_recente = sum(echantillon_recent) / len(echantillon_recent)
    moyenne_reference = sum(echantillon_reference) / len(echantillon_reference)
    variation_pct = (
        100 * (moyenne_recente - moyenne_reference) / moyenne_reference
        if moyenne_reference else None
    )

    return {
        "jours_recents": jours_recents,
        "jours_reference": jours_reference,
        "n_recents": len(echantillon_recent),
        "n_reference": len(echantillon_reference),
        "moyenne_recente": round(moyenne_recente, 4),
        "moyenne_reference": round(moyenne_reference, 4),
        "variation_pct": round(variation_pct, 2) if variation_pct is not None else None,
        "t_stat": round(float(t_stat), 4),
        "p_value": round(float(p_value), 8),
        "seuil_alpha": alpha,
        "significatif": bool(p_value < alpha),
    }


# =========================================================================
# Interface PostgreSQL
# =========================================================================
def _lire_historique(conn, code_materiau: str) -> tuple[list[date], list[float]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT date_releve, prix FROM materiaux_prix "
            "WHERE code_materiau = %s ORDER BY date_releve",
            (code_materiau,),
        )
        lignes = cur.fetchall()
    return [r[0] for r in lignes], [float(r[1]) for r in lignes]


def tester_materiau_depuis_db(
    conn, code_materiau: str, jours_recents: int = 150,
    jours_reference: int = 365, alpha: float = 0.05,
) -> dict | None:
    dates, prix = _lire_historique(conn, code_materiau)
    resultat = calculer_test_variation(dates, prix, jours_recents, jours_reference, alpha)
    if resultat:
        resultat["code_materiau"] = code_materiau
    return resultat


def enregistrer_resultat(conn, resultat: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO resultats_tests_statistiques
                (code_materiau, jours_recents, jours_reference, n_recents,
                 n_reference, moyenne_recente, moyenne_reference, variation_pct,
                 t_stat, p_value, seuil_alpha, significatif)
            VALUES (%(code_materiau)s, %(jours_recents)s, %(jours_reference)s,
                    %(n_recents)s, %(n_reference)s, %(moyenne_recente)s,
                    %(moyenne_reference)s, %(variation_pct)s, %(t_stat)s,
                    %(p_value)s, %(seuil_alpha)s, %(significatif)s)
            """,
            resultat,
        )
    conn.commit()


def executer_tous(conn, jours_recents: int = 150, jours_reference: int = 365,
                  alpha: float = 0.05) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM materiaux ORDER BY code")
        codes = [r[0] for r in cur.fetchall()]

    resultats = []
    for code in codes:
        r = tester_materiau_depuis_db(conn, code, jours_recents, jours_reference, alpha)
        if r:
            enregistrer_resultat(conn, r)
            resultats.append(r)
    return resultats
