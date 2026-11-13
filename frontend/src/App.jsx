import { useEffect, useState } from "react";
import { t } from "./theme.js";
import Header from "./components/Header.jsx";
import Home from "./components/Home.jsx";
import Chat from "./components/Chat.jsx";
import { consultar, getFrecuentes } from "./api.js";

// Datos de respaldo por si el backend aún no responde /api/frecuentes.
const FALLBACK = {
  frecuentes: [
    { id: "ruido", titulo: "Vecino ruidoso", articulo: "33", consulta: "¿Qué puedo hacer si mi vecino hace ruido excesivo?" },
    { id: "mascotas", titulo: "Tenencia de mascotas", articulo: "126", consulta: "¿Cuáles son las reglas para la tenencia de mascotas?" },
    { id: "grabar", titulo: "Grabar a la policía", articulo: "21", consulta: "¿Puedo grabar un procedimiento de la policía?" },
    { id: "prontopago", titulo: "50% pronto pago", articulo: "180", consulta: "¿Cómo funciona el descuento del 50% por pronto pago?" },
  ],
  recientes: [
    { texto: "Música alta a medianoche", articulo: "33", consulta: "¿Qué dice la ley sobre música alta a medianoche?" },
    { texto: "Perros peligrosos", articulo: "126", consulta: "¿Qué exige la ley para perros peligrosos?" },
    { texto: "Grabación de procedimientos", articulo: "21", consulta: "¿Es legal grabar un procedimiento policial?" },
  ],
};

let idSeq = 0;
const nuevoId = () => `m${++idSeq}`;

export default function App() {
  const [data, setData] = useState(FALLBACK);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const enChat = messages.length > 0;

  useEffect(() => {
    getFrecuentes()
      .then(setData)
      .catch(() => {}); // si falla, se quedan los de respaldo
  }, []);

  async function handleQuery(consulta) {
    if (loading) return;
    const userMsg = { id: nuevoId(), role: "user", content: consulta };
    const botId = nuevoId();
    setMessages((m) => [...m, userMsg, { id: botId, role: "assistant", loading: true }]);
    setLoading(true);
    try {
      const res = await consultar(consulta);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === botId
            ? { id: botId, role: "assistant", content: res.respuesta, fuentes: res.fuentes, fueraDeDominio: res.fuera_de_dominio }
            : msg
        )
      );
    } catch (err) {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === botId
            ? { id: botId, role: "assistant", error: true, content: `No se pudo obtener respuesta: ${err.message}` }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  }

  function goHome() {
    setMessages([]);
    setLoading(false);
  }

  return (
    <div style={{ minHeight: "100dvh", display: "flex", flexDirection: "column", background: t.bg, position: "relative", overflow: "hidden" }}>
      {/* Halo radial decorativo del mockup */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute", top: -180, left: "50%", transform: "translateX(-50%)",
          width: 760, height: 420, pointerEvents: "none",
          background: "radial-gradient(circle, #DDEFDF 0%, rgba(221,239,223,0) 68%)",
        }}
      />
      <Header onHome={goHome} />
      {enChat ? (
        <Chat messages={messages} onQuery={handleQuery} loading={loading} />
      ) : (
        <Home frecuentes={data.frecuentes} recientes={data.recientes} onQuery={handleQuery} />
      )}
    </div>
  );
}
