// Regenerates the desktop's Modelo wire types, scenario envelopes and relay
// bounds from the Python models and the host's Rust sources, through
// scripts/modelo_fixtures.py, and formats what it writes as the frontend's
// formatter does. `--contract` selects the wire types and relay bounds
// (src/shell/modeloContract.ts and relayBounds.ts, committed); `--envelopes`
// selects the scenario envelopes, which are build output in the host's build
// tree (see fixture-paths.mjs) and never committed; with neither, both. The
// envelopes are stored as the producer writes them, compact and the Modelo 100
// forms as patches; `--pack` stores the ones already on disk that way.
// `--check` writes nothing: for the wire types it fails when they differ from
// fresh output or the host's admitted list differs from the registered family,
// and for the envelopes it fails when a stored one no longer validates against
// its model, having nothing to check while none is seeded. `--output DIR`
// writes what was selected into an existing directory instead, which is how a
// determinism proof builds twice. The envelopes are read for synthetic
// taxpayers over the published authority under CADRUMO_AUTHORITY_ROOT, or the
// repository's `.authority` where unset.
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";
import { windowFixtures } from "./fixture-paths.mjs";

const { values } = parseArgs({
  options: {
    check: { type: "boolean", default: false },
    contract: { type: "boolean", default: false },
    envelopes: { type: "boolean", default: false },
    pack: { type: "boolean", default: false },
    output: { type: "string" },
  },
});
const wireTypes = values.contract || !values.envelopes;
const scenarios = values.envelopes || !values.contract;

const frontend = fileURLToPath(new URL("..", import.meta.url));
const repository = resolve(frontend, "../../..");
const contract = resolve(frontend, "src/shell/modeloContract.ts");
const bounds = resolve(frontend, "src/shell/relayBounds.ts");
const fixtures = resolve(windowFixtures(), "modelo");
const producer = resolve(frontend, "scripts/modelo_fixtures.py");
// Every envelope the producer wrote into its own scratch directory.
const ENVELOPE = /^[A-Za-z0-9-]+\.json$/;

const environment = { ...process.env };
environment.PYTHONPATH = repository;
const authority = resolve(repository, ".authority");
if (!environment.CADRUMO_AUTHORITY_ROOT && existsSync(authority))
  environment.CADRUMO_AUTHORITY_ROOT = authority;

function python(step, ...rest) {
  const run = spawnSync(
    "uv",
    ["run", "--no-sync", "python", "-B", producer, step, ...rest],
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

if (values.output && !existsSync(values.output)) {
  console.error(`--output ${values.output} is not an existing directory`);
  process.exit(1);
}

if (values.pack) {
  process.exit(python("pack", fixtures).status);
}

let failed = false;
if (wireTypes) {
  const generated = python("contract");
  if (generated.status !== 0) process.exit(generated.status);
  const fresh = await formatted(generated.output, contract);
  const measured = python("bounds");
  if (measured.status !== 0) process.exit(measured.status);
  const freshBounds = await formatted(measured.output, bounds);
  const targets = values.output
    ? [
        [resolve(values.output, "modeloContract.ts"), fresh],
        [resolve(values.output, "relayBounds.ts"), freshBounds],
      ]
    : [
        [contract, fresh],
        [bounds, freshBounds],
      ];

  if (values.check) {
    for (const [path, text] of targets) {
      const stored = existsSync(path)
        ? readFileSync(path, "utf8").replaceAll("\r\n", "\n")
        : "";
      if (stored !== text) {
        console.error(
          `${path} is stale; run node scripts/modelo-fixtures.mjs --contract`,
        );
        failed = true;
      }
    }
    // The host's admitted list is held to the registered family with no
    // envelope in hand.
    if (python("validate", "--definitions").status !== 0) {
      console.error(
        "The host's admitted list differs from the registered modelo family",
      );
      failed = true;
    }
  } else {
    for (const [path, text] of targets) {
      writeFileSync(path, text);
      console.log(`wrote ${path}`);
    }
  }
}

if (scenarios && values.check) {
  const seeded =
    existsSync(fixtures) &&
    readdirSync(fixtures).some((name) => ENVELOPE.test(name));
  if (!seeded) {
    console.log(
      "No modelo envelope is seeded, so none is checked; run just fixtures-seed modelo-envelopes",
    );
  } else if (python("validate").status !== 0) {
    console.error(
      "The modelo envelopes are stale; run just fixtures-seed modelo-envelopes",
    );
    failed = true;
  }
}
if (values.check) process.exit(failed ? 1 : 0);

if (scenarios) {
  // Read into a scratch directory, then write each envelope once: a
  // development server watching the fixtures may hold one open briefly. They
  // are not formatted: indentation doubles their size, and a Modelo 100 form
  // is stored as a patch of the form it differs from.
  const target = values.output ? resolve(values.output) : fixtures;
  mkdirSync(target, { recursive: true });
  const temporary = spawnSync(
    "uv",
    [
      "run",
      "--no-sync",
      "python",
      "-B",
      "-c",
      "from dev.temporary_output import prepare_temp_root; print(prepare_temp_root())",
    ],
    { cwd: repository, env: environment, encoding: "utf8", windowsHide: true },
  );
  if (temporary.error) throw temporary.error;
  if (temporary.status !== 0)
    throw new Error(`Could not prepare fixture scratch: ${temporary.stderr}`);
  const scratch = mkdtempSync(
    resolve(temporary.stdout.trim(), "modelo-envelopes-"),
  );
  try {
    const read = python("envelopes", scratch);
    if (read.status !== 0) process.exit(read.status);
    const names = readdirSync(scratch).filter((name) => ENVELOPE.test(name));
    // A seed leaves exactly the envelopes this read produced: one an earlier
    // read wrote and this one does not is gone, not left to be mistaken for current.
    for (const name of readdirSync(target))
      if (ENVELOPE.test(name) && !names.includes(name))
        rmSync(resolve(target, name));
    for (const name of names) {
      await written(
        resolve(target, name),
        readFileSync(resolve(scratch, name), "utf8"),
      );
    }
    console.log(`wrote ${names.length} envelopes`);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}
