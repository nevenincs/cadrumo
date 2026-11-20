// Run the silent-controls audit (silent-controls.test.mjs) of the packaged
// desktop window on a disposable synthetic world.
//
//   1. materialises one catalogue persona at the registry's horizon (read from
//      the published support envelope, never a year literal) with
//      `python -m dev.desktop_persona_world` into
//      %LOCALAPPDATA%\Temp\cadrumo-e2e-silent-<random>, refusing a root inside
//      a Git project;
//   2. stages the recorded native automation host of --build with
//      `python -m dev.desktop_automation_stage`;
//   3. runs the spec on that world and host, writing the table to --report;
//   4. on a failed audit, copies the run's host and runtime logs (*.log,
//      *.jsonl of the synthetic world's run) to <report>.logs/ beside the
//      report, since they are the only record of why a session ended;
//   5. removes the disposable root (the spec signs out and removes any
//      profile-session key the run left in the credential store).
//
// Usage:
//   node native/desktop/tests/ux/run-silent-controls.mjs --build <CMake binary dir>
//     [--config Release] [--persona <id>] [--report <file.md>] [--only <rail>[,...]]
//     [--staged-package <app dir an earlier stage of --build mirrored>
//      --strings-build <this checkout's CMake binary dir holding its chrome strings>]
//
// Exit 0 when no control was silent, 1 when the audit failed, 3 when a
// prerequisite (the automation host, the world) is absent.
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import {
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import {
  basename,
  delimiter,
  dirname,
  join,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const repository = fileURLToPath(new URL("../../../../", import.meta.url));
const spec = fileURLToPath(
  new URL("./silent-controls.test.mjs", import.meta.url),
);
const python = resolve(
  repository,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
// A development checkout publishes its authority under .authority; an
// explicit CADRUMO_AUTHORITY_ROOT is kept.
const checkoutAuthority = join(repository, ".authority");
const pythonEnv = {
  ...process.env,
  ...(!process.env.CADRUMO_AUTHORITY_ROOT &&
  existsSync(join(checkoutAuthority, "authority.current.json"))
    ? { CADRUMO_AUTHORITY_ROOT: checkoutAuthority }
    : {}),
  PYTHONPATH: [join(repository, "src"), repository].join(delimiter),
  PYTHONDONTWRITEBYTECODE: "1",
};
const ROOT = /^cadrumo-e2e-silent-[0-9a-f]{32}$/;
const HORIZON = [
  "from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority",
  "from cadrumo.entrypoints.tests.persona_world import year_envelope",
  "with bundled_indexed_authority().operation() as operation:",
  "    print(year_envelope(operation).horizon)",
].join("\n");

const { values: args } = parseArgs({
  options: {
    build: { type: "string" },
    config: { type: "string", default: "Release" },
    persona: { type: "string", default: "autonomo-electricista" },
    report: { type: "string" },
    only: { type: "string", default: "" },
    "staged-package": { type: "string" },
    "strings-build": { type: "string" },
  },
});

function insideGit(directory) {
  for (let at = resolve(directory); ; at = dirname(at)) {
    if (existsSync(join(at, ".git"))) return at;
    if (dirname(at) === at) return null;
  }
}

function createRoot(parent) {
  if (insideGit(parent))
    throw new Error(
      `the disposable root's parent ${parent} is inside a Git project`,
    );
  const root = join(
    realpathSync(parent),
    `cadrumo-e2e-silent-${randomBytes(16).toString("hex")}`,
  );
  mkdirSync(root);
  return root;
}

function removeRoot(root, parent) {
  const resolved = resolve(root);
  if (
    dirname(resolved) !== realpathSync(parent) ||
    !ROOT.test(basename(resolved)) ||
    lstatSync(resolved).isSymbolicLink()
  )
    throw new Error(`refusing to remove ${resolved}`);
  // rmSync removes a link inside the tree, never what it points at.
  rmSync(resolved, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 500,
  });
  if (existsSync(resolved)) throw new Error(`${resolved} was not removed`);
}

const LOG_FILE = /\.(log|jsonl)$/i;
const LOG_LIMIT = 64 << 20;

/** Copy the log files under `from` (no links followed, none over LOG_LIMIT)
 * into `to`, keeping their relative paths; returns how many were copied. */
function keepLogs(from, to) {
  let kept = 0;
  const walk = (dir, depth) => {
    if (depth > 8) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) walk(path, depth + 1);
      else if (
        entry.isFile() &&
        LOG_FILE.test(entry.name) &&
        lstatSync(path).size <= LOG_LIMIT
      ) {
        const target = join(to, relative(from, path));
        mkdirSync(dirname(target), { recursive: true });
        copyFileSync(path, target);
        kept += 1;
      }
    }
  };
  if (existsSync(from) && !lstatSync(from).isSymbolicLink()) walk(from, 0);
  return kept;
}

