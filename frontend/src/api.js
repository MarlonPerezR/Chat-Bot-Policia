// Cliente de la API del backend. En desarrollo, Vite redirige /api al Express.

export async function consultar(consulta, k = 5) {
  const res = await fetch("/api/consultar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consulta, k }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Error ${res.status} del servidor`);
  }
  return data; // { consulta, respuesta, fuera_de_dominio, fuentes: [...] }
}

export async function getFrecuentes() {
  const res = await fetch("/api/frecuentes");
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json(); // { frecuentes: [...], recientes: [...] }
}

export async function getHealth() {
  const res = await fetch("/api/health");
  return res.json();
}
