// Recuperación de fragmentos de la Ley 1801 de 2016.
//
// Dos motores, selección automática:
//   - SEMÁNTICO: si existe data/embeddings.json COMPLETO (1 vector por fragmento),
//     busca por similitud coseno embebiendo la consulta con Gemini.
//   - LÉXICO (BM25): si no hay embeddings completos, indexa el texto en memoria.
//     No consume cuota de Gemini (útil mientras el cupo gratuito de embeddings
//     está agotado). La respuesta la sigue redactando el modelo de chat.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { embedOne } from "./gemini.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CORPUS_PATH = path.join(__dirname, "data", "corpus.json");
const EMB_PATH = path.join(__dirname, "data", "embeddings.json");

// Umbral de coseno por debajo del cual la consulta probablemente no está en el
// Código (solo motor semántico).
export const UMBRAL_FUERA_DE_DOMINIO = 0.62;

// Texto que representa a cada fragmento. Replica la estrategia "fragmento" del
// motor original: artículo + epígrafe + texto.
export function textoParaEmbedding(frag) {
  const art = frag.articulo ? `Artículo ${frag.articulo}.` : "";
  const epi = frag.epigrafe ? ` ${frag.epigrafe}.` : "";
  return `${art}${epi} ${frag.texto}`.trim();
}

export function cargarCorpus() {
  if (!fs.existsSync(CORPUS_PATH)) throw new Error(`No se encontró el corpus en ${CORPUS_PATH}`);
  return JSON.parse(fs.readFileSync(CORPUS_PATH, "utf-8"));
}

function salidaFragmento(frag, puntaje) {
  return {
    puntaje: Math.round(puntaje * 10000) / 10000,
    identificador: frag.identificador,
    articulo: frag.articulo,
    norma: frag.norma,
    epigrafe: frag.epigrafe,
    texto: frag.texto,
    estado_vigencia: frag.estado_vigencia,
    ubicacion_jerarquica: frag.ubicacion_jerarquica,
    notas: frag.notas || [],
  };
}

// ---------- utilidades de texto (BM25) ----------

const STOPWORDS = new Set(
  ("de la que el en y a los del se las por un para con no una su al lo como mas " +
    "pero sus le ya o este si porque esta entre cuando muy sin sobre tambien me " +
    "hasta hay donde quien desde todo nos durante todos uno les ni contra otros " +
    "ese eso ante ellos e esto mi antes algunos que unos yo otro otras otra el " +
    "tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas " +
    "algo nosotros mi mis tu te ti tus ellas nosotras vosotros vosotras os mio " +
    "mia mios mias tuyo tuya suyo suya nuestro nuestra vuestro es son ser cual " +
    "cuales esa ese cada puede pueden debe deben").split(/\s+/)
);

function normalizar(texto) {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, ""); // quita tildes/diacríticos
}

function tokenizar(texto) {
  return (normalizar(texto).match(/[a-z0-9ñ]+/g) || []).filter(
    (w) => w.length >= 2 && !STOPWORDS.has(w)
  );
}

// ---------- motor semántico ----------

class MotorSemantico {
  constructor(corpus, cache) {
    this.corpus = corpus;
    this.vectores = cache.vectores;
  }
  async buscar(consulta, k, excluirInexequibles) {
    const q = await embedOne(consulta, "RETRIEVAL_QUERY");
    const cos = (a, b) => {
      let d = 0, na = 0, nb = 0;
      for (let i = 0; i < a.length; i++) { d += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
      return na && nb ? d / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
    };
    const rank = this.corpus
      .map((frag, i) => ({ s: cos(q, this.vectores[i]), frag }))
      .sort((a, b) => b.s - a.s);
    const topCrudo = rank.length ? rank[0].s : 0;
    const fuentes = [];
    for (const { s, frag } of rank) {
      if (excluirInexequibles && frag.estado_vigencia === "inexequible") continue;
      fuentes.push(salidaFragmento(frag, s));
      if (fuentes.length === k) break;
    }
    return { fuentes, fueraDeDominio: topCrudo < UMBRAL_FUERA_DE_DOMINIO, modo: "semantico" };
  }
}

// ---------- motor léxico (BM25) ----------

class MotorLexico {
  constructor(corpus) {
    this.corpus = corpus;
    this.k1 = 1.5;
    this.b = 0.75;
    this.N = corpus.length;
    this.df = new Map();
    this.docs = corpus.map((frag) => {
      const toks = tokenizar(`${textoParaEmbedding(frag)} ${frag.tema || ""}`);
      const tf = new Map();
      for (const w of toks) tf.set(w, (tf.get(w) || 0) + 1);
      for (const w of tf.keys()) this.df.set(w, (this.df.get(w) || 0) + 1);
      return { tf, len: toks.length };
    });
    this.avgdl = this.docs.reduce((s, d) => s + d.len, 0) / (this.N || 1);
  }

  idf(term) {
    const df = this.df.get(term) || 0;
    return Math.log(1 + (this.N - df + 0.5) / (df + 0.5));
  }

  async buscar(consulta, k, excluirInexequibles) {
    const qTerms = [...new Set(tokenizar(consulta))];
    const rank = this.docs.map((doc, i) => {
      let s = 0;
      for (const term of qTerms) {
        const f = doc.tf.get(term);
        if (!f) continue;
        s += this.idf(term) * (f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + this.b * (doc.len / this.avgdl)));
      }
      return { s, frag: this.corpus[i] };
    });
    rank.sort((a, b) => b.s - a.s);
    const topCrudo = rank.length ? rank[0].s : 0;

    const fuentes = [];
    for (const { s, frag } of rank) {
      if (s <= 0) break; // sin solape léxico
      if (excluirInexequibles && frag.estado_vigencia === "inexequible") continue;
      // Normaliza a 0-1 relativo al mejor resultado, para mostrar "% afinidad".
      fuentes.push(salidaFragmento(frag, topCrudo > 0 ? s / topCrudo : 0));
      if (fuentes.length === k) break;
    }
    return { fuentes, fueraDeDominio: topCrudo <= 0, modo: "lexico" };
  }
}

// ---------- fábrica ----------

export function crearBuscador() {
  const corpus = cargarCorpus();
  if (fs.existsSync(EMB_PATH)) {
    try {
      const cache = JSON.parse(fs.readFileSync(EMB_PATH, "utf-8"));
      if (Array.isArray(cache.vectores) && cache.vectores.length === corpus.length) {
        return { motor: new MotorSemantico(corpus, cache), corpus, modo: "semantico" };
      }
    } catch {}
  }
  return { motor: new MotorLexico(corpus), corpus, modo: "lexico" };
}
