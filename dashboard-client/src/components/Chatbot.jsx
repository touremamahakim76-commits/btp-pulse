import { useState } from "react";
import { api } from "../api";

export default function Chatbot() {
  const [question, setQuestion] = useState("");
  const [reponse, setReponse] = useState(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);

  async function envoyer(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setChargement(true);
    setErreur(null);
    try {
      const r = await api.poserQuestion(question);
      setReponse(r);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setChargement(false);
    }
  }

  return (
    <div className="section">
      <h2>Assistant devis (RAG)</h2>
      <p className="intro">
        Pose une question en langage naturel sur l'historique de devis —
        Module 8 (ChromaDB + Claude).
      </p>
      <div className="chat-box">
        <form className="chat-form" onSubmit={envoyer}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ex. Quels devis avons-nous perdus à cause du prix de l'acier ?"
          />
          <button disabled={chargement}>{chargement ? "…" : "Envoyer"}</button>
        </form>
        {erreur && <p className="erreur">{erreur}</p>}
        {reponse && (
          <div className="chat-reponse">
            {reponse.reponse}
            {reponse.sources?.length > 0 && (
              <div className="chat-note" style={{ marginTop: 8 }}>
                Sources : {reponse.sources.join(", ")}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
