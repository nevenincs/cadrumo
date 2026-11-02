// Exploratory native sessions: real WebKit, real IPC, isolated synthetic storage.
// No tax flow is encoded here. The caller chooses each action after inspecting UI.
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import {
  mkdirSync,
  mkdtempSync,
  openSync,
  closeSync,
  readFileSync,
  writeFileSync,
  realpathSync,
} from "node:fs";
import { resolve, relative, isAbsolute, dirname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { remote, attach } = require("webdriverio");
const repository = fileURLToPath(new URL("../../../../", import.meta.url));
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

export function within(root, path) {
  const member = relative(realpathSync(root), realpathSync(path));
  if (
    !member ||
    member === ".." ||
    member.startsWith(`..${sep}`) ||
    isAbsolute(member)
  )
    throw new Error(
      "Automation files must remain inside this build's run directory.",
    );
  return realpathSync(path);
}

export function hostEnvironment(source, run, packageRoot, port) {
  const env = Object.fromEntries(
    Object.entries(source).filter(
      ([key]) =>
        !/^(CADRUMO_|WEBVIEW2_|TAURI_WEBDRIVER_|PLAYWRIGHT_|OLLAMA_|HTTP_PROXY$|HTTPS_PROXY$|ALL_PROXY$)/i.test(
          key,
        ),
    ),
  );
  return {
    ...env,
    CADRUMO_STORAGE_ROOT: resolve(run, "storage"),
    CADRUMO_DESKTOP_PACKAGE_ROOT: packageRoot,
    TAURI_WEBDRIVER_PORT: String(port),
    TMPDIR: resolve(run, "temporary"),
    TMP: resolve(run, "temporary"),
    TEMP: resolve(run, "temporary"),
  };
}

async function freePort() {
  const server = createServer();
  await new Promise((done, fail) => {
    server.once("error", fail);
    server.listen(0, "127.0.0.1", done);
  });
  const port = server.address().port;
  await new Promise((done) => server.close(done));
  return port;
}

export function readSession(path) {
  const runs = resolve(buildPath("desktop_testing"), "automation", "runs");
  const file = within(runs, path);
  const state = JSON.parse(readFileSync(file, "utf8"));
  if (
    state.run !== dirname(file) ||
    state.hostname !== "127.0.0.1" ||
    !Number.isInteger(state.port) ||
    state.port < 1 ||
    state.port > 65535 ||
    typeof state.sessionId !== "string"
  )
    throw new Error("Invalid native automation session.");
  return state;
}

export function verifyListener(state) {
  const process = spawnSync("ps", ["-p", String(state.pid), "-o", "command="], {
    encoding: "utf8",
  });
  const listener = spawnSync(
    "lsof",
    [
      "-nP",
      "-a",
      "-p",
      String(state.pid),
      `-iTCP:${state.port}`,
      "-sTCP:LISTEN",
      "-Fpn",
    ],
    { encoding: "utf8" },
  );
  const records = (listener.stdout || "").trim().split("\n");
  if (
    process.status !== 0 ||
    process.stdout.trim() !== `${state.executable} --gui` ||
    listener.status !== 0 ||
    !records.includes(`p${state.pid}`) ||
    !records.includes(`n127.0.0.1:${state.port}`)
  )
    throw new Error(
      "The loopback WebDriver listener does not belong to this native test host.",
    );
}

export async function connect(path) {
  const state = readSession(path);
  verifyListener(state);
  const browser = await attach({
    hostname: state.hostname,
    port: state.port,
    path: "/",
    sessionId: state.sessionId,
    capabilities: state.capabilities,
    logLevel: "silent",
  });
  return { state, browser };
}

export async function start(previousSession) {
  const previous = previousSession ? readSession(previousSession) : null;
  if (previous) {
    const running = spawnSync(
      "ps",
      ["-p", String(previous.pid), "-o", "command="],
      { encoding: "utf8" },
    );
    if (
      running.status === 0 &&
      running.stdout.trim() === `${previous.executable} --gui`
    )
      throw new Error(
        "Stop this session before resuming it with a rebuilt package.",
      );
  }
  const staged = spawnSync(
    resolve(repository, ".venv/bin/python"),
    [
      "-m",
      "dev.desktop_automation_stage",
      "--build",
      process.env.CADRUMO_CMAKE_BINARY_DIR,
      "--config",
      process.env.CADRUMO_BUILD_CONFIG,
    ],
    { cwd: repository, encoding: "utf8" },
  );
  if (staged.status !== 0)
    throw new Error(
      staged.stdout || staged.stderr || "Native test package staging failed.",
    );
  const host = JSON.parse(staged.stdout.trim());
  const runs = resolve(buildPath("desktop_testing"), "automation", "runs");
  mkdirSync(runs, { recursive: true });
  const run = previous?.run ?? mkdtempSync(resolve(runs, "run-"));
  for (const member of ["storage", "temporary", "exports"])
    mkdirSync(resolve(run, member), { mode: 0o700, recursive: true });
  const port = await freePort();
  const stdout = openSync(
    resolve(run, "host.stdout.log"),
    previous ? "a" : "wx",
    0o600,
  );
  const stderr = openSync(
    resolve(run, "host.stderr.log"),
    previous ? "a" : "wx",
    0o600,
  );
  const child = spawn(host.executable, ["--gui"], {
    cwd: host.package,
    env: hostEnvironment(process.env, run, host.package, port),
    detached: true,
    stdio: ["ignore", stdout, stderr],
  });
  closeSync(stdout);
  closeSync(stderr);
  let launchError;
  child.once("error", (error) => {
    launchError = error;
  });
  child.unref();
  const sessionFile = resolve(run, "session.json");
  try {
    let ready = false;
    for (let attempt = 0; attempt < 120; attempt++) {
      if (launchError) throw launchError;
      if (child.exitCode !== null)
        throw new Error(
          `Native app exited with ${child.exitCode}; inspect ${run}.`,
        );
      try {
        const status = await fetch(`http://127.0.0.1:${port}/status`, {
          signal: AbortSignal.timeout(1000),
        });
        if (status.ok) {
          ready = true;
          break;
        }
      } catch {
        /* The listener starts with the native app. */
      }
      await sleep(500);
    }
    if (!ready)
      throw new Error(`Native WebDriver did not become ready; inspect ${run}.`);
    verifyListener({ pid: child.pid, executable: host.executable, port });
    const browser = await remote({
      hostname: "127.0.0.1",
      port,
      path: "/",
      logLevel: "silent",
      connectionRetryCount: 0,
      capabilities: {},
    });
    const state = {
      run,
      hostname: "127.0.0.1",
      port,
      sessionId: browser.sessionId,
      capabilities: browser.capabilities,
      pid: child.pid,
      executable: host.executable,
      package: host.package,
    };
    writeFileSync(sessionFile, JSON.stringify(state, null, 2), {
      mode: 0o600,
      flag: previous ? "w" : "wx",
    });
    return {
      session: sessionFile,
      run,
      windows: await browser.getWindowHandles(),
    };
  } catch (error) {
    if (child.pid) child.kill("SIGTERM");
    throw error;
  }
}

export async function stop(path) {
  const { state, browser } = await connect(path);
  await browser.deleteSession();
  // A persisted PID alone is not ownership: confirm its exact executable before
  // requesting normal process termination, and never kill a process group.
  const check = spawnSync("ps", ["-p", String(state.pid), "-o", "command="], {
    encoding: "utf8",
  });
  if (check.status === 0 && check.stdout.trim() === `${state.executable} --gui`)
    process.kill(state.pid, "SIGTERM");
  else
    throw new Error(
      "Session closed; native process identity changed, so it was not terminated.",
    );
  return { closed: true, run: state.run };
}
