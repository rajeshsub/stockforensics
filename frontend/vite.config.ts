import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy API + SSE to the FastAPI backend on :8000.
// Build: emits to dist/, which FastAPI serves as static (single backend, Q14).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist" },
});
