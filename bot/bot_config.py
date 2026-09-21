"""Configuration du bot d'alerte Telegram — Module 13."""
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCORE_MIN_ALERTE = int(os.getenv("SCORE_MIN_ALERTE", "6"))
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
