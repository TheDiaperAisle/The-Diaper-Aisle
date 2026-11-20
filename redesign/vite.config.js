import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Built to ../v2 so GitHub Pages serves it at /The-Diaper-Aisle/v2/; it reads the live ../data/ files.
export default defineConfig({ plugins: [react()], base: "./", build: { outDir: "../v2", emptyOutDir: true } });
