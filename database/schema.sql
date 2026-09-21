-- =====================================================================
-- BTP Pulse — Module 3 : schéma de la base transactionnelle PostgreSQL
-- =====================================================================
-- Appliqué automatiquement au premier démarrage du conteneur
-- (dossier /docker-entrypoint-initdb.d) OU manuellement :
--     python load.py --init
--
-- Le script est ré-exécutable sans risque (CREATE ... IF NOT EXISTS,
-- CREATE OR REPLACE VIEW).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Référentiel des matériaux suivis (issu du Module 1)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS materiaux (
    code      TEXT PRIMARY KEY,
    libelle   TEXT NOT NULL,
    unite     TEXT NOT NULL,
    prix_ref  NUMERIC(12,4)          -- prix indicatif € HT de référence
);

COMMENT ON TABLE materiaux IS
    'Référentiel des matériaux de construction suivis (Module 1)';

-- ---------------------------------------------------------------------
-- Historique des prix relevés (Module 1)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS materiaux_prix (
    id                    BIGSERIAL PRIMARY KEY,
    date_releve           DATE NOT NULL,
    code_materiau         TEXT NOT NULL REFERENCES materiaux(code),
    prix                  NUMERIC(12,4) NOT NULL CHECK (prix > 0),
    indice_base100        NUMERIC(8,2),
    source                TEXT NOT NULL,        -- 'eurostat' | 'demo'
    horodatage_ingestion  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- un seul prix par matériau et par date de relevé
    CONSTRAINT uq_prix_date_materiau UNIQUE (date_releve, code_materiau)
);

CREATE INDEX IF NOT EXISTS idx_prix_materiau_date
    ON materiaux_prix (code_materiau, date_releve);

COMMENT ON TABLE materiaux_prix IS
    'Relevés de prix par matériau et par date (Module 1)';

-- ---------------------------------------------------------------------
-- Appels d'offres publics (Module 2)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appels_offres (
    id_source             TEXT PRIMARY KEY,     -- idweb BOAMP
    objet                 TEXT NOT NULL,
    acheteur              TEXT,
    departements          TEXT,                 -- codes séparés par virgules
    date_parution         DATE,
    date_limite_reponse   DATE,
    type_marche           TEXT,                 -- TRAVAUX / SERVICES / FOURNITURES
    categorie             TEXT,                 -- descripteur BOAMP
    mots_cles_trouves     TEXT,
    score_pertinence      INTEGER NOT NULL DEFAULT 0,
    url_avis              TEXT,
    source                TEXT NOT NULL,        -- 'boamp' | 'demo'
    horodatage_ingestion  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ao_parution
    ON appels_offres (date_parution DESC);
CREATE INDEX IF NOT EXISTS idx_ao_score
    ON appels_offres (score_pertinence DESC);

COMMENT ON TABLE appels_offres IS
    'Avis de marchés publics BTP filtrés et scorés (Module 2)';

-- ---------------------------------------------------------------------
-- Historique de devis (données de démonstration — Module 3)
-- Sert de base au chatbot RAG (Module 8) et à l'API (Module 9).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devis_historique (
    id_devis              TEXT PRIMARY KEY,
    date_devis            DATE NOT NULL,
    client                TEXT NOT NULL,
    type_chantier         TEXT NOT NULL,
    departement           TEXT,
    surface_m2            NUMERIC(10,2),
    montant_ht            NUMERIC(14,2) NOT NULL CHECK (montant_ht >= 0),
    statut                TEXT NOT NULL
                          CHECK (statut IN ('gagné', 'perdu', 'en cours')),
    marge_estimee_pct     NUMERIC(5,2),
    principaux_materiaux  TEXT,
    commentaire           TEXT
);

CREATE INDEX IF NOT EXISTS idx_devis_date ON devis_historique (date_devis);
CREATE INDEX IF NOT EXISTS idx_devis_statut ON devis_historique (statut);

COMMENT ON TABLE devis_historique IS
    'Devis fictifs réalistes pour la démonstration (Module 3)';

-- ---------------------------------------------------------------------
-- Vue pratique : dernier prix connu par matériau
-- (réutilisée par l'API du Module 9)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dernier_prix_materiau AS
SELECT DISTINCT ON (mp.code_materiau)
       mp.code_materiau,
       m.libelle,
       m.unite,
       mp.date_releve,
       mp.prix,
       mp.indice_base100,
       mp.source
FROM materiaux_prix mp
JOIN materiaux m ON m.code = mp.code_materiau
ORDER BY mp.code_materiau, mp.date_releve DESC;

-- ---------------------------------------------------------------------
-- Résultats des tests statistiques de significativité (Module 6)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resultats_tests_statistiques (
    id                  BIGSERIAL PRIMARY KEY,
    code_materiau       TEXT NOT NULL REFERENCES materiaux(code),
    date_test           TIMESTAMPTZ NOT NULL DEFAULT now(),
    jours_recents       INTEGER NOT NULL,
    jours_reference     INTEGER NOT NULL,
    n_recents           INTEGER NOT NULL,
    n_reference         INTEGER NOT NULL,
    moyenne_recente     NUMERIC(12,4),
    moyenne_reference   NUMERIC(12,4),
    variation_pct       NUMERIC(8,2),
    t_stat              NUMERIC(12,4),
    p_value             NUMERIC(12,8),
    seuil_alpha         NUMERIC(4,3) NOT NULL DEFAULT 0.05,
    significatif        BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tests_stat_materiau_date
    ON resultats_tests_statistiques (code_materiau, date_test DESC);

COMMENT ON TABLE resultats_tests_statistiques IS
    'Historique des tests de significativité (t-test) sur les variations de prix (Module 6)';

-- ---------------------------------------------------------------------
-- Prédictions de prix à 30 jours (Module 7)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions_prix (
    id                    BIGSERIAL PRIMARY KEY,
    code_materiau         TEXT NOT NULL REFERENCES materiaux(code),
    date_prediction       TIMESTAMPTZ NOT NULL DEFAULT now(),
    horizon_jours         INTEGER NOT NULL,
    prix_actuel           NUMERIC(12,4) NOT NULL,
    prix_predit           NUMERIC(12,4) NOT NULL,
    variation_pct_predite NUMERIC(8,2),
    modele                TEXT NOT NULL,
    mae_validation         NUMERIC(12,4)
);

CREATE INDEX IF NOT EXISTS idx_predictions_materiau_date
    ON predictions_prix (code_materiau, date_prediction DESC);

COMMENT ON TABLE predictions_prix IS
    'Prédictions de prix à horizon 30 jours (Module 7)';
