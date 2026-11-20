import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Built into the repo root: GitHub Pages serves index.html at /The-Diaper-Aisle/ and the bundle from app/.
// Only index.html and app/ are written (emptyOutDir off: the root holds data/, pipeline/ and the rest).
export default defineConfig({ plugins: [react()], base: "./", build: { outDir: "..", emptyOutDir: false, assetsDir: "app" } });
