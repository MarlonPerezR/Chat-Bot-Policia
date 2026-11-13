import { useEffect, useRef } from "react";
import { t } from "../theme.js";
import Message from "./Message.jsx";
import SearchBar from "./SearchBar.jsx";

export default function Chat({ messages, onQuery, loading }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <main
      style={{
        flex: 1, minHeight: 0, display: "flex", flexDirection: "column",
        width: "100%", maxWidth: 820, margin: "0 auto",
        padding: "0 clamp(16px, 4vw, 40px)", position: "relative", zIndex: 1,
      }}
    >
      <div className="lp-scroll" style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 2px 16px", display: "grid", gap: 20 }}>
        {messages.map((m) => (
          <Message key={m.id} msg={m} />
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ padding: "8px 0 24px" }}>
        <SearchBar onSubmit={onQuery} disabled={loading} placeholder="Haz otra consulta sobre la Ley 1801…" />
      </div>
    </main>
  );
}
