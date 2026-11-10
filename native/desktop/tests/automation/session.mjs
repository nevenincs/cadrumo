// Exploratory native sessions: real WebKit, real IPC, isolated synthetic storage.
// No tax flow is encoded here. The caller chooses each action after inspecting UI.
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";
import { createServer } from "node:net";
import {
  mkdirSync,
  mkdtempSync,
  openSync,
  closeSync,
  readFileSync,
  writeFileSync,
  realpathSync,
  lstatSync,
  statSync,
  linkSync,
  unlinkSync,
} from "node:fs";
import {
  resolve,
  relative,
  isAbsolute,
  dirname,
  basename,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { remote, attach } = require("webdriverio");
const repository = fileURLToPath(new URL("../../../../", import.meta.url));
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

// Subscribe before the first asynchronous operation, and also inspect the
// ChildProcess properties in case the exit event has already been delivered.
export async function waitForWebDriver(child, port, run, options = {}) {
  let termination;
  let resolveTermination;
  const ended = new Promise((resolve) => {
    resolveTermination = resolve;
  });
  const onExit = (code, signal) => {
    termination = { code, signal };
    resolveTermination(termination);
  };
  const onError = () => {
    termination = { failed: true };
    resolveTermination(termination);
  };
  child.once("exit", onExit);
  child.once("error", onError);
  const currentTermination = () =>
    termination ??
    (child.exitCode !== null || child.signalCode !== null
      ? { code: child.exitCode, signal: child.signalCode }
      : null);
  const throwIfEnded = () => {
    const result = currentTermination();
    if (!result) return;
    const detail = result.failed
      ? "launch_failed"
      : result.signal
        ? `exit_signal=${result.signal}`
        : `exit_code=${result.code}`;
    throw new Error(`Native app ${detail}; inspect ${run}.`);
  };
  const check =
    options.fetchStatus ??
    ((url) =>
      fetch(url, {
        signal: AbortSignal.timeout(1000),
      }));
  let lastStatus = "not_checked";
  try {
    for (let attempt = 0; attempt < (options.attempts ?? 120); attempt++) {
      throwIfEnded();
      const response = await Promise.race([
        check(`http://127.0.0.1:${port}/status`).then(
          (status) => ({ status }),
          () => ({ connectionFailed: true }),
        ),
        ended.then(() => ({ ended: true })),
      ]);
      throwIfEnded();
      if (response.status?.ok) return;
      lastStatus = response.connectionFailed
        ? "connection_failed"
        : "http_non_ok";
      await Promise.race([sleep(options.interval ?? 500), ended]);
    }
    throwIfEnded();
    throw new Error(
      `Native WebDriver did not become ready; child=running readiness=${lastStatus}; inspect ${run}.`,
    );
  } finally {
    child.removeListener("exit", onExit);
    child.removeListener("error", onError);
  }
}

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

/** Publish one chooser answer without replacing any unconsumed answer. */
export function queuePickerSelection(run, kind, path) {
  if (
    !["open", "save"].includes(kind) ||
    (path !== null && typeof path !== "string")
  )
    throw new Error("Choose open or save and an absolute path, or cancel.");
  let chosen = null;
  let temporary;
  try {
    const realRun = realpathSync(run);
    const directDirectory = (name) => {
      const directory = resolve(realRun, name);
      if (
        lstatSync(directory).isSymbolicLink() ||
        !statSync(directory).isDirectory()
      )
        throw new Error("invalid directory");
      const canonical = realpathSync(directory);
      if (dirname(canonical) !== realRun) throw new Error("invalid directory");
      return canonical;
    };
    temporary = directDirectory("temporary");
    if (path !== null) {
      if (!isAbsolute(path) || path.split(/[\\/]/).includes(".."))
        throw new Error("invalid path");
      const root = directDirectory(kind === "open" ? "fixtures" : "exports");
      if (kind === "open") {
        chosen = within(root, path);
        if (!statSync(chosen).isFile()) throw new Error("not a file");
      } else {
        try {
          lstatSync(path);
          throw new Error("destination exists");
        } catch (error) {
          if (error.code !== "ENOENT") throw error;
        }
        const parent = realpathSync(dirname(path));
        if (parent !== root) within(root, parent);
        const name = basename(path);
        if (!name || name === "." || name === "..")
          throw new Error("invalid name");
        chosen = resolve(parent, name);
      }
    }
    const body = JSON.stringify({ kind, path: chosen });
    if (Buffer.byteLength(body) > 8192) throw new Error("answer too large");
    const pending = resolve(temporary, "native-picker-selection.json");
    const scratch = resolve(
      temporary,
      `.native-picker-${randomBytes(16).toString("hex")}`,
    );
    let created = false;
    try {
      writeFileSync(scratch, body, { mode: 0o600, flag: "wx" });
      created = true;
      linkSync(scratch, pending);
    } finally {
      if (created) unlinkSync(scratch);
    }
  } catch {
    // Do not leak paths, including a fixture name or a destination, on failure.
    throw new Error(
      "Cannot queue picker answer: invalid path or pending answer.",
    );
  }
  return { kind, selected: chosen === null ? null : basename(chosen) };
}

export function hostEnvironment(source, run, packageRoot, port, nonce) {
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
    ...(nonce === undefined ? {} : { [NONCE_VARIABLE]: nonce }),
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
    typeof state.sessionId !== "string" ||
    !isNonce(state.nonce)
  )
    throw new Error("Invalid native automation session.");
  return state;
}

