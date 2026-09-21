export default function KpiCard({ label, valeur, detail, sens }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="valeur">{valeur}</div>
      {detail && (
        <div className={`detail ${sens === "hausse" ? "hausse" : sens === "baisse" ? "baisse" : ""}`}>
          {detail}
        </div>
      )}
    </div>
  );
}
