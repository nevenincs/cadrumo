import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";
import { developmentServer } from "../scripts/development-server.mjs";
import { server } from "../scripts/configuration.mjs";

const frontend = fileURLToPath(new URL("../frontend/", import.meta.url));
const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { resolveConfig } = await import(
  pathToFileURL(require.resolve("vite")).href
);

test("generated listener assignments match the just dev contract", () => {
  const configured = server();
  const fixed = developmentServer();
  for (const key of ["devPort", "previewPort", "docsPort", "cataloguePort"])
    assert.equal(configured[key], fixed[key]);
});

test("Vite refuses alternate ports and automatic port fallback", async () => {
  const config = await resolveConfig({ root: frontend }, "serve");
  assert.equal(config.server.strictPort, true);
  assert.equal(config.preview.strictPort, true);
  for (const override of [
    { server: { port: config.server.port + 10 } },
    { preview: { port: config.preview.port + 10 } },
    { server: { strictPort: false } },
    { preview: { strictPort: false } },
  ])
    await assert.rejects(
      resolveConfig({ root: frontend, ...override }, "serve"),
      /ports are fixed by just dev/,
    );
});

test("bootstrap and catalogue reject legacy port override options", () => {
  for (const [script, args] of [
    ["bootstrap.mjs", ["--dev-port", "25420"]],
    ["bootstrap.mjs", ["--preview-port", "25421"]],
    ["storybook.mjs", ["dev", "--port", "25422"]],
  ]) {
    const result = spawnSync(
      process.execPath,
      [
        fileURLToPath(
          new URL(`../frontend/scripts/${script}`, import.meta.url),
        ),
        ...args,
      ],
      { encoding: "utf8", windowsHide: true },
    );
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Unknown option/);
  }
});
