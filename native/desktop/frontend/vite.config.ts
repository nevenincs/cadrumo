import { buildPath } from "../scripts/build-paths.mjs";
import { identity as readIdentity, server } from "../scripts/configuration.mjs";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const identity = readIdentity();
  const ports = server();
  const environment = loadEnv(
    mode,
    fileURLToPath(new URL(".", import.meta.url)),
    "CADRUMO_DESKTOP_",
  );
  const allowedHosts = (
    process.env.CADRUMO_DESKTOP_ALLOWED_HOSTS ??
    environment.CADRUMO_DESKTOP_ALLOWED_HOSTS ??
    ""
  )
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
  return {
    base: "./",
    cacheDir: buildPath("desktop_cache"),
    build: {
      outDir: buildPath("desktop_frontend"),
      emptyOutDir: false,
    },
    server: {
      host: ports.host,
      allowedHosts,
      port: ports.devPort,
      strictPort: true,
    },
    preview: {
      host: ports.host,
      allowedHosts,
      port: ports.previewPort,
      strictPort: true,
    },
    plugins: [
      react(),
      {
        name: "canonical-desktop-content",
        transformIndexHtml() {
          return [{ tag: "title", children: identity.name, injectTo: "head" }];
        },
        resolveId(id) {
          if (id === "virtual:desktop-content") return "\0desktop-content";
        },
        load(id) {
          if (id !== "\0desktop-content") return;
          this.emitFile({
            type: "asset",
            fileName: "identity.json",
            source: JSON.stringify(identity),
          });
          return `export const identity = ${JSON.stringify(identity)};`;
        },
      },
    ],
  };
});
