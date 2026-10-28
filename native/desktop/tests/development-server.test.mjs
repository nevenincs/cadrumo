import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";
import {
  developmentServer,
  PORT_KEYS,
} from "../scripts/development-server.mjs";
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
  for (const key of PORT_KEYS) assert.equal(configured[key], fixed[key]);
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

test("the browser tests serve on ports of their own, equally fixed", async () => {
  const fixed = developmentServer();
  for (const [mode, server, preview] of [
    ["development", fixed.devPort, fixed.previewPort],
    ["scenarios", fixed.hotPort, fixed.scenariosPort],
  ]) {
    const config = await resolveConfig({ root: frontend, mode }, "serve");
    assert.equal(config.server.port, server);
    assert.equal(config.preview.port, preview);
    assert.equal(config.server.strictPort, true);
    assert.equal(config.preview.strictPort, true);
  }
  // A test server may not take the display's port, or the display the test's.
  for (const [mode, override] of [
    ["scenarios", { server: { port: fixed.devPort } }],
    ["scenarios", { preview: { port: fixed.previewPort } }],
    ["development", { server: { port: fixed.hotPort } }],
    ["development", { preview: { port: fixed.scenariosPort } }],
  ])
    await assert.rejects(
      resolveConfig({ root: frontend, mode, ...override }, "serve"),
      /ports are fixed by just dev/,
    );
});

test("development display and catalogue reject legacy port override options", () => {
  for (const [script, args] of [
    ["dev.mjs", ["--dev-port", "25420"]],
    ["dev.mjs", ["--preview-port", "25421"]],
    ["dev.mjs", ["--build-dir", "build"]],
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
