import { t } from "../theme.js";
import SearchBar from "./SearchBar.jsx";
import { Clip, Book, ICONOS_FRECUENTES } from "./Icons.jsx";

function Badge({ children }) {
  return (
    <span style={{ fontSize: 11.5, fontWeight: 700, color: t.badgeInk, background: t.tintC, padding: "3px 9px", borderRadius: 6, alignSelf: "flex-start" }}>
      {children}
    </span>
  );
}

export default function Home({ frecuentes, recientes, onQuery }) {
  return (
    <main
      style={{
        flex: 1, minHeight: 0, display: "flex", flexDirection: "column",
        padding: "8px clamp(16px, 4vw, 40px) 44px", position: "relative", zIndex: 1,
        width: "100%", maxWidth: 1360, margin: "0 auto",
      }}
    >
      {/* Hero */}
      <section style={{ maxWidth: 760, width: "100%", margin: "clamp(24px, 6vh, 56px) auto 0", textAlign: "center" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 600, color: t.muted2, marginBottom: 18 }}>
          <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: "50%", background: "#3E9A5E" }} />
          Actualizado · Jurisprudencia 2024
        </span>
        <h1 style={{ margin: 0, fontFamily: t.display, fontWeight: 600, fontSize: "clamp(26px, 4vw, 34px)", color: t.ink, letterSpacing: "-.025em" }}>
          ¿En qué puedo ayudarte?
        </h1>
        <p style={{ margin: "10px 0 28px", fontSize: 15, color: t.muted }}>
          Asistente para la convivencia y la Ley 1801 de 2016
        </p>

        <SearchBar onSubmit={onQuery} autoFocus />

        <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          <button style={pill}>
            <Clip /> Adjuntar
          </button>
          <button style={pill}>
            <Book /> Normativa
          </button>
        </div>
      </section>

      {/* Consultas frecuentes */}
      <section style={{ marginTop: "auto", paddingTop: 44 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontFamily: t.display, fontWeight: 600, fontSize: 15, color: t.ink2 }}>Consultas frecuentes</h2>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: t.greenSoft, cursor: "pointer" }}>Ver todas</span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
          {frecuentes.map((f) => {
            const Icon = ICONOS_FRECUENTES[f.id] || ICONOS_FRECUENTES.ruido;
            return (
              <button key={f.id} onClick={() => onQuery(f.consulta)} style={card}>
                <span style={iconBox}><Icon /></span>
                <span style={{ fontSize: 14.5, fontWeight: 600, color: t.ink }}>{f.titulo}</span>
                <Badge>Art. {f.articulo}</Badge>
              </button>
            );
          })}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: t.greenSoft, marginRight: 2 }}>Recientes:</span>
          {recientes.map((r, i) => (
            <button key={i} onClick={() => onQuery(r.consulta)} style={chip}>
              {r.texto} · Art. {r.articulo}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

const pill = {
  display: "flex", alignItems: "center", gap: 7, background: "transparent",
  border: `1px solid ${t.border}`, borderRadius: 10, padding: "8px 13px",
  fontSize: 13, fontWeight: 600, color: t.muted3, cursor: "pointer",
};
const card = {
  textAlign: "left", display: "flex", flexDirection: "column", gap: 12, padding: 18,
  border: "none", borderRadius: 18, background: t.card, cursor: "pointer", boxShadow: t.shadowCard,
};
const iconBox = {
  width: 42, height: 42, borderRadius: 12, background: t.tintA,
  display: "flex", alignItems: "center", justifyContent: "center",
};
const chip = {
  fontSize: 12.5, fontWeight: 600, color: t.muted3, background: t.card,
  padding: "7px 13px", borderRadius: 20, border: "none", cursor: "pointer",
};
