// Cliente mínimo de la API REST de Google Gemini (Generative Language API).
// Usa fetch global (Node 18+). No requiere SDK externo.

const API_BASE = "https://generativelanguage.googleapis.com/v1beta";

function apiKey() {
  const k = process.env.GEMINI_API_KEY;
  if (!k || k === "tu_api_key_aqui") {
    throw new Error(
      "Falta GEMINI_API_KEY en backend/.env. Consíguela gratis en https://aistudio.google.com"
    );
  }
  return k;
}

function embedModel() {
  return process.env.GEMINI_EMBED_MODEL || "gemini-embedding-001";
}

// Dimensión de salida de los embeddings. 768 mantiene la caché ligera y la
// búsqueda rápida sin perder apenas calidad.
const EMBED_DIM = 768;

function chatModel() {
  return process.env.GEMINI_CHAT_MODEL || "gemini-2.5-flash";
}

async function callGemini(path, body) {
  const res = await fetch(`${API_BASE}/${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": apiKey(),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Gemini ${res.status} en ${path}: ${txt.slice(0, 500)}`);
  }
  return res.json();
}

// Embebe varios textos de una sola vez. taskType mejora la recuperación:
//   RETRIEVAL_DOCUMENT para los fragmentos, RETRIEVAL_QUERY para la consulta.
// Devuelve un array de vectores (array de números).
export async function embedBatch(textos, taskType = "RETRIEVAL_DOCUMENT") {
  const model = embedModel();
  const body = {
    requests: textos.map((t) => ({
      model: `models/${model}`,
      content: { parts: [{ text: t }] },
      taskType,
      outputDimensionality: EMBED_DIM,
    })),
  };
  const data = await callGemini(`models/${model}:batchEmbedContents`, body);
  return (data.embeddings || []).map((e) => e.values);
}

// Embebe un único texto (p. ej. la consulta del usuario).
export async function embedOne(texto, taskType = "RETRIEVAL_QUERY") {
  const [v] = await embedBatch([texto], taskType);
  return v;
}

// Genera una respuesta de texto con el modelo de chat.
export async function generarRespuesta({ system, prompt, temperature = 0.2 }) {
  const model = chatModel();
  const body = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: { temperature, maxOutputTokens: 1024 },
  };
  if (system) body.systemInstruction = { parts: [{ text: system }] };
  const data = await callGemini(`models/${model}:generateContent`, body);
  const cand = data.candidates && data.candidates[0];
  const parts = cand?.content?.parts || [];
  const texto = parts.map((p) => p.text || "").join("").trim();
  if (!texto) {
    const motivo = cand?.finishReason || data.promptFeedback?.blockReason || "sin texto";
    throw new Error(`Gemini no devolvió respuesta (${motivo}).`);
  }
  return texto;
}

export const config = { embedModel, chatModel };
