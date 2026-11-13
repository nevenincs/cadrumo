// Regenerates the desktop's ledger operation wire types from the JSON schema
// of the registered Python models, through
// scripts/ledger_operation_contract.py, and formats what it writes as the
// frontend's formatter does. `--check` writes nothing: it fails when a module
// named below differs from fresh output. It refuses, writing and comparing
// nothing, when a formatted module would be longer than the module bound the
// producer reports.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";
import { refuseOversizedModules } from "./generated-module-bound.mjs";
import { producerEnvironment } from "./producer-environment.mjs";

const { values } = parseArgs({
  options: { check: { type: "boolean", default: false } },
});

// The module of each family the producer writes, by family name.
const outputs = {
  classification: "src/shell/ledgerClassificationContract.ts",
};

const frontend = fileURLToPath(new URL("..", import.meta.url));
const repository = resolve(frontend, "../../..");
const producer = resolve(frontend, "scripts/ledger_operation_contract.py");

const run = spawnSync("uv", ["run", "--no-sync", "python", "-B", producer], {
  cwd: repository,
  env: producerEnvironment(repository),
  encoding: "utf8",
  maxBuffer: 16 * 1024 * 1024,
  windowsHide: true,
  stdio: ["ignore", "pipe", "inherit"],
});
if (run.error) throw run.error;
if ((run.status ?? 1) !== 0) process.exit(run.status ?? 1);

const { bound, modules } = JSON.parse(run.stdout);
const families = Object.keys(modules).sort();
if (families.join() !== Object.keys(outputs).sort().join()) {
  console.error(
    `the producer writes ${families.join(", ")}; this driver names ${Object.keys(outputs).join(", ")}`,
  );
  process.exit(1);
}

const fresh = {};
for (const family of families) {
  const path = resolve(frontend, outputs[family]);
  const options = (await resolveConfig(path)) ?? {};
  fresh[family] = await format(modules[family], { ...options, filepath: path });
}
refuseOversizedModules(
  families.map((family) => [basename(outputs[family]), fresh[family]]),
  bound,
  "split what scripts/ledger_operation_contract.py emits",
);

if (values.check) {
  let stale = false;
  for (const family of families) {
    const path = resolve(frontend, outputs[family]);
    const stored = existsSync(path)
      ? readFileSync(path, "utf8").replaceAll("\r\n", "\n")
      : "";
    if (stored !== fresh[family]) {
      console.error(
        `${outputs[family]} is stale; run node scripts/ledger-operation-contract.mjs`,
      );
      stale = true;
    }
  }
  process.exit(stale ? 1 : 0);
}

for (const family of families) {
  writeFileSync(resolve(frontend, outputs[family]), fresh[family]);
  console.log(`wrote ${outputs[family]}`);
}
