import { useEffect, useState } from "react";
import { api } from "./api";
import KpiCard from "./components/KpiCard";
import PriceChart from "./components/PriceChart";
import TendersTable from "./components/TendersTable";
import QuotesChart from "./components/QuotesChart";
import Chatbot from "./components/Chatbot";

export default function App() {
  const [prix, setPrix] = useState(null);
  const [appelsOffres, setAppelsOffres] = useState(null);
  const [devis, setDevis] = useState(null);
  const [testsStat, setTestsStat] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    Promise.all([
      api.prixActuels(), api.appelsOffres(50), api.devis(300), api.testsStatistiques(),
    ])
      .then(([p, ao, d, t]) => {
        setPrix(p); setAppelsOffres(ao); setDevis(d); setTestsStat(t);
      })
      .catch((e) => setErreur(e.message));
  }, []);

  if (erreur) {
    return (
      <div className="app">
        <p className="erreur">
          Impossible de joindre l'API ({erreur}). Vérifie qu'elle tourne :
          <code> uvicorn main:app --port 8000</code> dans le dossier <code>api/</code>.
        </p>
      </div>
    );
  }

  if (!prix) {
    return <div className="app"><p className="etat">Chargement des données BTP Pulse…</p></div>;
  }

  const nbAlertes = testsStat.filter((t) => t.significatif).length;
  const nbAoOuverts = appelsOffres.length;
  const nbGagnes = devis.filter((d) => d.statut === "gagné").length;
  const nbStatues = devis.filter((d) => d.statut !== "en cours").length;
  const tauxReussite = nbStatues ? Math.round((100 * nbGagnes) / nbStatues) : 0;
  const pipelineEnCours = devis
    .filter((d) => d.statut === "en cours")
    .reduce((s, d) => s + Number(d.montant_ht), 0);

  return (
    <div className="app">
      <div className="entete">
        <h1>BTP <span>Pulse</span></h1>
        <div className="sous-titre">Prix matériaux, appels d'offres &amp; devis — vue de pilotage</div>
      </div>

      <div className="kpi-grille">
        <KpiCard label="Matériaux suivis" valeur={prix.length} />
        <KpiCard
          label="Variations significatives" valeur={nbAlertes}
          detail={nbAlertes > 0 ? "à surveiller" : "situation stable"}
          sens={nbAlertes > 0 ? "hausse" : "baisse"}
        />
        <KpiCard label="Appels d'offres pertinents" valeur={nbAoOuverts} detail="score ≥ 3" />
        <KpiCard label="Taux de réussite devis" valeur={`${tauxReussite}%`} />
        <KpiCard
          label="Pipeline en cours"
          valeur={`${Math.round(pipelineEnCours / 1000)} k€`}
        />
      </div>

      <PriceChart materiaux={prix} />

      <div className="grille-2">
        <TendersTable appelsOffres={appelsOffres} />
        <QuotesChart devis={devis} />
      </div>

      <Chatbot />
    </div>
  );
}
