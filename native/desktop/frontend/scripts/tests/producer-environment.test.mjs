import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { delimiter, resolve } from "node:path";
import test from "node:test";
import { buildPath } from "../../../scripts/build-paths.mjs";
import { producerEnvironment } from "../producer-environment.mjs";

const repository = resolve(import.meta.dirname, "../../../../..");
const testing = buildPath("desktop_testing");
mkdirSync(testing, { recursive: true });

// A checkout whose src holds its own cadrumo package, as a worktree's does
// while the shared environment's editable install points at another checkout.
function plantedCheckout(t) {
  const root = mkdtempSync(resolve(testing, "producer-environment-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(resolve(root, "src", "cadrumo"), { recursive: true });
  writeFileSync(resolve(root, "src", "cadrumo", "__init__.py"), "");
  return root;
}

function importedCadrumo(environment) {
  const run = spawnSync(
    "uv",
    [
      "run",
      "--no-sync",
      "python",
      "-B",
      "-c",
      "import cadrumo; print(cadrumo.__file__)",
    ],
    { cwd: repository, env: environment, encoding: "utf8", windowsHide: true },
  );
  if (run.error) throw run.error;
  assert.equal(run.status, 0, run.stderr);
  return resolve(run.stdout.trim());
}

test("a producer imports cadrumo from the checkout it was launched for", (t) => {
  const checkout = plantedCheckout(t);

  const imported = importedCadrumo(producerEnvironment(checkout));

  assert.equal(imported, resolve(checkout, "src", "cadrumo", "__init__.py"));
});

test("a caller's path that names only a checkout root still puts its src first", (t) => {
  const checkout = plantedCheckout(t);
  const inherited = { ...process.env, PYTHONPATH: checkout };

  const environment = producerEnvironment(checkout, inherited);

  assert.deepEqual(environment.PYTHONPATH.split(delimiter), [
    resolve(checkout, "src"),
    checkout,
  ]);
  assert.equal(
    importedCadrumo(environment),
    resolve(checkout, "src", "cadrumo", "__init__.py"),
  );
});

test("the caller's own path entries are kept after the checkout's, once each", () => {
  const checkout = resolve(testing, "checkout");
  const elsewhere = resolve(testing, "elsewhere");

  const environment = producerEnvironment(checkout, {
    PYTHONPATH: [elsewhere, checkout].join(delimiter),
  });

  assert.deepEqual(environment.PYTHONPATH.split(delimiter), [
    resolve(checkout, "src"),
    checkout,
    elsewhere,
  ]);
});
