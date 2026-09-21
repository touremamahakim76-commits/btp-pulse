"""Tests du Module 6 — pytest analytics/ -v (aucune base requise)."""
from __future__ import annotations

from datetime import date, timedelta

from tests_statistiques import calculer_test_variation


def _serie(jours: int, valeur_fn, aujourdhui: date):
    dates = [aujourdhui - timedelta(days=jours - i) for i in range(jours)]
    return dates, [valeur_fn(i) for i in range(jours)]


def test_variation_significative_detectee():
    aujourdhui = date(2026, 9, 1)
    dates, prix = _serie(200, lambda i: 100.0, aujourdhui)
    # cassure nette sur les 30 derniers jours : +50 %
    for i, d in enumerate(dates):
        if d > aujourdhui - timedelta(days=30):
            prix[i] = 150.0

    res = calculer_test_variation(dates, prix, jours_recents=30, jours_reference=150,
                                  aujourdhui=aujourdhui)
    assert res is not None
    assert res["significatif"] is True
    assert res["variation_pct"] > 40


def test_bruit_non_significatif():
    import random
    rng = random.Random(0)
    aujourdhui = date(2026, 9, 1)
    dates, prix = _serie(200, lambda i: 100.0 + rng.uniform(-1, 1), aujourdhui)

    res = calculer_test_variation(dates, prix, jours_recents=30, jours_reference=150,
                                  aujourdhui=aujourdhui)
    assert res is not None
    assert res["significatif"] is False


def test_historique_insuffisant_renvoie_none():
    aujourdhui = date(2026, 9, 1)
    dates = [aujourdhui - timedelta(days=5)]
    prix = [100.0]
    assert calculer_test_variation(dates, prix, aujourdhui=aujourdhui) is None
