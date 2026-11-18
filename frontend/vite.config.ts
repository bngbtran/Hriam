import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: /api (kể cả WebSocket) chuyển tới FastAPI ở cổng 8000, nên cookie refresh cùng origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: process.env.API_TARGET ?? "http://127.0.0.1:8000", changeOrigin: false, ws: true } } },
});
