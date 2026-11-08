// F5: customer-facing sushi site. Same /api proxy to engine_api.py as web-react, on its own port so
// both UIs can run side by side. fs.allow lets the site link the real menu PDF in domains/ (one copy).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    fs: { allow: [".."] },
    proxy: {
      "/api": { target: API_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
