"""Configuration du chatbot RAG — Module 8."""
from __future__ import annotations

import os
from pathlib import Path

_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for _ligne in _env_path.read_text(encoding="utf-8").splitlines():
        _ligne = _ligne.strip()
        if _ligne and not _ligne.startswith("#") and "=" in _ligne:
            _cle, _, _val = _ligne.partition("=")
            os.environ.setdefault(_cle.strip(), _val.strip())

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

CHROMA_DIR = Path(__file__).resolve().parent / "chroma_data"
COLLECTION = "devis_historique"
