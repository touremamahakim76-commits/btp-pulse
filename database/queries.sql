-- =====================================================================
-- BTP Pulse — Module 3 : requêtes de démonstration
-- =====================================================================
-- À lancer dans psql :
--   docker exec -it btp_pulse_pg psql -U btp -d btp_pulse -f /dev/stdin < database/queries.sql
-- ou copier/coller une requête à la fois.
-- =====================================================================

-- 1. Dernier prix connu par matériau (via la vue)
SELECT * FROM v_dernier_prix_materiau ORDER BY indice_base100 DESC;

-- 2. Évolution du prix sur 12 mois glissants, par matériau
WITH bornes AS (
    SELECT code_materiau,
           min(prix) FILTER (WHERE date_releve <= current_date - INTERVAL '12 months') AS prix_il_y_a_1_an,
           (array_agg(prix ORDER BY date_releve DESC))[1]                              AS prix_actuel
    FROM materiaux_prix
    GROUP BY code_materiau
)
SELECT b.code_materiau, m.libelle,
       round(b.prix_il_y_a_1_an, 2) AS prix_1_an,
       round(b.prix_actuel, 2)      AS prix_actuel,
       round(100.0 * (b.prix_actuel - b.prix_il_y_a_1_an) / b.prix_il_y_a_1_an, 1) AS variation_pct
FROM bornes b
JOIN materiaux m ON m.code = b.code_materiau
WHERE b.prix_il_y_a_1_an IS NOT NULL
ORDER BY variation_pct DESC;

-- 3. Appels d'offres pertinents encore ouverts (date limite future)
SELECT date_parution, date_limite_reponse, departements, score_pertinence,
       left(objet, 80) AS objet
FROM appels_offres
WHERE date_limite_reponse >= current_date
  AND score_pertinence >= 4
ORDER BY score_pertinence DESC, date_limite_reponse
LIMIT 20;

-- 4. Taux de réussite des devis par type de chantier
SELECT type_chantier,
       count(*)                                             AS nb_devis,
       count(*) FILTER (WHERE statut = 'gagné')             AS gagnes,
       round(100.0 * count(*) FILTER (WHERE statut = 'gagné')
             / NULLIF(count(*) FILTER (WHERE statut IN ('gagné','perdu')), 0), 1) AS taux_reussite_pct,
       round(avg(marge_estimee_pct), 1)                     AS marge_moyenne_pct,
       round(avg(montant_ht))                               AS montant_moyen_ht
FROM devis_historique
GROUP BY type_chantier
ORDER BY taux_reussite_pct DESC NULLS LAST;

-- 5. Volume d'appels d'offres par département (top 15)
SELECT unnest(string_to_array(departements, ',')) AS departement,
       count(*)                                    AS nb_annonces
FROM appels_offres
GROUP BY 1
ORDER BY nb_annonces DESC
LIMIT 15;

-- 6. Fraîcheur des données (dernière ingestion par table)
SELECT 'materiaux_prix' AS table, max(horodatage_ingestion) AS derniere_ingestion FROM materiaux_prix
UNION ALL
SELECT 'appels_offres', max(horodatage_ingestion) FROM appels_offres;