/** Which process-inspection tools apply: Windows has no `ps` or `lsof`. */
export function inspectionPlatform(platform = process.platform) {
  return platform === "win32" ? "windows" : "unix";
}

/** Paths on Windows compare without case or separator differences. */
function samePath(left, right, platform) {
  if (inspectionPlatform(platform) !== "windows") return left === right;
  const normal = (value) => value.replaceAll("/", "\\").toLowerCase();
  return normal(left) === normal(right);
}

/** Whether `command` (as `inspectProcess` reports it) is this host's `--gui` launch. */
export function isHostCommand(
  command,
  executable,
  platform = process.platform,
) {
  const suffix = " --gui";
  const text = command.trim();
  return (
    text.endsWith(suffix) &&
    samePath(text.slice(0, -suffix.length), executable, platform)
  );
}

/**
 * Parse `netstat -ano -p tcp` into the listening sockets it reports. Local
 * addresses keep their host part so a non-loopback bind is not mistaken for
 * a loopback one.
 */
export function parseNetstatListeners(output) {
  const listeners = [];
  for (const line of output.split(/\r?\n/)) {
    const fields = line.trim().split(/\s+/);
    if (fields.length !== 5 || fields[0].toUpperCase() !== "TCP") continue;
    if (fields[3].toUpperCase() !== "LISTENING") continue;
    const split = fields[1].lastIndexOf(":");
    const port = Number(fields[1].slice(split + 1));
    const pid = Number(fields[4]);
    if (split < 1 || !Number.isInteger(port) || !Number.isInteger(pid))
      continue;
    listeners.push({ address: fields[1].slice(0, split), port, pid });
  }
  return listeners;
}

/**
 * Parse the JSON the Windows process query prints. A process whose image path
 * and command line disagree, or whose command line carries other arguments, is
 * reported as a command that cannot match a host launch.
 */
export function parseWindowsProcess(output) {
  let record;
  try {
    record = JSON.parse(output);
  } catch {
    return null;
  }
  if (
    typeof record?.path !== "string" ||
    typeof record?.command !== "string" ||
    record.path === ""
  )
    return null;
  const quoted = /^"([^"]*)"(.*)$/.exec(record.command);
  const image = quoted ? quoted[1] : record.command.split(" ")[0];
  const rest = quoted ? quoted[2] : record.command.slice(image.length);
  return samePath(image, record.path, "win32") ? `${record.path}${rest}` : null;
}

