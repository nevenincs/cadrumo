// The results directory of one Playwright run. Playwright empties its output
// directory when a run starts, so a directory shared by two runs in the same
// build loses the other run's traces in the middle of it. Each run writes
// under `runs/<start>-<pid>` of the build's test results instead.
import { randomBytes } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { connect, createServer } from "node:net";
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

const PORTS = ["previewPort", "scenariosPort", "scenariosDocsPort", "hotPort"];

/** Allocate the test run's ports once; children read the same run-owned file.
 * A later bind collision fails server startup rather than reusing a listener. */
export function testRunPorts(results) {
  if (!process.env[RUN]) return null;
  const directory = testRunDirectory(results);
  const file = requireBuildOutput(resolve(directory, "ports.json"));
  const value = JSON.parse(readFileSync(file, "utf8"));
  if (
    PORTS.some(
      (key) =>
        !Number.isInteger(value[key]) || value[key] < 1 || value[key] > 65535,
    ) ||
    !Number.isInteger(value.controlPort) ||
    value.controlPort < 1 ||
    value.controlPort > 65535 ||
    typeof value.token !== "string" ||
    !/^[0-9a-f]{48}$/.test(value.token) ||
    new Set([...PORTS.map((key) => value[key]), value.controlPort]).size !==
      PORTS.length + 1
  )
    throw new Error(`Invalid browser test ports in ${file}`);
  return value;
}

function listen(server, host = "0.0.0.0") {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen({ host, port: 0, exclusive: true }, () => {
      server.removeListener("error", reject);
      server.unref();
      resolve(server.address().port);
    });
  });
}

/** Hold each listener until its own server is ready to bind it. */
export async function reserveTestRunPorts(results) {
  const file = requireBuildOutput(
    resolve(testRunDirectory(results), "ports.json"),
  );
  if (existsSync(file)) return testRunPorts(results);
  const held = new Map();
  const value = {};
  let control;
  try {
    for (const key of PORTS) {
      const server = createServer();
      held.set(key, server);
      value[key] = await listen(server);
    }
    const token = randomBytes(24).toString("hex");
    control = createServer((socket) => {
      let input = "";
      socket.on("data", async (chunk) => {
        input += chunk.toString();
        if (!input.endsWith("\n")) return;
        try {
          const request = JSON.parse(input);
          if (
            request.token !== token ||
            !Array.isArray(request.keys) ||
            request.keys.length === 0 ||
            new Set(request.keys).size !== request.keys.length ||
            request.keys.some((key) => !held.has(key))
          )
            throw new Error("Invalid reservation request");
          const servers = request.keys.map((key) => {
            const server = held.get(key);
            held.delete(key);
            return server;
          });
          await Promise.all(
            servers.map((server) => new Promise((done) => server.close(done))),
          );
          socket.end("ok\n");
          if (held.size === 0) control.close();
        } catch {
          socket.destroy();
        }
      });
    });
    value.controlPort = await listen(control, "127.0.0.1");
    value.token = token;
    writeFileSync(file, JSON.stringify(value), { flag: "wx", mode: 0o600 });
    return value;
  } catch (error) {
    for (const server of held.values()) if (server.listening) server.close();
    if (control?.listening) control.close();
    throw error;
  }
}

/** Release only the listeners the calling run's server is about to bind. */
export function releaseTestRunPorts(results, keys) {
  const value = testRunPorts(results);
  if (
    !value ||
    !Number.isInteger(value.controlPort) ||
    typeof value.token !== "string"
  )
    throw new Error("Missing browser test port reservation");
  return new Promise((resolve, reject) => {
    const socket = connect(value.controlPort, "127.0.0.1", () =>
      socket.write(`${JSON.stringify({ token: value.token, keys })}\n`),
    );
    let reply = "";
    socket.setTimeout(10_000, () =>
      socket.destroy(new Error("Port reservation timed out")),
    );
    socket.on("data", (chunk) => {
      reply += chunk.toString();
    });
    socket.once("error", reject);
    socket.once("end", () =>
      reply === "ok\n"
        ? resolve()
        : reject(new Error("Port reservation refused")),
    );
  });
}
