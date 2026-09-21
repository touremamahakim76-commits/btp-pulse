"""Tests du Module 13 — pytest bot/ -v (aucun réseau requis)."""
from __future__ import annotations

import bot_config
from telegram_alerte import envoyer_message, formater_message_ao, formater_message_prix


def test_formater_message_prix_vide():
    assert formater_message_prix([]) is None


def test_formater_message_prix_contenu():
    msg = formater_message_prix([
        {"code_materiau": "ACIER_T", "variation_pct": 8.6, "p_value": 0.00001},
        {"code_materiau": "CUIVRE_T", "variation_pct": -3.2, "p_value": 0.02},
    ])
    assert "ACIER_T" in msg and "+8.6%" in msg
    assert "CUIVRE_T" in msg and "-3.2%" in msg


def test_formater_message_ao_contenu():
    msg = formater_message_ao([
        {"objet": "Travaux de maçonnerie", "departements": "69",
         "date_limite_reponse": "2026-10-01", "score_pertinence": 7},
    ])
    assert "Travaux de maçonnerie" in msg
    assert "[7]" in msg


def test_formater_message_ao_plafonne_le_nombre_de_lignes():
    annonces = [
        {"objet": f"Chantier {i}", "departements": "01",
         "date_limite_reponse": "2026-10-01", "score_pertinence": 6}
        for i in range(25)
    ]
    msg = formater_message_ao(annonces)
    assert msg.count("•") == 10
    assert "15 autre" in msg


def test_envoyer_message_dry_run_sans_token(monkeypatch, capsys):
    monkeypatch.setattr(bot_config, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(bot_config, "TELEGRAM_CHAT_ID", None)

    envoye = envoyer_message("test d'alerte")
    assert envoye is False
    assert "dry-run" in capsys.readouterr().out
