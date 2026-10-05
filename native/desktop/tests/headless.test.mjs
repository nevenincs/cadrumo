import { buildPath } from "../scripts/build-paths.mjs";
import { executable } from "../scripts/configuration.mjs";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve, isAbsolute } from "node:path";

const build = process.env.CADRUMO_CMAKE_BINARY_DIR;
const root = process.env.CADRUMO_DESKTOP_PACKAGE_ROOT;
const contractPath = process.env.CADRUMO_NATIVE_CONTRACT;
assert(build && isAbsolute(build) && root && isAbsolute(root) && contractPath);
const contract = JSON.parse(readFileSync(contractPath, "utf8"));
const interpreter = resolve(root, contract.layout.paths.executable);
const host = executable();
const cwd = resolve(buildPath("desktop_testing"), "headless");
mkdirSync(cwd, { recursive: true });
const env = {
  ...process.env,
  CADRUMO_LOCAL_STORAGE_ROOT: resolve(cwd, "storage"),
  CADRUMO_LOG_DIR: resolve(cwd, "logs"),
  PYTHONHOME: "Z:/hostile-python",
  PYTHONPATH: "Z:/hostile-imports",
};
const script = readFileSync(
  new URL("../src-tauri/src/python/cli.py", import.meta.url),
  "utf8",
);
assert(script, "Use the host's exact installed entrypoint bootstrap");
function run(file, args) {
  const result = spawnSync(file, args, {
    cwd,
    env,
    input: Buffer.alloc(0),
    timeout: 120000,
    windowsHide: true,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null);
  return result;
}
for (const args of [
  ["--version"],
  ["--help"],
  ["unrecognized-command-á漢"],
  [],
]) {
  const expected = run(interpreter, ["-u", "-c", script, ...args]);
  const actual = run(host, ["--headless", "--", ...args]);
  assert.equal(actual.status, expected.status, JSON.stringify(args));
  assert.deepEqual(
    actual.stdout,
    expected.stdout,
    `stdout ${JSON.stringify(args)}`,
  );
  assert.deepEqual(
    actual.stderr,
    expected.stderr,
    `stderr ${JSON.stringify(args)}`,
  );
  console.log(`Explicit headless parity passed: ${JSON.stringify(args)}`);
  if (args.length) {
    const automatic = run(host, args);
    assert.equal(automatic.status, expected.status);
    assert.deepEqual(automatic.stdout, expected.stdout);
    assert.deepEqual(automatic.stderr, expected.stderr);
  }
}
if (process.env.CADRUMO_TEST_HEADLESS_SESSION === "1") {
  const expected = run(interpreter, ["-u", "-c", script]);
  const automatic = run(host, []);
  assert.equal(automatic.status, expected.status);
  assert.deepEqual(automatic.stdout, expected.stdout);
  assert.deepEqual(automatic.stderr, expected.stderr);
  const forced = run(host, ["--gui"]);
  assert.equal(forced.status, 69);
  assert.equal(JSON.parse(forced.stderr).code, "desktop_unavailable");
  assert.equal(forced.stdout.length, 0);
}
const invalid = run(host, ["--gui", "--help"]);
assert.equal(invalid.status, 64);
assert.equal(JSON.parse(invalid.stderr).code, "invalid_arguments");
const records = readFileSync(resolve(cwd, "logs/cadrumo-native.jsonl"), "utf8")
  .trim()
  .split("\n")
  .map(JSON.parse);
assert(records.some((record) => record.kind === "headless_selected"));
assert(
  records.some(
    (record) => record.kind === "child_exited" && record.status?.role === "cli",
  ),
);
assert(!JSON.stringify(records).includes("hostile-imports"));
console.log(
  "Real installed CLI: exact stdout/stderr/exit parity, Unicode arguments, hostile Python environment, logs and launch guards passed.",
);
