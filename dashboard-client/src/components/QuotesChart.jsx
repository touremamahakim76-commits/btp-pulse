import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

function agreger(devis) {
  const parType = {};
  for (const d of devis) {
    const t = d.type_chantier;
    parType[t] ??= { type: t, gagné: 0, perdu: 0, "en cours": 0 };
    parType[t][d.statut] += 1;
  }
  return Object.values(parType);
}

export default function QuotesChart({ devis }) {
  const donnees = agreger(devis);
  const nbGagnes = devis.filter((d) => d.statut === "gagné").length;
  const nbStatues = devis.filter((d) => d.statut !== "en cours").length;
  const taux = nbStatues ? Math.round((100 * nbGagnes) / nbStatues) : 0;

  return (
    <div className="section">
      <h2>Devis : gagné / perdu / en cours</h2>
      <p className="intro">
        {devis.length} devis historiques (démonstration) — taux de réussite global : <strong>{taux}%</strong>.
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={donnees} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eceff2" />
          <XAxis dataKey="type" tick={{ fontSize: 10 }} interval={0} angle={-18} textAnchor="end" height={70} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="gagné" stackId="s" fill="#1e8e5a" radius={[0, 0, 0, 0]} />
          <Bar dataKey="perdu" stackId="s" fill="#c23b3b" />
          <Bar dataKey="en cours" stackId="s" fill="#b8b8b8" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
