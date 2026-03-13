import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ["recharts"],
          radix: [
            "@radix-ui/react-tabs",
            "@radix-ui/react-accordion",
            "@radix-ui/react-progress",
          ],
        },
      },
    },
  },
  server: {
    port: 22002,
    proxy: {
      "/api": {
        target: `http://localhost:${process.env.VITE_API_PORT || "22012"}`,
        changeOrigin: true,
      },
    },
  },
});
