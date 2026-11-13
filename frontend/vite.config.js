import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El front llama a /api/* y Vite lo redirige al backend Express (puerto 3001),
// así no hay problemas de CORS en desarrollo.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:3001",
        changeOrigin: true,
      },
    },
  },
});
