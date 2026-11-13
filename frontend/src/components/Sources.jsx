import { useState } from "react";
import { t } from "../theme.js";

const ETIQUETA_VIGENCIA = {
  vigente: { txt: "Vigente", bg: "#E3F0E4", fg: "#245237" },
  inexequible: { txt: "Inexequible", bg: "#FBE4E4", fg: "#9B2C2C" },
  inexequible_parcial: { txt: "Inexequible parcial", bg: "#FCEFE0", fg: "#9A5B13" },
  derogado: { txt: "Derogado", bg: "#ECECEC", fg: "#555" },
};

function FuenteItem({ f }) {
  const [open, setOpen] = useState(false);
  const vig = ETIQUETA_VIGENCIA[f.estado_vigencia] || ETIQUETA_VIGENCIA.vigente;
  const largo = f.texto.length > 220;
  const texto = open || !largo ? f.texto : f.texto.slice(0, 220) + "…";

  return (
    <div style={{ background: t.card, borderRadius: 14, padding: 14, boxShadow: t.shadowCard }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: t.badgeInk, background: t.tintC, padding: "3px 9px", borderRadius: 6 }}>
          Art. {f.articulo}
        </span>
        <span style={{ fontSize: 11.5, fontWeight: 600, color: vig.fg, background: vig.bg, padding: "3px 9px", borderRadius: 6 }}>
          {vig.txt}
        </span>
        <span style={{ fontSize: 11, color: t.greenSoft, marginLeft: "auto" }}>
          {(f.puntaje * 100).toFixed(0)}% afinidad
        </span>
      </div>
      {f.epigrafe && (
        <div style={{ fontSize: 13.5, fontWeight: 600, color: t.ink, marginBottom: 4 }}>{f.epigrafe}</div>
      )}
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: t.muted2 }}>{texto}</p>
      {largo && (
        <button
          onClick={() => setOpen((o) => !o)}
          style={{ marginTop: 6, background: "transparent", border: "none", color: t.greenSoft, fontWeight: 600, fontSize: 12, cursor: "pointer", padding: 0 }}
        >
          {open ? "Ver menos" : "Ver más"}
        </button>
      )}
      {f.ubicacion_jerarquica?.titulo && (
        <div style={{ marginTop: 8, fontSize: 10.5, color: t.greenSoft }}>
          {f.ubicacion_jerarquica.titulo}
        </div>
      )}
    </div>
  );
}

export default function Sources({ fuentes }) {
  if (!fuentes?.length) return null;
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: t.greenSoft, marginBottom: 10, textTransform: "uppercase", letterSpacing: ".04em" }}>
        Fuentes del Código ({fuentes.length})
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {fuentes.map((f) => (
          <FuenteItem key={f.identificador} f={f} />
        ))}
      </div>
    </div>
  );
}
