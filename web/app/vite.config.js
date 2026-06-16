import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + client-report routes to the Flask backend on :8000,
// so the UI always calls relative paths and the engine stays the source of truth.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/r": "http://localhost:8000",
    },
  },
});
