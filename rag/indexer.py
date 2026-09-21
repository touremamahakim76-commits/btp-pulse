"""Module 8 — Indexation des devis dans ChromaDB (BTP Pulse).

Construit (ou reconstruit) une collection vectorielle à partir de
l'historique de devis (Module 3), pour que le chatbot puisse retrouver
les devis pertinents par similarité sémantique (recherche en langage
naturel, pas par mot-clé exact).

Embeddings : fonction par défaut de ChromaDB (MiniLM, tourne en local,
aucune clé API requise — seule la génération de réponse, dans
chatbot.py, appelle l'API Anthropic).

Usage :
  python indexer.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import chromadb
import pandas as pd
import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "database"))
import db_config  # noqa: E402

import rag_config

CSV_SECOURS = Path(__file__).resolve().parent.parent / "ingestion" / "data" / "devis_historique.csv"


def _document(row: pd.Series) -> str:
    """Texte indexé : contexte structuré + commentaire libre, pour que
    la recherche sémantique capte aussi bien 'un devis perdu à cause du
    prix' que 'un chantier de maçonnerie à Bourg-en-Bresse'."""
    return (
        f"Devis {row['id_devis']} du {row['date_devis']} — {row['type_chantier']} "
        f"pour {row['client']} (département {row['departement']}), "
        f"{row['surface_m2']} m², montant {row['montant_ht']} € HT, "
        f"statut : {row['statut']}, marge estimée {row['marge_estimee_pct']} %. "
        f"Matériaux principaux : {row['principaux_materiaux']}. {row['commentaire']}"
    )


def charger_devis() -> pd.DataFrame:
    try:
        from sqlalchemy import create_engine
        moteur = create_engine(db_config.sqlalchemy_url())
        with psycopg2.connect(db_config.dsn()):  # vérifie la connectivité, message clair sinon
            pass
        return pd.read_sql("SELECT * FROM devis_historique", moteur)
    except Exception as exc:
        if not CSV_SECOURS.exists():
            raise RuntimeError(
                "Ni PostgreSQL ni le CSV de secours ne sont disponibles pour "
                f"charger les devis.\n{exc}"
            )
        print(f"(PostgreSQL indisponible, repli sur {CSV_SECOURS.name})")
        return pd.read_csv(CSV_SECOURS)


def indexer(df: pd.DataFrame) -> int:
    client = chromadb.PersistentClient(path=str(rag_config.CHROMA_DIR))
    client.delete_collection(rag_config.COLLECTION) if rag_config.COLLECTION in [
        c.name for c in client.list_collections()
    ] else None
    collection = client.get_or_create_collection(rag_config.COLLECTION)

    documents = [_document(r) for _, r in df.iterrows()]
    metadatas = [
        {
            "id_devis": r["id_devis"], "type_chantier": r["type_chantier"],
            "statut": r["statut"], "departement": str(r["departement"]),
            "montant_ht": float(r["montant_ht"]),
        }
        for _, r in df.iterrows()
    ]
    ids = df["id_devis"].astype(str).tolist()

    # Chroma limite la taille d'un batch d'ajout : on découpe par sécurité.
    taille_lot = 200
    for i in range(0, len(ids), taille_lot):
        collection.add(
            documents=documents[i:i + taille_lot],
            metadatas=metadatas[i:i + taille_lot],
            ids=ids[i:i + taille_lot],
        )
    return len(ids)


def main() -> int:
    for _flux in (sys.stdout, sys.stderr):
        try:
            _flux.reconfigure(encoding="utf-8")
        except Exception:
            pass

    df = charger_devis()
    n = indexer(df)
    print(f"{n} devis indexés dans ChromaDB ({rag_config.CHROMA_DIR})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
