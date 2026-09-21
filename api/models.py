"""Module 9 — Schémas Pydantic de l'API (BTP Pulse).

Documentent automatiquement le format des réponses dans Swagger
(/docs) : chaque champ, son type, et sa description apparaissent dans
la documentation générée par FastAPI sans rien écrire de plus.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PrixActuel(BaseModel):
    code_materiau: str
    libelle: str
    unite: str
    date_releve: date
    prix: float = Field(description="Dernier prix connu, € HT")
    indice_base100: Optional[float] = None
    source: str


class PointHistorique(BaseModel):
    date_releve: date
    prix: float


class Prediction(BaseModel):
    code_materiau: str
    horizon_jours: int
    prix_actuel: float
    prix_predit: float
    variation_pct_predite: Optional[float]
    modele: str
    mae_validation: Optional[float]
    date_prediction: str


class AppelOffre(BaseModel):
    id_source: str
    objet: str
    acheteur: Optional[str]
    departements: Optional[str]
    date_parution: Optional[date]
    date_limite_reponse: Optional[date]
    type_marche: Optional[str]
    score_pertinence: int
    url_avis: Optional[str]


class ResultatTestStatistique(BaseModel):
    code_materiau: str
    date_test: str
    variation_pct: Optional[float]
    p_value: float
    seuil_alpha: float
    significatif: bool


class Devis(BaseModel):
    id_devis: str
    date_devis: date
    client: str
    type_chantier: str
    departement: Optional[str]
    surface_m2: Optional[float]
    montant_ht: float
    statut: str
    marge_estimee_pct: Optional[float]


class QuestionChatbot(BaseModel):
    question: str = Field(min_length=3, examples=["Quels devis avons-nous perdus à cause du prix de l'acier ?"])
    top_k: int = Field(default=4, ge=1, le=10)


class ReponseChatbot(BaseModel):
    reponse: str
    sources: list[str]
    generation_effectuee: bool
