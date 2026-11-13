import { t } from "../theme.js";
import { Shield, Pin, Chevron } from "./Icons.jsx";

export default function Header({ onHome }) {
  return (
    <header
      style={{
        height: 76,
        flex: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 clamp(16px, 4vw, 40px)",
        position: "relative",
        zIndex: 1,
      }}
    >
      <button
        onClick={onHome}
        aria-label="Ir al inicio"
        style={{ display: "flex", alignItems: "center", gap: 11, background: "transparent", border: "none", cursor: "pointer", padding: 0 }}
      >
        <Shield />
        <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
          <span style={{ fontFamily: t.display, fontWeight: 700, fontSize: 18, color: t.green, letterSpacing: "-.01em" }}>
            LexPolicía
          </span>
          <span style={{ fontFamily: t.display, fontWeight: 600, fontSize: 12, color: t.greenSoft, background: t.tintA, padding: "2px 7px", borderRadius: 6 }}>
            AI
          </span>
        </div>
      </button>

      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <button
          style={{
            display: "flex", alignItems: "center", gap: 8, background: "transparent",
            border: "none", borderRadius: 10, padding: "8px 10px", fontSize: 13.5,
            fontWeight: 600, color: t.muted3, cursor: "pointer",
          }}
        >
          <Pin />
          Bogotá D.C.
          <Chevron />
        </button>
        <div
          aria-hidden="true"
          style={{
            width: 38, height: 38, borderRadius: "50%", background: t.green, color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 700, fontSize: 14, fontFamily: t.display,
          }}
        >
          C
        </div>
      </div>
    </header>
  );
}
