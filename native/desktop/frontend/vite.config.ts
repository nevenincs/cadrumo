import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir)) {
  throw new Error(
    "Set CADRUMO_CMAKE_BINARY_DIR to the absolute selected CMake build directory.",
  );
}

export default defineConfig({
  base: "./",
  cacheDir: resolve(binaryDir, "desktop/vite-cache"),
  build: { outDir: resolve(binaryDir, "desktop/frontend"), emptyOutDir: false },
  server: { port: 1420, strictPort: true },
  preview: { port: 1421, strictPort: true },
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
        const directory = resolve(root, "docs/explanation");
        const chapters = readdirSync(directory)
          .filter((name) =>
            [
              "from-records-to-figures.md",
              "editing-and-verifying.md",
              "reviewing-and-exporting.md",
              "recording-a-filing-and-the-boundary.md",
              "building-on-earlier-filings.md",
            ].includes(name),
          )
          .map((name) => {
            const path = resolve(directory, name);
            this.addWatchFile(path);
            const source = readFileSync(path, "utf8");
            if (/```\{/.test(source))
              throw new Error(
                `Sphinx directive requires the full documentation build: ${path}`,
              );
            const markdown = source
              .replace(/^\([^\n]+\)=\r?\n/gm, "")
              .replace(/\{(?:term|ref|doc)\}`([^`]+)`/g, (_, label: string) =>
                label.replace(/\s*<[^>]+>$/, ""),
              );
            return {
              id: name.slice(0, -3),
              title: source.match(/^# (.+)/m)?.[1]?.trim() ?? name,
              source: `docs/explanation/${name}`,
              markdown,
            };
          });
        const markPath = resolve(root, "docs/_static/cadrumo-favicon.svg");
        this.addWatchFile(markPath);
        const mark = `data:image/svg+xml;base64,${readFileSync(markPath).toString("base64")}`;
        this.emitFile({
          type: "asset",
          fileName: "identity.json",
          source: JSON.stringify(identity),
        });
        return `export const identity = ${JSON.stringify(identity)}; export const chapters = ${JSON.stringify(chapters)}; export const mark = ${JSON.stringify(mark)};`;
      },
    },
  ],
});
