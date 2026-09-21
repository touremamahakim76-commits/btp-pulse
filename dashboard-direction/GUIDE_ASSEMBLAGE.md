# Module 10 — Dashboard Power BI (direction)

Power BI Desktop est une application graphique Windows : je ne peux pas
la piloter depuis un terminal. Voici le kit prêt à l'emploi pour
assembler le `.pbix` toi-même en ~10 minutes — tout le travail de
requête et de calcul est déjà préparé.

## Fichiers de ce dossier

- `connexion_postgresql.pbids` — raccourci de connexion : double-clique
  dessus, Power BI Desktop s'ouvre directement connecté à la base
  `btp_pulse` (pas besoin de naviguer dans « Obtenir des données »).
- `mesures_dax.txt` — les mesures DAX prêtes à copier-coller.

## Étapes

1. **Prérequis** : la base tourne (`docker compose -f database/docker-compose.yml up -d`)
   et le pilote PostgreSQL de Power BI est installé (Power BI Desktop le
   propose automatiquement au premier `Obtenir des données > PostgreSQL`,
   ou installe le driver Npgsql si demandé).

2. **Ouvrir la connexion** : double-clique `connexion_postgresql.pbids`.
   Identifiants : utilisateur `btp`, mot de passe `btp_pulse_dev`
   (ceux de `database/docker-compose.yml`).

3. **Sélectionner les tables** dans le navigateur : `materiaux`,
   `materiaux_prix`, `appels_offres`, `devis_historique`,
   `resultats_tests_statistiques`, `predictions_prix`,
   `v_dernier_prix_materiau`. Charger (Import, pas DirectQuery, pour un
   dashboard rapide et utilisable hors connexion pendant la démo).

4. **Relations** : Power BI détecte automatiquement
   `materiaux_prix[code_materiau] -> materiaux[code]`. Vérifie dans
   l'onglet Modèle.

5. **Mesures** : pour chaque mesure de `mesures_dax.txt`, clic droit sur
   la table indiquée > Nouvelle mesure > coller.

6. **Pages suggérées** (storytelling direction) :
   - **Vue d'ensemble** : cartes KPI (Dernier prix par matériau,
     Taux de réussite %, AO ouverts pertinents, Pipeline en cours €).
   - **Prix matériaux** : courbe temporelle `materiaux_prix[prix]` par
     `date_releve`, filtrée par `code_materiau` (slicer), avec un repère
     visuel sur les points où `resultats_tests_statistiques[significatif]`
     = vrai.
   - **Appels d'offres** : carte de France par département
     (`appels_offres[departements]`), table triée par score de
     pertinence.
   - **Devis** : entonnoir gagné/perdu/en cours par `type_chantier`,
     et marge moyenne pondérée.

7. **Publier** (optionnel, Power BI Service — nécessite un compte
   Microsoft/organisation) : `Accueil > Publier`.

## Pourquoi PostgreSQL plutôt que BigQuery pour ce module

La base PostgreSQL du Module 3 tourne déjà en local et contient toutes
les données à jour : c'est la connexion la plus rapide à démontrer.
Une fois le Module 5 finalisé avec tes accès GCP, le même dashboard
peut être rebranché sur BigQuery (connecteur natif Power BI) pour
montrer la maîtrise d'un entrepôt cloud — même principe, changer
uniquement la source dans `Transformer les données > Paramètres de la
source de données`.
