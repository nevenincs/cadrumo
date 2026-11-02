// Regenerates the desktop's ledger enums and field masks from the Python
// models that own them, through scripts/ledger_contract.py, and formats what
// it writes as the frontend's formatter does. `--check` writes nothing: it
// fails when src/shell/ledgerContract.ts, or the file `--target` names,
// differs from fresh output.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";

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
  : resolve(frontend, "src/shell/ledgerContract.ts");
const producer = resolve(frontend, "scripts/ledger_contract.py");

const environment = { ...process.env };
environment.PYTHONPATH = repository;

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
const fresh = await format(run.stdout, { ...options, filepath: contract });

if (values.check) {
  const stored = existsSync(contract)
    ? readFileSync(contract, "utf8").replaceAll("\r\n", "\n")
    : "";
  if (stored !== fresh) {
    console.error(
      `${values.target ?? "src/shell/ledgerContract.ts"} is stale; run node scripts/ledger-contract.mjs`,
    );
    process.exit(1);
  }
  process.exit(0);
}

writeFileSync(contract, fresh);
console.log(`wrote ${values.target ?? "src/shell/ledgerContract.ts"}`);
