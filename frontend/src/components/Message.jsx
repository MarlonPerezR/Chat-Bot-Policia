import { t } from "../theme.js";
import { Shield } from "./Icons.jsx";
import Sources from "./Sources.jsx";

// Convierte el texto plano del LLM en párrafos, resaltando "Art. N".
function formatear(texto) {
  return texto.split(/\n{2,}/).map((parrafo, i) => {
    const partes = parrafo.split(/(\bArt\.?\s?\d+[A-Z]?\b)/g);
    return (
      <p key={i}>
        {partes.map((p, j) =>
          /^Art\.?\s?\d+[A-Z]?$/.test(p) ? <strong key={j}>{p}</strong> : p
        )}
      </p>
    );
  });
}

export default function Message({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="lp-fade" style={{ display: "flex", justifyContent: "flex-end" }}>
        <div style={{ maxWidth: "80%", background: t.green, color: "#fff", padding: "12px 16px", borderRadius: "16px 16px 4px 16px", fontSize: 14.5, lineHeight: 1.5 }}>
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="lp-fade" style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <span style={{ flex: "none", width: 34, height: 34, borderRadius: 10, background: t.tintA, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Shield size={20} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ background: t.card, borderRadius: "4px 16px 16px 16px", padding: "14px 18px", boxShadow: t.shadowCard }}>
          {msg.loading ? (
            <div style={{ display: "flex", gap: 6, padding: "4px 0" }}>
              <span className="lp-dot" style={dot(0)} />
              <span className="lp-dot" style={dot(0.2)} />
              <span className="lp-dot" style={dot(0.4)} />
            </div>
          ) : msg.error ? (
            <p style={{ margin: 0, color: "#9B2C2C", fontSize: 14 }}>{msg.content}</p>
          ) : (
            <div className="lp-answer" style={{ fontSize: 14.5, color: t.ink }}>
              {formatear(msg.content)}
            </div>
          )}
        </div>
        {!msg.loading && !msg.error && <Sources fuentes={msg.fuentes} />}
        {!msg.loading && !msg.error && (
          <p style={{ margin: "10px 2px 0", fontSize: 11, color: t.greenSoft }}>
            Orientación informativa basada en la Ley 1801 de 2016. No sustituye asesoría jurídica profesional.
          </p>
        )}
      </div>
    </div>
  );
}

const dot = (delay) => ({
  width: 8, height: 8, borderRadius: "50%", background: t.greenSoft,
  animationDelay: `${delay}s`,
});
