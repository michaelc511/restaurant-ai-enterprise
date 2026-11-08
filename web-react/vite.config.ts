// F5: dev server proxies /api to engine_api.py, so the browser never makes a cross-origin call and
// engine_api.py needs no CORS setup. Override the target with API_URL=http://host:port.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
