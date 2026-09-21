"""Tests du Module 8 — pytest rag/ -v

Utilise un client ChromaDB EPHÉMÈRE (en mémoire, isolé du dossier
chroma_data/ réel) : pas besoin de PostgreSQL ni de clé Anthropic pour
tester le retrieval. Le premier lancement télécharge le petit modèle
d'embeddings MiniLM (~80 Mo, mis en cache ensuite).
"""
from __future__ import annotations

import chromadb
import pytest


@pytest.fixture
def collection_test():
    client = chromadb.EphemeralClient()
    col = client.get_or_create_collection("devis_test")
    col.add(
        documents=[
            "Devis DV-1 — Maison individuelle pour M. Dupont. Tension sur le "
            "prix de l'acier au moment du chiffrage. Offre retenue.",
            "Devis DV-2 — VRD et assainissement pour la commune de Meximieux. "
            "Écarté : offre 6% au-dessus du moins-disant.",
            "Devis DV-3 — Réhabilitation lourde, isolation et menuiserie. "
            "Perdu face à un concurrent local.",
        ],
        metadatas=[{"statut": "gagné"}, {"statut": "perdu"}, {"statut": "perdu"}],
        ids=["DV-1", "DV-2", "DV-3"],
    )
    return col


def test_recherche_semantique_retrouve_le_bon_devis(collection_test):
    res = collection_test.query(query_texts=["variation du cours de l'acier"], n_results=1)
    assert res["ids"][0][0] == "DV-1"


def test_recherche_semantique_devis_perdus(collection_test):
    # MiniLM (petit modèle d'embeddings par défaut de Chroma) est surtout
    # entraîné en anglais : on garde une requête avec un recouvrement
    # lexical suffisant pour un test fiable, plutôt qu'une paraphrase
    # complète qui dépendrait de la qualité sémantique fine en français.
    res = collection_test.query(
        query_texts=["un devis perdu face à un concurrent local"],
        n_results=1,
    )
    assert res["ids"][0][0] == "DV-3"


def test_repondre_sans_cle_api_renvoie_le_contexte(monkeypatch, tmp_path):
    import rag_config
    import chatbot

    monkeypatch.setattr(rag_config, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(rag_config, "CHROMA_DIR", tmp_path)

    client = chromadb.PersistentClient(path=str(tmp_path))
    col = client.get_or_create_collection(rag_config.COLLECTION)
    col.add(documents=["Devis DV-9 — test isolant."], ids=["DV-9"],
            metadatas=[{"statut": "gagné"}])

    resultat = chatbot.repondre("test isolant", top_k=1)
    assert resultat["generation_effectuee"] is False
    assert "DV-9" in resultat["reponse"]
    assert len(resultat["sources"]) == 1
