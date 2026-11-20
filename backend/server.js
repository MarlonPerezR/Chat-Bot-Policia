// API del asistente LexPolicía AI — Ley 1801 de 2016.
// Patrón RAG: busca los fragmentos relevantes del Código y Gemini redacta la
// respuesta citando solo esos fragmentos.

import "dotenv/config";
import express from "express";
import cors from "cors";
import { crearBuscador } from "./retrieval.js";
import { generarRespuesta } from "./gemini.js";

const PORT = process.env.PORT || 3001;
const app = express();
app.use(cors());
app.use(express.json());

// Carga perezosa del buscador: así el server arranca aunque falten embeddings,
// y el error se reporta claro en la primera consulta / en /api/health.
let buscador = null;
let corpus = [];
let modoBusqueda = null;
let errorArranque = null;
try {
  const b = crearBuscador();
  buscador = b.motor;
  corpus = b.corpus;
  modoBusqueda = b.modo;
  console.log(`Corpus cargado: ${corpus.length} fragmentos. Motor de búsqueda: ${modoBusqueda}.`);
} catch (err) {
  errorArranque = err.message;
  console.warn("Aviso:", err.message);
}

// Consultas frecuentes que muestra el front (mapeadas a preguntas reales).
const FRECUENTES = [
  { id: "ruido", titulo: "Vecino ruidoso", articulo: "33", consulta: "¿Qué puedo hacer si mi vecino hace ruido excesivo y perturba la tranquilidad?" },
  { id: "mascotas", titulo: "Tenencia de mascotas", articulo: "126", consulta: "¿Cuáles son las reglas para la tenencia de mascotas y perros potencialmente peligrosos?" },
  { id: "grabar", titulo: "Grabar a la policía", articulo: "21", consulta: "¿Puedo grabar un procedimiento de la policía en espacio público?" },
  { id: "prontopago", titulo: "50% pronto pago", articulo: "180", consulta: "¿Cómo funciona el descuento del 50% por pronto pago de una multa?" },
];

const RECIENTES = [
  { texto: "Música alta a medianoche", articulo: "33", consulta: "¿Qué dice la ley sobre música alta a medianoche?" },
  { texto: "Perros peligrosos", articulo: "126", consulta: "¿Qué requisitos exige la ley para perros potencialmente peligrosos?" },
  { texto: "Grabación de procedimientos", articulo: "21", consulta: "¿Es legal grabar un procedimiento policial?" },
];

const SYSTEM_PROMPT = `Eres LexPolicía AI, un asistente jurídico ciudadano especializado EXCLUSIVAMENTE en el Código Nacional de Seguridad y Convivencia Ciudadana de Colombia (Ley 1801 de 2016).

Reglas:
- Responde en español, claro y breve, para una persona sin formación jurídica.
- Básate ÚNICAMENTE en los fragmentos del Código que se te entregan como contexto. No inventes artículos, cifras ni sanciones.
- Cita los artículos relevantes en el formato "Art. N" dentro de la respuesta.
- Si algún fragmento está marcado como inexequible o derogado, adviértelo.
- Si los fragmentos NO responden la pregunta, dilo con honestidad y sugiere consultar a la autoridad competente (p. ej. la estación de policía, una inspección de policía o un abogado). No respondas con conocimiento ajeno al contexto.
- No des asesoría legal definitiva; aclara que es orientación informativa.
- Estructura la respuesta en 1 a 3 párrafos cortos. Nada de listas largas salvo que ayude.`;

function construirPrompt(consulta, fragmentos) {
  const contexto = fragmentos
    .map((f, i) => {
      const ubic = f.ubicacion_jerarquica || {};
      const notas = (f.notas || []).length ? `\n  Notas: ${f.notas.join(" | ")}` : "";
      return `[Fragmento ${i + 1}] Art. ${f.articulo} — ${f.epigrafe || "(sin epígrafe)"} (vigencia: ${f.estado_vigencia})
  ${ubic.titulo || ""} / ${ubic.capitulo || ""}
  ${f.texto}${notas}`;
    })
    .join("\n\n");

  return `Pregunta del ciudadano:
"${consulta}"

Fragmentos del Código (contexto):
${contexto}

Redacta la respuesta siguiendo las reglas. Cita los artículos usados.`;
}

app.get("/api/health", (req, res) => {
  res.json({
    ok: !!buscador,
    fragmentos: corpus.length,
    motor: modoBusqueda,
    modeloChat: process.env.GEMINI_CHAT_MODEL || "gemini-flash-lite-latest",
    error: errorArranque,
  });
});

app.get("/api/frecuentes", (req, res) => {
  res.json({ frecuentes: FRECUENTES, recientes: RECIENTES });
});

app.post("/api/consultar", async (req, res) => {
  try {
    if (!buscador) {
      return res.status(503).json({ error: errorArranque || "El buscador no está disponible." });
    }
    const consulta = (req.body?.consulta || "").toString().trim();
    if (!consulta) {
      return res.status(400).json({ error: "Falta el campo 'consulta'." });
    }
    const k = Math.min(Math.max(parseInt(req.body?.k, 10) || 5, 1), 10);

    const { fuentes: fragmentos, fueraDeDominio } = await buscador.buscar(consulta, k, true);

    let respuesta;
    if (fueraDeDominio) {
      respuesta =
        "Tu consulta no parece estar cubierta por el Código Nacional de Seguridad y Convivencia Ciudadana (Ley 1801 de 2016), que es el único tema que puedo atender. Te recomiendo reformular la pregunta o consultar directamente con la autoridad competente (una inspección de policía o un abogado).";
    } else {
      respuesta = await generarRespuesta({
        system: SYSTEM_PROMPT,
        prompt: construirPrompt(consulta, fragmentos),
      });
    }

    res.json({
      consulta,
      respuesta,
      fuera_de_dominio: fueraDeDominio,
      fuentes: fragmentos,
    });
  } catch (err) {
    console.error("Error en /api/consultar:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`API LexPolicía escuchando en http://localhost:${PORT}`);
});
