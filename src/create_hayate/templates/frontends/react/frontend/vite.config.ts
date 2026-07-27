import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendOrigin =
    process.env.HAYATE_DEV_ORIGIN || env.HAYATE_DEV_ORIGIN || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: {
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
      },
    },
  };
});