function fail(code, message) {
  console.error(`silent-controls: ${message}`);
  process.exit(code);
}

if (!args.build) fail(3, "--build names no CMake binary directory");
const build = resolve(args.build);
// A build owned by another checkout is staged by that checkout's own
// dev.desktop_automation_stage (it admits only its own build tree); its
// package mirror is then named here.
const staged = args["staged-package"]
  ? {
      status: 0,
      stdout: JSON.stringify({
        package: resolve(args["staged-package"]),
        executable: join(resolve(args["staged-package"]), "cadrumo.exe"),
      }),
    }
  : spawnSync(
      python,
      [
        "-m",
        "dev.desktop_automation_stage",
        "--build",
        build,
        "--config",
        args.config,
      ],
      { cwd: repository, env: pythonEnv, encoding: "utf8" },
    );
if (staged.status !== 0)
  fail(
    3,
    `no automation host: ${(staged.stdout || staged.stderr).trim().slice(-400)}`,
  );
const horizon = spawnSync(python, ["-c", HORIZON], {
  cwd: repository,
  env: pythonEnv,
  encoding: "utf8",
});
if (horizon.status !== 0)
  fail(
    3,
    `the registry horizon was not read: ${horizon.stderr.trim().slice(-400)}`,
  );

const parent = process.env.LOCALAPPDATA
  ? join(process.env.LOCALAPPDATA, "Temp")
  : tmpdir();
const root = createRoot(parent);
const report = resolve(
  args.report ??
    join(repository, ".tmp", "silent-controls", `${basename(root)}.md`),
);
if (report.startsWith(root + sep))
  fail(3, "--report must lie outside the disposable root");
let code = 1;
try {
  const world = spawnSync(
    python,
    [
      "-m",
      "dev.desktop_persona_world",
      "--persona",
      args.persona,
      "--horizon",
      horizon.stdout.trim(),
      "--storage-root",
      join(root, "world"),
    ],
    { cwd: repository, env: pythonEnv, encoding: "utf8", maxBuffer: 64 << 20 },
  );
  if (world.status !== 0) {
    code = 3;
    throw new Error(
      `the persona world was not prepared (exit ${world.status}): ${world.stderr.trim().split(/\r?\n/).slice(-3).join(" | ")}`,
    );
  }
  const worldPath = join(root, "world.json");
  writeFileSync(worldPath, world.stdout);
  mkdirSync(dirname(report), { recursive: true });
  const run = spawnSync(
    process.execPath,
    ["--test", "--test-reporter=spec", spec],
    {
      cwd: repository,
      stdio: "inherit",
      env: {
        ...process.env,
        CADRUMO_PERSONA_WORLD: worldPath,
        CADRUMO_PERSONA_HOST: staged.stdout.trim(),
        // The window's chrome strings are read from an enrolled build of this
        // checkout; with --staged-package that is --strings-build.
        CADRUMO_CMAKE_BINARY_DIR: resolve(args["strings-build"] ?? build),
        CADRUMO_BUILD_CONFIG: args.config,
        CADRUMO_UX_RUN: join(root, "run"),
        CADRUMO_SILENT_REPORT: report,
        ...(args.only ? { CADRUMO_SILENT_ONLY: args.only } : {}),
        PYTHONDONTWRITEBYTECODE: "1",
      },
    },
  );
  code = run.status === 0 ? 0 : 1;
  console.log(`silent-controls: table at ${report}`);
  if (code !== 0) {
    const logs = `${report.replace(/\.md$/i, "")}.logs`;
    const kept = keepLogs(join(root, "run"), logs);
    if (kept)
      console.log(`silent-controls: ${kept} run log(s) kept at ${logs}`);
  }
} catch (error) {
  console.error(`silent-controls: ${error.message}`);
} finally {
  try {
    removeRoot(root, parent);
  } catch (error) {
    console.error(`silent-controls: ${error.message}`);
    code = code === 0 ? 1 : code;
  }
}
process.exit(code);
