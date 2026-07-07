import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy /api to the backend so there are no CORS issues locally.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_API || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: Number(process.env.PORT) || 4173,
    host: true,
  },
});
