import { useState } from "react";
import { t } from "../theme.js";
import { Search, Mic, Send } from "./Icons.jsx";

export default function SearchBar({ onSubmit, disabled, autoFocus, placeholder }) {
  const [value, setValue] = useState("");

  function submit(e) {
    e.preventDefault();
    const q = value.trim();
    if (!q || disabled) return;
    onSubmit(q);
    setValue("");
  }

  return (
    <form
      onSubmit={submit}
      style={{
        display: "flex", alignItems: "center", gap: 12, background: t.card,
        borderRadius: 18, padding: "12px 12px 12px 20px", boxShadow: t.shadowSearch,
        textAlign: "left", opacity: disabled ? 0.75 : 1,
      }}
    >
      <Search />
      <label htmlFor="q-main" className="sr-only">Describe tu consulta</label>
      <input
        id="q-main"
        type="text"
        autoFocus={autoFocus}
        disabled={disabled}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder || "Describe la situación que necesitas resolver…"}
        style={{
          flex: 1, minWidth: 0, border: "none", background: "transparent",
          fontSize: 15.5, color: t.ink, outline: "none",
        }}
      />
      <button
        type="button"
        aria-label="Dictar por voz"
        style={{
          width: 42, height: 42, borderRadius: 12, border: "none", background: t.bg,
          display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flex: "none",
        }}
      >
        <Mic />
      </button>
      <button
        type="submit"
        aria-label="Enviar consulta"
        disabled={disabled}
        style={{
          width: 46, height: 46, borderRadius: 13, border: "none", background: t.green,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: disabled ? "default" : "pointer", flex: "none",
        }}
      >
        <Send />
      </button>
    </form>
  );
}
