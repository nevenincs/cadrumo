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

// The shell's generated inputs, by the names the shell imports them
// under. They are outputs of the build directory in use, so one build's are
// never another's and nothing generated is written into the source tree.
const GENERATED_INPUTS: Record<string, string> = {
  "virtual:desktop-strings": "chrome-strings.json",
  "virtual:desktop-palette.css": "palette.css",
  "virtual:desktop-provider-icons": "provider-icons.json",
  "virtual:desktop-navigation": "navigation.json",
};

export default defineConfig(({ command, mode }) => {
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
  // development server's unminified modules are not what ships, and what the
  // browser scenarios run against, served by `vite preview`, because nothing
  // in a build watches the source tree. It is never the product and nothing
  // packages it. Every server of this mode belongs to the browser tests and
  // has ports of its own, so a test run neither meets nor reuses the server
  // a developer has open.
  const scenarios = mode === "scenarios";
  const listening = scenarios
    ? { server: ports.hotPort, preview: ports.scenariosPort }
    : { server: ports.devPort, preview: ports.previewPort };
  // The product has a workspace and a lightweight loading entry. The development entry beside it is never an
  // input of the product build, and the boundary plugin refuses its modules
  // by any route.
  const input: Record<string, string> = scenarios
    ? { scenarios: resolve(root, "scenarios.html") }
    : {
        index: resolve(root, "index.html"),
        startup: resolve(root, "startup.html"),
      };
  return {
    base: "./",
    // A development server keeps its optimized dependencies here, keyed by the
    // mode among other things, and a server of another mode would discard them.
    // The test server of mode scenarios has its own, so it cannot make the
    // display a developer has open reload.
    cacheDir: scenarios
      ? resolve(buildPath("desktop_cache"), "scenarios")
      : buildPath("desktop_cache"),
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
      port: listening.server,
      strictPort: true,
      // The shell's typefaces are the documentation's own files, outside
      // this project, so that directory of public assets is served as well.
      fs: { allow: [root, docsStatic, generated] },
    },
    preview: {
      host: ports.host,
      allowedHosts,
      port: listening.preview,
      strictPort: true,
    },
    resolve: { alias: { "@": source } },
    plugins: [
      {
        name: "desktop-server-ports",
        configResolved(config) {
          if (
            config.server.port !== listening.server ||
            config.preview.port !== listening.preview ||
            config.server.strictPort !== true ||
            config.preview.strictPort !== true
          )
            throw new Error(
              "Desktop server ports are fixed by just dev; port overrides and fallback are not supported.",
            );
        },
      },
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
              `${name} has not been generated in ${generated}. Build the desktop-frontend-generated target, or run just dev.`,
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
          if (command === "build")
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
