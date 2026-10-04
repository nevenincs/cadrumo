import { buildPath } from "../scripts/build-paths.mjs";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const root = fileURLToPath(new URL("../../../", import.meta.url));
export default defineConfig(({ mode }) => {
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
    server: { host: "0.0.0.0", allowedHosts, port: 1420, strictPort: true },
    preview: { host: "0.0.0.0", allowedHosts, port: 1421, strictPort: true },
    plugins: [
      react(),
      {
        name: "canonical-desktop-content",
        resolveId(id) {
          if (id === "virtual:desktop-content") return "\0desktop-content";
        },
        load(id) {
          if (id !== "\0desktop-content") return;
          const identityPath = resolve(
            root,
            "src/cadrumo/core/product_identity.py",
          );
          this.addWatchFile(identityPath);
          const python =
            process.env.CADRUMO_DEV_PYTHON ??
            resolve(
              root,
              process.platform === "win32"
                ? ".venv/Scripts/python.exe"
                : ".venv/bin/python",
            );
          const identity = JSON.parse(
            execFileSync(
              python,
              [
                "-B",
                "-c",
                'import json,runpy,sys; print(json.dumps(runpy.run_path(sys.argv[1])["PRODUCT_IDENTITY"]._asdict()))',
                identityPath,
              ],
              { encoding: "utf8" },
            ),
          );
          const markPath = resolve(root, "docs/_static/cadrumo-favicon.svg");
          this.addWatchFile(markPath);
          const mark = `data:image/svg+xml;base64,${readFileSync(markPath).toString("base64")}`;
          this.emitFile({
            type: "asset",
            fileName: "identity.json",
            source: JSON.stringify(identity),
          });
          return `export const identity = ${JSON.stringify(identity)}; export const mark = ${JSON.stringify(mark)};`;
        },
      },
    ],
  };
});
