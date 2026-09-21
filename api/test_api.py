"""Tests du Module 9 — pytest api/ -v

Tests d'intégration contre la vraie base PostgreSQL (cohérent avec le
reste du projet : on préfère tester contre le vrai système plutôt que
mocker la base). Nécessite : docker compose -f database/docker-compose.yml up -d
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_prix_actuels():
    r = client.get("/prix/actuels")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 10
    assert {"code_materiau", "prix", "unite"} <= data[0].keys()


def test_prix_historique_materiau_inconnu():
    r = client.get("/prix/CODE_INEXISTANT/historique")
    assert r.status_code == 404


def test_prix_historique_ok():
    r = client.get("/prix/ACIER_T/historique?jours=3650")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_appels_offres_filtre_score():
    r = client.get("/appels-offres?score_min=5&ouverts_uniquement=false&limite=10")
    assert r.status_code == 200
    assert all(a["score_pertinence"] >= 5 for a in r.json())


def test_devis_filtre_statut():
    r = client.get("/devis?statut=gagné&limite=200")
    assert r.status_code == 200
    assert all(d["statut"] == "gagné" for d in r.json())


def test_devis_statut_invalide_rejete():
    r = client.get("/devis?statut=inconnu")
    assert r.status_code == 422  # validation Pydantic (pattern)


def test_chatbot_repond_sans_erreur():
    r = client.post("/chatbot", json={"question": "Quels devis mentionnent l'acier ?", "top_k": 2})
    assert r.status_code == 200
    body = r.json()
    assert "reponse" in body and len(body["sources"]) <= 2
