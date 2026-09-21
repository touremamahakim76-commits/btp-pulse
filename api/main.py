"""Module 9 — API FastAPI (BTP Pulse).

Expose en REST les résultats des Modules 1 à 8 : prix actuels et
prédits, appels d'offres filtrés, résultats des tests statistiques,
historique des devis, et le chatbot RAG. Documentation Swagger
automatique sur /docs.

Lancer :
  uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import db
from models import (
    AppelOffre, Devis, PointHistorique, Prediction, PrixActuel,
    QuestionChatbot, ReponseChatbot, ResultatTestStatistique,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rag"))

app = FastAPI(
    title="BTP Pulse API",
    description="Prix matériaux, appels d'offres, prédictions et chatbot RAG "
               "pour une entreprise du BTP.",
    version="1.0.0",
)

# Le dashboard client (Module 11) tourne sur une autre origine (Vite) :
# CORS ouvert ici par simplicité de démo, à restreindre en production.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health", tags=["technique"])
def health():
    try:
        db.requete("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(503, f"base indisponible : {exc}")


# --------------------------------------------------------------------------
# Prix des matériaux (Modules 1, 3, 7)
# --------------------------------------------------------------------------
@app.get("/prix/actuels", response_model=list[PrixActuel], tags=["prix"])
def prix_actuels():
    """Dernier prix connu de chaque matériau."""
    return db.requete("SELECT * FROM v_dernier_prix_materiau ORDER BY code_materiau")


@app.get("/prix/{code_materiau}/historique", response_model=list[PointHistorique], tags=["prix"])
def prix_historique(code_materiau: str, jours: int = Query(730, ge=1, le=3650)):
    """Historique de prix d'un matériau sur les `jours` derniers jours."""
    lignes = db.requete(
        "SELECT date_releve, prix FROM materiaux_prix "
        "WHERE code_materiau = %s AND date_releve >= current_date - %s::int "
        "ORDER BY date_releve",
        (code_materiau, jours),
    )
    if not lignes:
        raise HTTPException(404, f"aucun historique pour '{code_materiau}'")
    return lignes


@app.get("/prix/{code_materiau}/prediction", response_model=Prediction, tags=["prix"])
def prix_prediction(code_materiau: str):
    """Dernière prédiction de prix à horizon (Module 7)."""
    lignes = db.requete(
        "SELECT code_materiau, horizon_jours, prix_actuel, prix_predit, "
        "variation_pct_predite, modele, mae_validation, "
        "date_prediction::text FROM predictions_prix "
        "WHERE code_materiau = %s ORDER BY date_prediction DESC LIMIT 1",
        (code_materiau,),
    )
    if not lignes:
        raise HTTPException(404, f"aucune prédiction pour '{code_materiau}' "
                                 "(lance ml/entrainement.py puis ml/predire.py)")
    return lignes[0]


# --------------------------------------------------------------------------
# Appels d'offres (Modules 2, 3)
# --------------------------------------------------------------------------
@app.get("/appels-offres", response_model=list[AppelOffre], tags=["appels-offres"])
def appels_offres(
    score_min: int = Query(0, ge=0, description="score de pertinence minimal"),
    departement: str | None = Query(None, description="code département, ex. 69"),
    ouverts_uniquement: bool = Query(True, description="date limite de réponse non dépassée"),
    limite: int = Query(50, ge=1, le=500),
):
    conditions = ["score_pertinence >= %s"]
    params: list = [score_min]
    if departement:
        conditions.append("departements LIKE %s")
        params.append(f"%{departement}%")
    if ouverts_uniquement:
        conditions.append("(date_limite_reponse IS NULL OR date_limite_reponse >= current_date)")
    params.append(limite)

    return db.requete(
        f"SELECT id_source, objet, acheteur, departements, date_parution, "
        f"date_limite_reponse, type_marche, score_pertinence, url_avis "
        f"FROM appels_offres WHERE {' AND '.join(conditions)} "
        f"ORDER BY score_pertinence DESC, date_parution DESC LIMIT %s",
        tuple(params),
    )


# --------------------------------------------------------------------------
# Tests statistiques (Module 6)
# --------------------------------------------------------------------------
@app.get("/tests-statistiques", response_model=list[ResultatTestStatistique], tags=["statistiques"])
def tests_statistiques(significatifs_uniquement: bool = False):
    """Dernier résultat de test de significativité par matériau."""
    condition = "WHERE significatif" if significatifs_uniquement else ""
    return db.requete(
        f"SELECT DISTINCT ON (code_materiau) code_materiau, date_test::text, "
        f"variation_pct, p_value, seuil_alpha, significatif "
        f"FROM resultats_tests_statistiques {condition} "
        f"ORDER BY code_materiau, date_test DESC"
    )


# --------------------------------------------------------------------------
# Devis (Module 3)
# --------------------------------------------------------------------------
@app.get("/devis", response_model=list[Devis], tags=["devis"])
def devis(
    statut: str | None = Query(None, pattern="^(gagné|perdu|en cours)$"),
    type_chantier: str | None = None,
    limite: int = Query(50, ge=1, le=500),
):
    conditions, params = ["1=1"], []
    if statut:
        conditions.append("statut = %s")
        params.append(statut)
    if type_chantier:
        conditions.append("type_chantier = %s")
        params.append(type_chantier)
    params.append(limite)

    return db.requete(
        f"SELECT id_devis, date_devis, client, type_chantier, departement, "
        f"surface_m2, montant_ht, statut, marge_estimee_pct FROM devis_historique "
        f"WHERE {' AND '.join(conditions)} ORDER BY date_devis DESC LIMIT %s",
        tuple(params),
    )


# --------------------------------------------------------------------------
# Chatbot RAG (Module 8)
# --------------------------------------------------------------------------
@app.post("/chatbot", response_model=ReponseChatbot, tags=["chatbot"])
def chatbot(question: QuestionChatbot):
    try:
        import chatbot as rag_chatbot
    except Exception as exc:
        raise HTTPException(500, f"module RAG indisponible : {exc}")

    try:
        resultat = rag_chatbot.repondre(question.question, question.top_k)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))

    return {
        "reponse": resultat["reponse"],
        "sources": [s["id"] for s in resultat["sources"]],
        "generation_effectuee": resultat["generation_effectuee"],
    }
