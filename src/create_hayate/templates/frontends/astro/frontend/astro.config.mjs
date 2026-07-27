import preact from "@astrojs/preact";
import { defineConfig } from "astro/config";

const backendOrigin = process.env.HAYATE_DEV_ORIGIN || "http://127.0.0.1:8000";
const proxy = {
  "/api": {
    target: backendOrigin,
    changeOrigin: true,
  },
  "/openapi.json": {
    target: backendOrigin,
    changeOrigin: true,
  },
  "/docs": {
    target: backendOrigin,
    changeOrigin: true,
  },
};

export default defineConfig({
  output: "static",
  prerenderConflictBehavior: "error",
  integrations: [preact()],
  server: {
    host: "127.0.0.1",
    port: 4321,
  },
  vite: {
    server: { proxy },
    preview: { proxy },
  },
});
