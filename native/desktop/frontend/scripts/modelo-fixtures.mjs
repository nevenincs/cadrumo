// Regenerates the desktop's Modelo wire types and scenario envelopes from the
// Python models, and the relay bounds from the host's Rust sources, through
// scripts/modelo_fixtures.py, and formats what it writes as the frontend's
// formatter does. `--check` writes nothing: it fails when
// src/shell/modeloContract.ts or src/shell/relayBounds.ts differs from fresh
// output, when the host's
// admitted list differs from the registered family, or when a stored
// envelope no longer validates against its model. The envelopes are read for
// a synthetic taxpayer over the published authority under
// CADRUMO_AUTHORITY_ROOT, or the repository's `.authority` where unset.
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";

const { values } = parseArgs({
  options: {
    check: { type: "boolean", default: false },
    contract: { type: "boolean", default: false },
  },
});

const frontend = fileURLToPath(new URL("..", import.meta.url));
const repository = resolve(frontend, "../../..");
const contract = resolve(frontend, "src/shell/modeloContract.ts");
const bounds = resolve(frontend, "src/shell/relayBounds.ts");
const fixtures = resolve(frontend, "src/dev/fixtures/modelo");
const producer = resolve(frontend, "scripts/modelo_fixtures.py");
// Every envelope the producer wrote into its own scratch directory.
const ENVELOPE = /^[A-Za-z0-9-]+\.json$/;

const environment = { ...process.env };
const authority = resolve(repository, ".authority");
if (!environment.CADRUMO_AUTHORITY_ROOT && existsSync(authority))
  environment.CADRUMO_AUTHORITY_ROOT = authority;

function python(step, ...rest) {
  const run = spawnSync(
    "uv",
    ["run", "--no-sync", "python", producer, step, ...rest],
    {
      cwd: repository,
      env: environment,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
      windowsHide: true,
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  if (run.error) throw run.error;
  return { status: run.status ?? 1, output: run.stdout };
}

async function written(path, text) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      writeFileSync(path, text);
      return;
    } catch (error) {
      if (attempt === 20) throw error;
      await new Promise((done) => setTimeout(done, 250));
    }
  }
}

async function formatted(source, path) {
  const options = (await resolveConfig(path)) ?? {};
  return format(source, { ...options, filepath: path });
}

const generated = python("contract");
if (generated.status !== 0) process.exit(generated.status);
const fresh = await formatted(generated.output, contract);
const measured = python("bounds");
if (measured.status !== 0) process.exit(measured.status);
const freshBounds = await formatted(measured.output, bounds);

if (values.check) {
  let failed = false;
  const stored = existsSync(contract)
    ? readFileSync(contract, "utf8").replaceAll("\r\n", "\n")
    : "";
  if (stored !== fresh) {
    console.error(
      "src/shell/modeloContract.ts is stale; run node scripts/modelo-fixtures.mjs --contract",
    );
    failed = true;
  }
  const storedBounds = existsSync(bounds)
    ? readFileSync(bounds, "utf8").replaceAll("\r\n", "\n")
    : "";
  if (storedBounds !== freshBounds) {
    console.error(
      "src/shell/relayBounds.ts is stale; run node scripts/modelo-fixtures.mjs --contract",
    );
    failed = true;
  }
  if (python("validate").status !== 0) {
    console.error(
      "The modelo envelopes are stale; run node scripts/modelo-fixtures.mjs",
    );
    failed = true;
  }
  process.exit(failed ? 1 : 0);
}

writeFileSync(contract, fresh);
console.log("wrote src/shell/modeloContract.ts");
writeFileSync(bounds, freshBounds);
console.log("wrote src/shell/relayBounds.ts");
if (!values.contract) {
  // Read into a scratch directory, then write each envelope once, formatted:
  // a development server watching the fixtures may hold one open briefly.
  const scratch = mkdtempSync(resolve(tmpdir(), "modelo-envelopes-"));
  try {
    const read = python("envelopes", scratch);
    if (read.status !== 0) process.exit(read.status);
    const names = readdirSync(scratch).filter((name) => ENVELOPE.test(name));
    for (const name of names) {
      const path = resolve(fixtures, name);
      const source = readFileSync(resolve(scratch, name), "utf8");
      await written(path, await formatted(source, path));
    }
    console.log(`wrote ${names.length} envelopes`);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}
