// Genera la caché de embeddings de los 1.125 fragmentos del Código con la API
// de embeddings de Gemini. Se ejecuta UNA sola vez (o cuando cambie el corpus):
//   npm run build-index
//
// La capa gratuita permite ~100 embeddings/minuto, así que el script va a ese
// ritmo (lotes pequeños con pausa de ~1 min). Guarda el progreso en
// data/embeddings.partial.json para poder REANUDAR si se interrumpe.
// Al terminar escribe data/embeddings.json  { modelo, dim, vectores: number[][] }

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import "dotenv/config";
import { embedBatch, config } from "./gemini.js";
import { cargarCorpus, textoParaEmbedding } from "./retrieval.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EMB_PATH = path.join(__dirname, "data", "embeddings.json");
const PARCIAL_PATH = path.join(__dirname, "data", "embeddings.partial.json");

const LOTE = 90; // < 100/min de la capa gratuita, con margen
const PAUSA_MIN_MS = 62000; // ventana de 1 min del límite por minuto
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

function cargarParcial() {
  if (fs.existsSync(PARCIAL_PATH)) {
    try {
      const p = JSON.parse(fs.readFileSync(PARCIAL_PATH, "utf-8"));
      if (Array.isArray(p.vectores)) return p.vectores;
    } catch {}
  }
  return [];
}

async function main() {
  const corpus = cargarCorpus();
  const textos = corpus.map(textoParaEmbedding);
  const vectores = cargarParcial();
  if (vectores.length) console.log(`Reanudando: ya había ${vectores.length} vectores.`);
  console.log(`Fragmentos: ${textos.length} · modelo: ${config.embedModel()}`);

  for (let i = vectores.length; i < textos.length; i += LOTE) {
    const lote = textos.slice(i, i + LOTE);
    let intentos = 0;
    for (;;) {
      try {
        const vs = await embedBatch(lote, "RETRIEVAL_DOCUMENT");
        if (vs.length !== lote.length) throw new Error(`devolvió ${vs.length}/${lote.length}`);
        vectores.push(...vs);
        break;
      } catch (err) {
        intentos++;
        if (intentos > 8) throw err;
        const es429 = /\b429\b/.test(err.message);
        const espera = es429 ? PAUSA_MIN_MS : 1000 * Math.pow(2, intentos);
        console.warn(`  Lote ${i}: ${es429 ? "límite/min" : "error"} (reintento ${intentos}, espera ${Math.round(espera / 1000)}s)`);
        await dormir(espera);
      }
    }
    // Guardar progreso tras cada lote (permite reanudar)
    fs.writeFileSync(PARCIAL_PATH, JSON.stringify({ vectores }));
    console.log(`  ${Math.min(i + LOTE, textos.length)}/${textos.length}`);
    if (i + LOTE < textos.length) await dormir(PAUSA_MIN_MS);
  }

  const dim = vectores[0]?.length || 0;
  fs.writeFileSync(EMB_PATH, JSON.stringify({ modelo: config.embedModel(), dim, vectores }));
  if (fs.existsSync(PARCIAL_PATH)) fs.unlinkSync(PARCIAL_PATH);
  console.log(`\nListo. ${vectores.length} vectores (dim ${dim}) en ${EMB_PATH}`);
}

main().catch((err) => {
  console.error("\nError generando el índice:", err.message);
  console.error("Puedes reanudar volviendo a ejecutar: npm run build-index");
  process.exit(1);
});
