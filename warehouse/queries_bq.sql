-- =====================================================================
-- BTP Pulse — Module 5 : requêtes de démonstration sur BigQuery
-- =====================================================================
-- À lancer dans la console BigQuery, ou :
--   bq query --use_legacy_sql=false < warehouse/queries_bq.sql
-- Remplace `TON_PROJET` par ton project id (BQ_PROJECT du .env).
-- =====================================================================

-- 1. Dernier prix connu par matériau (QUALIFY = idiome BigQuery, pas de
--    sous-requête nécessaire pour un "top 1 par groupe")
SELECT code_materiau, date_releve, prix, indice_base100
FROM `TON_PROJET.btp_pulse.materiaux_prix`
QUALIFY ROW_NUMBER() OVER (PARTITION BY code_materiau ORDER BY date_releve DESC) = 1
ORDER BY indice_base100 DESC;

-- 2. Variation de prix sur 12 mois glissants, par matériau
--    (le partitionnement sur date_releve limite le volume scanné)
WITH releves AS (
    SELECT code_materiau, date_releve, prix,
           ROW_NUMBER() OVER (PARTITION BY code_materiau ORDER BY date_releve DESC) AS rang_recent,
           ROW_NUMBER() OVER (
               PARTITION BY code_materiau
               ORDER BY ABS(DATE_DIFF(date_releve, DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH), DAY))
           ) AS rang_il_y_a_1_an
    FROM `TON_PROJET.btp_pulse.materiaux_prix`
)
SELECT a.code_materiau,
       b.prix AS prix_il_y_a_1_an,
       a.prix AS prix_actuel,
       ROUND(100 * (a.prix - b.prix) / b.prix, 1) AS variation_pct
FROM releves a
JOIN releves b USING (code_materiau)
WHERE a.rang_recent = 1 AND b.rang_il_y_a_1_an = 1
ORDER BY variation_pct DESC;

-- 3. Appels d'offres pertinents encore ouverts
SELECT date_parution, date_limite_reponse, departements, score_pertinence,
       SUBSTR(objet, 1, 80) AS objet
FROM `TON_PROJET.btp_pulse.appels_offres`
WHERE date_limite_reponse >= CURRENT_DATE()
  AND score_pertinence >= 4
ORDER BY score_pertinence DESC, date_limite_reponse
LIMIT 20;

-- 4. Taux de réussite des devis par type de chantier
SELECT type_chantier,
       COUNT(*) AS nb_devis,
       COUNTIF(statut = 'gagné') AS gagnes,
       ROUND(100 * COUNTIF(statut = 'gagné')
             / NULLIF(COUNTIF(statut IN ('gagné', 'perdu')), 0), 1) AS taux_reussite_pct,
       ROUND(AVG(marge_estimee_pct), 1) AS marge_moyenne_pct
FROM `TON_PROJET.btp_pulse.devis_historique`
GROUP BY type_chantier
ORDER BY taux_reussite_pct DESC;

-- 5. Volume d'appels d'offres par département
SELECT dept, COUNT(*) AS nb_annonces
FROM `TON_PROJET.btp_pulse.appels_offres`,
     UNNEST(SPLIT(departements, ',')) AS dept
GROUP BY dept
ORDER BY nb_annonces DESC
LIMIT 15;

-- 6. Estimation du volume scanné avant de lancer une requête (dry run)
--    — bon réflexe de maîtrise des coûts BigQuery, à montrer en entretien :
--    bq query --use_legacy_sql=false --dry_run "SELECT * FROM \`TON_PROJET.btp_pulse.materiaux_prix\`"
