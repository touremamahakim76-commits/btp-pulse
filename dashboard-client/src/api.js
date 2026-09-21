// Module 11 — client HTTP vers l'API BTP Pulse (Module 9)
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(chemin) {
  const reponse = await fetch(`${BASE_URL}${chemin}`);
  if (!reponse.ok) {
    throw new Error(`${chemin} -> HTTP ${reponse.status}`);
  }
  return reponse.json();
}

export const api = {
  prixActuels: () => get("/prix/actuels"),
  prixHistorique: (code, jours = 730) => get(`/prix/${code}/historique?jours=${jours}`),
  prediction: (code) => get(`/prix/${code}/prediction`).catch(() => null),
  appelsOffres: (limite = 20) => get(`/appels-offres?score_min=3&limite=${limite}`),
  testsStatistiques: () => get("/tests-statistiques"),
  devis: (limite = 300) => get(`/devis?limite=${limite}`),
  poserQuestion: (question, topK = 4) =>
    fetch(`${BASE_URL}/chatbot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK }),
    }).then((r) => {
      if (!r.ok) throw new Error(`chatbot -> HTTP ${r.status}`);
      return r.json();
    }),
};
