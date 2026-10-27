import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api is proxied to the backend so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: { "/api": { target: process.env.VITE_PROXY_TARGET || "http://localhost:8000", changeOrigin: true } },
  },
  test: { environment: "jsdom", setupFiles: ["./src/setupTests.js"], globals: true },
});
