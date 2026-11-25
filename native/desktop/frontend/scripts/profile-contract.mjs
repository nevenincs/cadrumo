// Regenerates the desktop's profile wire types from the JSON schema of the
// registered Python models, through scripts/profile_contract.py, and formats
// what it writes as the frontend's formatter does. `--check` writes nothing:
// it fails when src/shell/profileContract.ts, or the file `--target` names,
// differs from fresh output. It refuses, writing and comparing nothing, when
// the formatted module would be longer than the module bound the producer
// reports.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";
import { refuseOversizedModules } from "./generated-module-bound.mjs";
import { producerEnvironment } from "./producer-environment.mjs";

const { values } = parseArgs({
  options: {
    check: { type: "boolean", default: false },
    target: { type: "string" },
  },
});

const frontend = fileURLToPath(new URL("..", import.meta.url));
const repository = resolve(frontend, "../../..");
const contract = values.target
  ? resolve(values.target)
  : resolve(frontend, "src/shell/profileContract.ts");
const producer = resolve(frontend, "scripts/profile_contract.py");

const environment = producerEnvironment(repository);

const run = spawnSync("uv", ["run", "--no-sync", "python", "-B", producer], {
  cwd: repository,
  env: environment,
  encoding: "utf8",
  maxBuffer: 16 * 1024 * 1024,
  windowsHide: true,
  stdio: ["ignore", "pipe", "inherit"],
});
if (run.error) throw run.error;
if ((run.status ?? 1) !== 0) process.exit(run.status ?? 1);

const options = (await resolveConfig(contract)) ?? {};
const { bound, module } = JSON.parse(run.stdout);
const fresh = await format(module, { ...options, filepath: contract });
refuseOversizedModules(
  [[basename(contract), fresh]],
  bound,
  "split what scripts/profile_contract.py emits",
);

if (values.check) {
  const stored = existsSync(contract)
    ? readFileSync(contract, "utf8").replaceAll("\r\n", "\n")
    : "";
  if (stored !== fresh) {
    console.error(
      `${values.target ?? "src/shell/profileContract.ts"} is stale; run node scripts/profile-contract.mjs`,
    );
    process.exit(1);
  }
  process.exit(0);
}

writeFileSync(contract, fresh);
console.log(`wrote ${values.target ?? "src/shell/profileContract.ts"}`);
