import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev (`npm run dev`), proxy API + tracking routes to the backend on :8080
// so the SPA and API appear same-origin (cookies + CSRF just work).
// In build, output to dist/ which the FastAPI backend serves in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/t": "http://127.0.0.1:8080",
      "/c": "http://127.0.0.1:8080",
      "/p": "http://127.0.0.1:8080",
      "/r": "http://127.0.0.1:8080",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
