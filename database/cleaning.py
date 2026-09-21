"""Nettoyage des données avant chargement en base — Module 3.

Fonctions PURES : elles prennent un DataFrame et renvoient
`(df_propre, rapport)`, sans toucher à la base. Elles sont donc
testables sans PostgreSQL (voir test_cleaning.py).

`rapport` est un dict :
    {
      "lignes_entree": int,
      "lignes_sortie": int,
      "retirees": { "raison": nombre_de_lignes, ... }
    }
"""
from __future__ import annotations

import pandas as pd


def _rapport_init(n: int) -> dict:
    return {"lignes_entree": n, "lignes_sortie": n, "retirees": {}}


# =========================================================================
# Prix des matériaux (Module 1)
# =========================================================================
def nettoyer_prix(
    df: pd.DataFrame,
    prix_ref: dict[str, float] | None = None,
    facteur_aberrant: float = 5.0,
) -> tuple[pd.DataFrame, dict]:
    """Nettoie l'historique de prix.

    Étapes : valeurs manquantes -> typage date/prix -> prix > 0 ->
    valeurs aberrantes (hors de [prix_ref / f ; prix_ref * f]) ->
    doublons (date, matériau) en gardant le relevé le plus récent.
    """
    rap = _rapport_init(len(df))
    df = df.copy()

    # 1. colonnes obligatoires
    avant = len(df)
    df = df.dropna(subset=["date_releve", "code_materiau", "prix"])
    rap["retirees"]["valeurs_manquantes"] = avant - len(df)

    # 2. typage
    df["date_releve"] = pd.to_datetime(df["date_releve"], errors="coerce").dt.date
    df["prix"] = pd.to_numeric(df["prix"], errors="coerce")
    avant = len(df)
    df = df.dropna(subset=["date_releve", "prix"])
    rap["retirees"]["date_ou_prix_invalide"] = avant - len(df)

    # 3. prix strictement positif
    avant = len(df)
    df = df[df["prix"] > 0]
    rap["retirees"]["prix_negatif_ou_nul"] = avant - len(df)

    # 4. valeurs aberrantes vs prix de référence
    if prix_ref:
        def _ok(row) -> bool:
            ref = prix_ref.get(row["code_materiau"])
            if not ref:
                return True
            return ref / facteur_aberrant <= row["prix"] <= ref * facteur_aberrant

        avant = len(df)
        df = df[df.apply(_ok, axis=1)]
        rap["retirees"]["valeur_aberrante"] = avant - len(df)

    # 5. doublons (date, matériau) — on garde le plus récemment ingéré
    avant = len(df)
    if "horodatage_ingestion" in df.columns:
        df = df.sort_values("horodatage_ingestion")
    df = df.drop_duplicates(subset=["date_releve", "code_materiau"], keep="last")
    rap["retirees"]["doublon"] = avant - len(df)

    df = df.sort_values(["code_materiau", "date_releve"]).reset_index(drop=True)
    rap["lignes_sortie"] = len(df)
    return df, rap


# =========================================================================
# Appels d'offres (Module 2)
# =========================================================================
def nettoyer_appels_offres(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Nettoie les avis d'appels d'offres.

    - retire les lignes sans identifiant ou sans objet ;
    - normalise les espaces dans les champs texte ;
    - type les dates ; annule une date limite antérieure à la parution ;
    - force `score_pertinence` en entier ;
    - dédoublonne sur `id_source`.
    """
    rap = _rapport_init(len(df))
    df = df.copy()

    # 1. id + objet obligatoires
    avant = len(df)
    df = df.dropna(subset=["id_source", "objet"])
    df = df[df["objet"].astype(str).str.strip() != ""]
    rap["retirees"]["sans_id_ou_objet"] = avant - len(df)

    # 2. normalisation des espaces
    for col in ("objet", "acheteur", "categorie", "mots_cles_trouves"):
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
                .replace({"nan": None, "None": None})
            )

    # 3. dates
    for col in ("date_parution", "date_limite_reponse"):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # 4. incohérence de dates : limite < parution -> on annule la limite
    masque = df.apply(
        lambda r: (
            r["date_limite_reponse"] is not None
            and r["date_parution"] is not None
            and pd.notna(r["date_limite_reponse"])
            and pd.notna(r["date_parution"])
            and r["date_limite_reponse"] < r["date_parution"]
        ),
        axis=1,
    )
    rap["retirees"]["date_limite_incoherente_corrigee"] = int(masque.sum())
    df.loc[masque, "date_limite_reponse"] = None

    # 5. score entier
    df["score_pertinence"] = (
        pd.to_numeric(df["score_pertinence"], errors="coerce").fillna(0).astype(int)
    )

    # 6. doublons sur id_source
    avant = len(df)
    if "horodatage_ingestion" in df.columns:
        df = df.sort_values("horodatage_ingestion")
    df = df.drop_duplicates(subset=["id_source"], keep="last")
    rap["retirees"]["doublon"] = avant - len(df)

    df = df.sort_values(
        ["date_parution", "score_pertinence"], ascending=[False, False]
    ).reset_index(drop=True)
    rap["lignes_sortie"] = len(df)
    return df, rap


# =========================================================================
# Devis (Module 3)
# =========================================================================
def nettoyer_devis(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Contrôle de cohérence des devis (générés propres, mais on vérifie)."""
    rap = _rapport_init(len(df))
    df = df.copy()

    avant = len(df)
    df = df.dropna(subset=["id_devis", "date_devis", "client", "montant_ht"])
    rap["retirees"]["valeurs_manquantes"] = avant - len(df)

    df["montant_ht"] = pd.to_numeric(df["montant_ht"], errors="coerce")
    avant = len(df)
    df = df[df["montant_ht"].fillna(-1) >= 0]
    rap["retirees"]["montant_invalide"] = avant - len(df)

    statuts_ok = {"gagné", "perdu", "en cours"}
    avant = len(df)
    df = df[df["statut"].isin(statuts_ok)]
    rap["retirees"]["statut_inconnu"] = avant - len(df)

    avant = len(df)
    df = df.drop_duplicates(subset=["id_devis"], keep="last")
    rap["retirees"]["doublon"] = avant - len(df)

    df = df.reset_index(drop=True)
    rap["lignes_sortie"] = len(df)
    return df, rap


# =========================================================================
# Affichage
# =========================================================================
def afficher_rapport(nom: str, rap: dict) -> None:
    retirees = {k: v for k, v in rap["retirees"].items() if v}
    detail = ", ".join(f"{k}={v}" for k, v in retirees.items()) or "rien à retirer"
    print(
        f"  [{nom}] {rap['lignes_entree']} -> {rap['lignes_sortie']} lignes  ({detail})"
    )
