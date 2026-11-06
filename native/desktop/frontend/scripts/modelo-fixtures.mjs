// Regenerates the desktop's Modelo wire types, scenario envelopes and relay
// bounds from the Python models and the host's Rust sources, through
// scripts/modelo_fixtures.py, and formats what it writes as the frontend's
// formatter does. `--contract` selects the wire types and relay bounds
// (the modules under src/shell/modeloContract/ and relayBounds.ts,
// committed), and the module bound the producer reports, written to
// src/shell/moduleBound.json for the lint rule; `--envelopes`
// selects the scenario envelopes, which are build output in the window
// projections of the selected build tree and never committed, the directory
// `--fixtures DIR` names; with neither, both. The
// envelopes are stored as the producer writes them, compact and the Modelo 100
// forms as patches; `--pack` stores the ones already on disk that way.
// The wire types are refused, none written or compared, when a formatted
// module would be longer than the module bound the producer reports.
// `--check` writes nothing: for the wire types it fails when they differ from
// fresh output, a module is missing or left over, or the host's admitted list
// differs from the registered family,
// and for the envelopes it fails when a stored one no longer validates against
// its model, having nothing to check while none is seeded. `--output DIR`
// writes what was selected into an existing directory instead, which is how a
// determinism proof builds twice. The envelopes are read for synthetic
// taxpayers over the published authority under CADRUMO_AUTHORITY_ROOT, or the
// repository's `.authority` where unset.
import { spawnSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { format, resolveConfig } from "prettier";
import { refuseOversizedModules } from "./generated-module-bound.mjs";

const { values } = parseArgs({
  options: {
    check: { type: "boolean", default: false },
    contract: { type: "boolean", default: false },
    envelopes: { type: "boolean", default: false },
    pack: { type: "boolean", default: false },
    output: { type: "string" },
    fixtures: { type: "string" },
  },
});
const wireTypes = values.contract || !values.envelopes;
const scenarios = values.envelopes || !values.contract;

const frontend = fileURLToPath(new URL("..", import.meta.url));
const repository = resolve(frontend, "../../..");
// The wire type modules, one directory the generator alone writes. The
// producer groups the types into modules; this list names every module it
// writes, and a run fails when the two differ.
const CONTRACT_MODULES = [
  "src/shell/modeloContract/contracts.ts",
  "src/shell/modeloContract/modelo.ts",
  "src/shell/modeloContract/modelo036.ts",
  "src/shell/modeloContract/modeloAggregate.ts",
  "src/shell/modeloContract/modeloAudit.ts",
  "src/shell/modeloContract/modeloBindings.ts",
  "src/shell/modeloContract/modeloCompare.ts",
  "src/shell/modeloContract/modeloDeclarations.ts",
  "src/shell/modeloContract/modeloEdit.ts",
  "src/shell/modeloContract/modeloEditWork.ts",
  "src/shell/modeloContract/modeloExport.ts",
  "src/shell/modeloContract/modeloFilingRecord.ts",
  "src/shell/modeloContract/modeloHistory.ts",
  "src/shell/modeloContract/modeloIvaWallet.ts",
  "src/shell/modeloContract/modeloM145.ts",
  "src/shell/modeloContract/modeloM360Solicitud.ts",
  "src/shell/modeloContract/modeloObservation.ts",
  "src/shell/modeloContract/modeloProject.ts",
  "src/shell/modeloContract/modeloQuickfile.ts",
  "src/shell/modeloContract/modeloReadiness.ts",
  "src/shell/modeloContract/modeloReconcile.ts",
  "src/shell/modeloContract/modeloRequires.ts",
  "src/shell/modeloContract/modeloReviewPackage.ts",
  "src/shell/modeloContract/modeloSpreadsheet.ts",
  "src/shell/modeloContract/modeloVerificationReport.ts",
  "src/shell/modeloContract/modeloWork.ts",
  "src/shell/modeloContract/modeloWorkAmend.ts",
  "src/shell/modeloContract/modeloWorkAmendmentContext.ts",
  "src/shell/modeloContract/modeloWorkCasillaHelp.ts",
  "src/shell/modeloContract/modeloWorkDependencies.ts",
  "src/shell/modeloContract/modeloWorkForm.ts",
  "src/shell/modeloContract/modeloWorkHistory.ts",
  "src/shell/modeloContract/modeloWorkReportVerify.ts",
  "src/shell/modeloContract/modeloWorkReview.ts",
  "src/shell/modeloContract/modeloWorkVerify.ts",
];
const contractDirectory = resolve(frontend, "src/shell/modeloContract");
const bounds = resolve(frontend, "src/shell/relayBounds.ts");
// The module bound as the producer reported it, for the lint rule to read.
const moduleBound = resolve(frontend, "src/shell/moduleBound.json");
// The fixture projection seeder names the window projections' directory, the
// one place the envelopes are stored, so this driver resolves no build tree.
const storedEnvelopes =
  values.pack || (scenarios && (values.check || !values.output));
if (storedEnvelopes && !values.fixtures) {
  console.error(
    "Name the window projections' directory with --fixtures; run just fixtures-seed modelo-envelopes",
  );
  process.exit(1);
}
const fixtures = values.fixtures ? resolve(values.fixtures, "modelo") : "";
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
  const { bound, modules: emitted } = JSON.parse(generated.output);
  const modules = Object.entries(emitted);
  const listed = CONTRACT_MODULES.map((path) => basename(path));
  const unlisted = modules
    .map(([name]) => name)
    .filter((name) => !listed.includes(name));
  const unwritten = listed.filter(
    (name) => !modules.some(([module]) => module === name),
  );
  if (unlisted.length || unwritten.length) {
    console.error(
      `The producer's contract modules differ from CONTRACT_MODULES: list ${unlisted.join(", ") || "nothing new"}; drop ${unwritten.join(", ") || "nothing"}`,
    );
    process.exit(1);
  }
  const directory = values.output
    ? resolve(values.output, "modeloContract")
    : contractDirectory;
  const targets = [];
  for (const [name, source] of modules) {
    const path = resolve(directory, name);
    targets.push([
      path,
      await formatted(source, resolve(contractDirectory, name)),
    ]);
  }
  const measured = python("bounds");
  if (measured.status !== 0) process.exit(measured.status);
  const freshBounds = await formatted(measured.output, bounds);
  targets.push([
    values.output ? resolve(values.output, "relayBounds.ts") : bounds,
    freshBounds,
  ]);
  // Every generated module is held to the repository's module bound before
  // any is written or compared.
  refuseOversizedModules(
    targets.map(([path, text]) => [basename(path), text]),
    bound,
    "split what the producer emits",
  );
  targets.push([
    values.output ? resolve(values.output, "moduleBound.json") : moduleBound,
    await formatted(JSON.stringify({ physicalLines: bound }), moduleBound),
  ]);
  // A module the producer no longer writes is stale, not left to be imported.
  const leftover = existsSync(directory)
    ? readdirSync(directory).filter((name) => !listed.includes(name))
    : [];

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
    for (const name of leftover) {
      console.error(
        `${resolve(directory, name)} is no generated module; run node scripts/modelo-fixtures.mjs --contract`,
      );
      failed = true;
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
    // Only a plain file the generator could have written is removed; anything
    // else in its directory is refused, and nothing is written.
    const foreign = leftover.filter(
      (name) => !lstatSync(resolve(directory, name)).isFile(),
    );
    if (foreign.length) {
      for (const name of foreign)
        console.error(
          `${resolve(directory, name)} is not a generated module; remove it by hand`,
        );
      process.exit(1);
    }
    mkdirSync(directory, { recursive: true });
    for (const name of leftover) {
      rmSync(resolve(directory, name));
      console.log(`removed ${resolve(directory, name)}`);
    }
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
  } else if (python("validate", fixtures).status !== 0) {
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
