// The results directory of one Playwright run. Playwright empties its output
// directory when a run starts, so a directory shared by two runs in the same
// build loses the other run's traces in the middle of it. Each run writes
// under `runs/<start>-<pid>` of the build's test results instead.
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { requireBuildOutput } from "../../scripts/build-paths.mjs";

// Workers and web servers inherit the environment of the run that starts
// them and load this configuration again: the variable keeps them on the
// directory their run chose.
const RUN = "CADRUMO_DESKTOP_TEST_RUN";
const STALE_AFTER_MS = 24 * 60 * 60 * 1000;
const NAME = /^(\d{8}T\d{6}Z)-(\d+)$/;

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    // EPERM: the process exists but belongs to someone this one cannot signal.
    return error.code === "EPERM";
  }
}

function started(stamp) {
  const [, y, mo, d, h, mi, s] = /^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$/
    .exec(stamp)
    .map(Number);
  return Date.UTC(y, mo - 1, d, h, mi, s);
}

// A run whose process has ended keeps its results for a day, so a failure
// stays readable after the run; a run still going is never touched.
function removeStale(runs, now) {
  let entries;
  try {
    entries = readdirSync(runs, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }
  for (const entry of entries) {
    const match = entry.isDirectory() ? NAME.exec(entry.name) : null;
    if (!match) continue;
    if (now - started(match[1]) < STALE_AFTER_MS) continue;
    if (alive(Number(match[2]))) continue;
    rmSync(resolve(runs, entry.name), { recursive: true, force: true });
  }
}

/** This run's own results directory below `results`, created on first use. */
export function testRunDirectory(results) {
  const runs = requireBuildOutput(resolve(results, "runs"));
  let name = process.env[RUN];
  if (!name) {
    const now = Date.now();
    removeStale(runs, now);
    const stamp = new Date(now).toISOString().replace(/[-:]|\.\d+/g, "");
    name = `${stamp}-${process.pid}`;
    process.env[RUN] = name;
  }
  if (!NAME.test(name)) throw new Error(`Invalid ${RUN}: ${name}`);
  const directory = requireBuildOutput(resolve(runs, name));
  mkdirSync(directory, { recursive: true });
  return directory;
}

/** A bundle belongs to its test run, so another build cannot empty it under
 * the run's live server. Outside a run the ordinary build location is used. */
function testRunBuild(results, kind) {
  const name = process.env[RUN];
  if (!name) return null;
  if (!NAME.test(name)) throw new Error(`Invalid ${RUN}: ${name}`);
  return requireBuildOutput(resolve(results, "runs", name, kind));
}

export function testRunScenariosBuild(results) {
  return testRunBuild(results, "scenarios");
}

/** This run's product bundle, separate from the ordinary product build. */
export function testRunProductBuild(results) {
  return testRunBuild(results, "product");
}