const WINDOWS_PROCESS_QUERY = (pid) =>
  `$p = Get-CimInstance Win32_Process -Filter "ProcessId=${Number(pid)}"; ` +
  `if ($null -eq $p) { exit 1 }; ` +
  `[Console]::Out.Write((@{ path = $p.ExecutablePath; command = $p.CommandLine } | ConvertTo-Json -Compress))`;

/**
 * `spawnSync`-shaped answer for one process: status 0 with its command, status
 * 1 with no output when it does not exist, anything else when it cannot be
 * confirmed.
 */
export function inspectProcess(
  pid,
  platform = process.platform,
  run = spawnSync,
) {
  if (inspectionPlatform(platform) !== "windows")
    return run("ps", ["-p", String(pid), "-o", "command="], {
      encoding: "utf8",
    });
  const queried = run(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROCESS_QUERY(pid)],
    { encoding: "utf8" },
  );
  if (queried.status !== 0) return queried;
  const command = parseWindowsProcess(queried.stdout || "");
  return command === null
    ? { status: 3, stdout: "", stderr: "unconfirmed process identity" }
    : { status: 0, stdout: command, stderr: "" };
}

// Each refusal names what was actually observed, so an absent listener is never
// reported as somebody else's.
const LISTENER_REFUSALS = {
  host: "The native test host process cannot be confirmed by its PID and image.",
  sockets:
    "The listening sockets cannot be read to confirm the WebDriver listener.",
  foreign:
    "The loopback WebDriver listener does not belong to this native test host.",
};

function refuseListener(reason) {
  throw new Error(LISTENER_REFUSALS[reason]);
}

/**
 * Windows: the exact launched PID, running the packaged host image, owns the
 * loopback listener, and no other process listens on that port. Anything the
 * tools cannot confirm refuses.
 */
function verifyWindowsListener(state, run) {
  const process = inspectProcess(state.pid, "win32", run);
  if (
    process.status !== 0 ||
    !isHostCommand(process.stdout, state.executable, "win32")
  )
    refuseListener("host");
  const sockets = run("netstat", ["-ano", "-p", "tcp"], { encoding: "utf8" });
  if (sockets.status !== 0) refuseListener("sockets");
  const onPort = parseNetstatListeners(sockets.stdout || "").filter(
    (listener) => listener.port === state.port,
  );
  // The socket table can be blind to loopback listeners on Windows, so an
  // empty answer is not proof of absence; ownership is proven by the launch
  // nonce over the connection instead. A listener the table does show must
  // still be this host's own loopback one.
  if (onPort.length === 0) return;
  if (
    !onPort.some(
      (listener) =>
        listener.pid === state.pid && listener.address === "127.0.0.1",
    ) ||
    onPort.some((listener) => listener.pid !== state.pid)
  )
    refuseListener("foreign");
}

function verifyUnixListener(state, run) {
  const process = inspectProcess(state.pid, "darwin", run);
  const listener = run(
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
    !isHostCommand(process.stdout, state.executable, "darwin") ||
    listener.status !== 0 ||
    !records.includes(`p${state.pid}`) ||
    !records.includes(`n127.0.0.1:${state.port}`)
  )
    refuseListener("foreign");
}

export function verifyListener(
  state,
  platform = process.platform,
  run = spawnSync,
) {
  if (inspectionPlatform(platform) === "windows")
    verifyWindowsListener(state, run);
  else verifyUnixListener(state, run);
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
  await proveOwnership(browser, state.nonce);
  return { state, browser };
}

const NONCE_VARIABLE = "CADRUMO_AUTOMATION_NONCE";

function isNonce(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

/** Equal strings, compared over every character. */
function sameNonce(expected, presented) {
  if (typeof presented !== "string" || presented.length !== expected.length)
    return false;
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1)
    difference |= expected.charCodeAt(index) ^ presented.charCodeAt(index);
  return difference === 0;
}

