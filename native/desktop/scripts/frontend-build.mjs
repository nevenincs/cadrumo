import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "./build-paths.mjs";
import { contentBuild } from "./content-build.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const frontend = resolve(desktop, "frontend");
// TypeScript checks every configured source tree, including development/test
// code. Dependency content is pinned by the lockfile and checked by install.
const inputs = readdirSync(frontend)
  .filter(
    (name) =>
      [
        "src",
        "dev",
        "scripts",
        "tests",
        ".storybook",
        "public",
        "index.html",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "vite.config.ts",
        "playwright.config.ts",
      ].includes(name) || name.startsWith(".env"),
  )
  .map((name) => resolve(frontend, name));
// Resolve TypeScript's complete extends chain, including configurations outside
// the frontend and node_modules. The compiler itself owns JSONC/path semantics.
const require = createRequire(resolve(frontend, "package.json"));
const ts = require("typescript");
const extended = new Map();
const config = ts.getParsedCommandLineOfConfigFile(
  resolve(frontend, "tsconfig.json"),
  {},
  {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
      throw new Error(
        ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"),
      );
    },
  },
  extended,
);
if (config?.errors.length)
  throw new Error(
    ts.formatDiagnosticsWithColorAndContext(config.errors, {
      getCurrentDirectory: ts.sys.getCurrentDirectory,
      getCanonicalFileName: (file) => file,
      getNewLine: () => "\n",
    }),
  );
inputs.push(...extended.keys(), ...(config?.fileNames ?? []));
inputs.push(
  process.execPath,
  process.argv[2],
  resolve(dirname(process.argv[2]), "../package.json"),
  ...[
    "frontend-build.mjs",
    "content-build.mjs",
    "build-paths.mjs",
    "configuration.mjs",
  ].map((name) => resolve(desktop, "scripts", name)),
  ...readdirSync(resolve(desktop, "../../docs/_static"))
    .filter((name) => name.endsWith(".woff2"))
    .map((name) => resolve(desktop, "../../docs/_static", name)),
  resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
  buildPath("desktop_frontend_generated"),
  resolve(buildPath("generated"), "identity.json"),
  resolve(buildPath("generated"), "desktop-server.json"),
);
const changed = contentBuild(
  {
    inputs,
    outputs: [
      buildPath("desktop_frontend"),
      resolve(buildPath("desktop_frontend"), "index.html"),
    ],
    record: resolve(buildPath("desktop_cache"), "frontend-build.json"),
    identity: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
      environment: Object.fromEntries(
        Object.entries(process.env).filter(
          ([key]) =>
            key.startsWith("VITE_") ||
            key.startsWith("CADRUMO_DESKTOP_") ||
            ["NODE_ENV", "NODE_OPTIONS"].includes(key),
        ),
      ),
    },
  },
  () => {
    const result = spawnSync(
      process.execPath,
      [process.argv[2], "run", "build"],
      {
        cwd: frontend,
        stdio: "inherit",
        windowsHide: true,
      },
    );
    if (result.error) throw result.error;
    if (result.status !== 0)
      throw new Error(`Frontend build failed: ${result.status}`);
  },
);
console.log(`Frontend assets: ${changed ? "built" : "unchanged"}.`);
