export default function TendersTable({ appelsOffres }) {
  return (
    <div className="section">
      <h2>Appels d'offres pertinents</h2>
      <p className="intro">
        Marchés publics BTP scorés par pertinence (mots-clés secteur),
        triés par score décroissant — Module 2.
      </p>
      <table>
        <thead>
          <tr>
            <th>Score</th>
            <th>Objet</th>
            <th>Département</th>
            <th>Limite de réponse</th>
          </tr>
        </thead>
        <tbody>
          {appelsOffres.slice(0, 8).map((a) => (
            <tr key={a.id_source}>
              <td><span className="badge signif">{a.score_pertinence}</span></td>
              <td>
                {a.url_avis ? (
                  <a href={a.url_avis} target="_blank" rel="noreferrer">{a.objet}</a>
                ) : a.objet}
              </td>
              <td>{a.departements}</td>
              <td>{a.date_limite_reponse ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