/**
 * The page the endpoint drives must belong to the host this launch gave the
 * nonce to; anything else, including no answer, refuses.
 */
export async function proveOwnership(browser, nonce) {
  let presented;
  try {
    presented = await browser.execute(
      () => window.__cadrumoAutomationNonce ?? null,
    );
  } catch {
    presented = null;
  }
  if (!isNonce(nonce) || !sameNonce(nonce, presented))
    throw new Error(
      "The WebDriver endpoint did not answer this launch's nonce, so it is not this native test host.",
    );
}

/** Resume only after the former host is gone, discarding its queued answer. */
export function prepareResume(previous, inspect = inspectProcess) {
  const running = inspect(previous.pid);
  if (
    running.status === 0 &&
    isHostCommand(running.stdout, previous.executable)
  )
    throw new Error(
      "Stop this session before resuming it with a rebuilt package.",
    );
  if (
    running.status !== 0 &&
    !(running.status === 1 && !running.stdout.trim() && !running.stderr.trim())
  )
    throw new Error("Cannot confirm the previous native host has exited.");
  const run = realpathSync(previous.run);
  const temporary = resolve(run, "temporary");
  if (
    lstatSync(temporary).isSymbolicLink() ||
    realpathSync(temporary) !== temporary ||
    !statSync(temporary).isDirectory()
  )
    throw new Error("Invalid native automation temporary directory.");
  const queue = resolve(temporary, "native-picker-selection.json");
  let metadata;
  try {
    metadata = lstatSync(queue);
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }
  if (!metadata.isFile() || metadata.isSymbolicLink())
    throw new Error("Invalid pending picker answer.");
  unlinkSync(queue);
}

export async function start(previousSession) {
  const previous = previousSession ? readSession(previousSession) : null;
  if (previous) prepareResume(previous);
  const staged = spawnSync(
    resolve(
      repository,
      inspectionPlatform() === "windows"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    ),
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
  for (const member of ["storage", "temporary", "fixtures", "exports"])
    mkdirSync(resolve(run, member), { mode: 0o700, recursive: true });
  const port = await freePort();
  const nonce = randomBytes(32).toString("hex");
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
    env: hostEnvironment(process.env, run, host.package, port, nonce),
    detached: true,
    stdio: ["ignore", stdout, stderr],
  });
  closeSync(stdout);
  closeSync(stderr);
  child.unref();
  const sessionFile = resolve(run, "session.json");
  try {
    await waitForWebDriver(child, port, run);
    verifyListener({ pid: child.pid, executable: host.executable, port });
    const browser = await remote({
      hostname: "127.0.0.1",
      port,
      path: "/",
      logLevel: "silent",
      connectionRetryCount: 0,
      capabilities: {},
    });
    await proveOwnership(browser, nonce);
    const state = {
      run,
      hostname: "127.0.0.1",
      port,
      sessionId: browser.sessionId,
      capabilities: browser.capabilities,
      pid: child.pid,
      executable: host.executable,
      package: host.package,
      nonce,
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
    if (child.pid && child.exitCode === null && child.signalCode === null) {
      try {
        if (!child.kill("SIGTERM"))
          error.message += " Native process cleanup could not be requested.";
      } catch {
        error.message += " Native process cleanup could not be requested.";
      }
    }
    throw error;
  }
}

export async function stop(path) {
  const { state, browser } = await connect(path);
  await browser.deleteSession();
  // A persisted PID alone is not ownership: confirm its exact executable before
  // requesting normal process termination, and never kill a process group.
  const check = inspectProcess(state.pid);
  if (check.status === 0 && isHostCommand(check.stdout, state.executable))
    process.kill(state.pid, "SIGTERM");
  else
    throw new Error(
      "Session closed; native process identity changed, so it was not terminated.",
    );
  return { closed: true, run: state.run };
}
