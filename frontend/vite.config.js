import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    // some deps expect a global for browser builds
    global: "globalThis",
  },
});
