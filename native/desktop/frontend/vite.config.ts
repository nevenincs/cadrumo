import { buildPath } from "../scripts/build-paths.mjs";
import { identity as readIdentity, server } from "../scripts/configuration.mjs";
import { docsFixture } from "./dev/docs-fixture/plugin.ts";
import { productBoundary } from "./dev/product-boundary.ts";
import { existsSync } from "node:fs";
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

// The shell's two generated inputs, by the names the shell imports them
// under. They are outputs of the build directory in use, so one build's are
// never another's and nothing generated is written into the source tree.
const GENERATED_INPUTS: Record<string, string> = {
  "virtual:desktop-strings": "chrome-strings.json",
  "virtual:desktop-palette.css": "palette.css",
};

export default defineConfig(({ mode }) => {
  const identity = readIdentity();
  const generated = buildPath("desktop_frontend_generated");
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
  // `--mode scenarios` builds the development entry instead, minified, into
  // the testing directory. It is what the benchmarks measure, because a
  // development server's unminified modules are not what ships; it is never
  // the product and nothing packages it.
  const scenarios = mode === "scenarios";
  // The product has one entry. The development entry beside it is never an
  // input of the product build, and the boundary plugin refuses its modules
  // by any route.
  const input: Record<string, string> = scenarios
    ? { scenarios: resolve(root, "scenarios.html") }
    : { index: resolve(root, "index.html") };
  return {
    base: "./",
    cacheDir: buildPath("desktop_cache"),
    build: {
      outDir: scenarios
        ? resolve(buildPath("desktop_testing"), "scenarios")
        : buildPath("desktop_frontend"),
      // The desktop package embeds this whole directory, so nothing from an
      // earlier build may be left in it.
      emptyOutDir: true,
      rolldownOptions: { input },
    },
    server: {
      host: ports.host,
      allowedHosts,
      port: ports.devPort,
      strictPort: true,
      // The shell's typefaces are the documentation's own files, outside
      // this project, so that directory of public assets is served as well.
      fs: { allow: [root, docsStatic, generated] },
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
      ...(scenarios ? [] : [productBoundary(root)]),
      {
        name: "desktop-generated-inputs",
        enforce: "pre",
        resolveId(id) {
          const name = GENERATED_INPUTS[id];
          if (!name) return;
          const file = resolve(generated, name);
          if (!existsSync(file))
            this.error(
              `${name} has not been generated in ${generated}. Run "npm run bootstrap".`,
            );
          // The file itself: it is then watched and transformed as any
          // stylesheet or JSON module is.
          return file;
        },
      },
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
