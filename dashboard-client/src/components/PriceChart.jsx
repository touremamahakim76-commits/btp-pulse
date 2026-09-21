import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

export default function PriceChart({ materiaux }) {
  const [code, setCode] = useState(materiaux[0]?.code_materiau);
  const [historique, setHistorique] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    if (!code) return;
    setErreur(null);
    api.prixHistorique(code)
      .then((pts) => setHistorique(pts.map((p) => ({ ...p, prix: Number(p.prix) }))))
      .catch((e) => setErreur(e.message));
    api.prediction(code).then(setPrediction);
  }, [code]);

  const materiau = materiaux.find((m) => m.code_materiau === code);
  const donneesGraph = [...historique];
  if (prediction) {
    donneesGraph.push({
      date_releve: "+30j (prévision)",
      prix: Number(prediction.prix_predit),
      prevision: true,
    });
  }

  return (
    <div className="section">
      <h2>Évolution des prix matériaux</h2>
      <p className="intro">
        Historique réel (Eurostat) et prévision à 30 jours (modèle de
        régression, Module 7). Sélectionne un matériau.
      </p>
      <div className="selecteur">
        {materiaux.map((m) => (
          <button
            key={m.code_materiau}
            className={m.code_materiau === code ? "actif" : ""}
            onClick={() => setCode(m.code_materiau)}
          >
            {m.libelle}
          </button>
        ))}
      </div>

      {erreur && <p className="erreur">{erreur}</p>}

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={donneesGraph} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eceff2" />
          <XAxis dataKey="date_releve" tick={{ fontSize: 11 }} minTickGap={40} />
          <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} unit={` €`} width={70} />
          <Tooltip formatter={(v) => [`${v.toFixed(2)} €`, "Prix"]} />
          <Line
            type="monotone" dataKey="prix" stroke="#1e3a5f" strokeWidth={2}
            dot={false} activeDot={{ r: 4 }}
          />
          {prediction && donneesGraph.length > 0 && (
            <ReferenceDot
              x={donneesGraph[donneesGraph.length - 1].date_releve}
              y={donneesGraph[donneesGraph.length - 1].prix}
              r={5} fill="#d9622b" stroke="none"
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      {materiau && (
        <p className="chat-note">
          Prix actuel : <strong>{Number(materiau.prix).toFixed(2)} € / {materiau.unite}</strong>
          {prediction && (
            <> — prévision à 30 j : <strong>{Number(prediction.prix_predit).toFixed(2)} €</strong>{" "}
              ({prediction.variation_pct_predite > 0 ? "+" : ""}{prediction.variation_pct_predite}%,
              modèle {prediction.modele})</>
          )}
        </p>
      )}
    </div>
  );
}
