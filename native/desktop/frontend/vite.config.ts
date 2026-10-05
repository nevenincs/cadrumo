import { buildPath } from "../scripts/build-paths.mjs";
import { identity as readIdentity, server } from "../scripts/configuration.mjs";
import { docsFixture } from "./dev/docs-fixture/plugin.ts";
import { productBoundary } from "./dev/product-boundary.ts";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const root = fileURLToPath(new URL(".", import.meta.url));
const source = fileURLToPath(new URL("./src", import.meta.url));
const docsStatic = fileURLToPath(
  new URL("../../../docs/_static", import.meta.url),
);

export default defineConfig(({ mode }) => {
  const identity = readIdentity();
  const ports = server();
  const environment = loadEnv(mode, root, "CADRUMO_DESKTOP_");
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
      // The product has one entry. The development entry beside it is never
      // an input, and the boundary plugin refuses its modules by any route.
      rolldownOptions: { input: { index: resolve(root, "index.html") } },
    },
    server: {
      host: ports.host,
      allowedHosts,
      port: ports.devPort,
      strictPort: true,
      // The shell's typefaces are the documentation's own files, outside
      // this project, so that directory of public assets is served as well.
      fs: { allow: [root, docsStatic] },
    },
    preview: {
      host: ports.host,
      allowedHosts,
      port: ports.previewPort,
      strictPort: true,
    },
    resolve: { alias: { "@": source } },
    plugins: [
      react(),
      tailwindcss(),
      docsFixture(),
      productBoundary(root),
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
