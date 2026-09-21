"""Module 8 — Chatbot RAG sur l'historique de devis (BTP Pulse).

Retrieval-Augmented Generation :
  1. RETRIEVAL : on cherche dans ChromaDB (indexer.py) les devis les
     plus proches sémantiquement de la question.
  2. AUGMENTED : on injecte ces devis dans le prompt, comme contexte.
  3. GENERATION : Claude (API Anthropic) rédige la réponse EN SE
     BASANT UNIQUEMENT sur ce contexte — pas sur sa connaissance
     générale — pour éviter les réponses inventées (hallucination)
     sur des chiffres métier précis.

Si ANTHROPIC_API_KEY n'est pas configurée, la fonction ne plante pas :
elle renvoie le contexte retrouvé (la partie « retrieval » reste
démontrable) avec un message clair au lieu d'appeler l'API.

Usage :
  python chatbot.py "Quels devis avons-nous perdus à cause du prix de l'acier ?"
  python chatbot.py                # mode interactif
"""
from __future__ import annotations

import sys
from pathlib import Path

import chromadb

import rag_config

PROMPT_SYSTEME = """Tu es l'assistant interne de BTP Pulse, spécialisé dans \
l'historique des devis de l'entreprise. Réponds UNIQUEMENT à partir des \
devis fournis en contexte ci-dessous. Si le contexte ne permet pas de \
répondre, dis-le clairement plutôt que d'inventer. Réponds en français, \
de façon concise et professionnelle, et cite les identifiants de devis \
(ex. DV-202503-012) sur lesquels tu t'appuies."""


def _collection():
    client = chromadb.PersistentClient(path=str(rag_config.CHROMA_DIR))
    if rag_config.COLLECTION not in [c.name for c in client.list_collections()]:
        raise RuntimeError(
            "Collection vide : lance d'abord `python indexer.py`."
        )
    return client.get_collection(rag_config.COLLECTION)


def rechercher_contexte(question: str, top_k: int | None = None) -> list[dict]:
    """Étape RETRIEVAL : renvoie les `top_k` devis les plus proches de
    la question, avec leur score de similarité."""
    top_k = top_k or rag_config.RAG_TOP_K
    resultats = _collection().query(query_texts=[question], n_results=top_k)
    return [
        {"id": id_, "document": doc, "metadata": meta, "distance": dist}
        for id_, doc, meta, dist in zip(
            resultats["ids"][0], resultats["documents"][0],
            resultats["metadatas"][0], resultats["distances"][0],
        )
    ]


def repondre(question: str, top_k: int | None = None) -> dict:
    """Pipeline RAG complet. Renvoie toujours le contexte retrouvé ;
    la réponse générée n'est présente que si ANTHROPIC_API_KEY est
    configurée (sinon `reponse` explique pourquoi)."""
    contexte = rechercher_contexte(question, top_k)
    texte_contexte = "\n\n".join(
        f"[{c['id']}] {c['document']}" for c in contexte
    )

    if not rag_config.ANTHROPIC_API_KEY:
        return {
            "reponse": (
                "ANTHROPIC_API_KEY n'est pas configurée : voici le contexte "
                "qui aurait été envoyé au modèle (la recherche sémantique, "
                "elle, fonctionne déjà pleinement) :\n\n" + texte_contexte
            ),
            "sources": contexte,
            "generation_effectuee": False,
        }

    import anthropic
    client = anthropic.Anthropic(api_key=rag_config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=rag_config.ANTHROPIC_MODEL,
        max_tokens=700,
        system=PROMPT_SYSTEME,
        messages=[{
            "role": "user",
            "content": f"Contexte (devis retrouvés) :\n{texte_contexte}\n\n"
                       f"Question : {question}",
        }],
    )
    return {
        "reponse": message.content[0].text,
        "sources": contexte,
        "generation_effectuee": True,
    }


def main(argv: list[str] | None = None) -> int:
    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    argv = argv if argv is not None else sys.argv[1:]

    def _poser(question: str) -> None:
        resultat = repondre(question)
        print(f"\n{resultat['reponse']}\n")
        print("Sources :", ", ".join(s["id"] for s in resultat["sources"]))

    if argv:
        _poser(" ".join(argv))
        return 0

    print("Chatbot RAG — historique de devis BTP Pulse (Ctrl+C pour quitter)\n")
    try:
        while True:
            question = input("Question > ").strip()
            if question:
                _poser(question)
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
