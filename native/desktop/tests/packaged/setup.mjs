// The packaged setup acceptance: its decisions, and the driver that drives the
// packaged window through a real browser setup. The run happens on the
// development host, so everything it writes lives under one throwaway root
// inside the build's testing directory: storage, temporary files, application
// data, the browser download and the runtime's endpoint. The root is removed
// when the run ends and real storage is listed before and after. Each item's
// readiness is decided from the app's own full check recorded after setup
// settled; an installer's exit code, a receipt or a declaration is never
// evidence that an item works. Each decision takes observations and returns
// { verdict, detail, data? }, so it can be tested against observations that
// must pass and observations that must fail.

import { spawnSync } from "node:child_process";
import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { createServer } from "node:http";
import { connect as netConnect } from "node:net";
import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { waitFor } from "./session.mjs";
import { FAIL, PASS } from "./verdicts.mjs";

const pass = (detail, data) => ({
  verdict: PASS,
  detail,
  ...(data && { data }),
});
const fail = (detail, data) => ({
  verdict: FAIL,
  detail,
  ...(data && { data }),
});

/** The setup run is asked for only through this variable, set to "1". */
export const SETUP_VARIABLE = "CADRUMO_PACKAGED_SETUP";

/** The run refuses to start on a volume with less free space than this. */
export const FREE_SPACE_FLOOR_BYTES = 30 * 1024 ** 3;

/** The largest the throwaway root may grow to before the watchdog stops the run. */
export const SCRATCH_BUDGET_BYTES = 8 * 1024 ** 3;

/** What a setup that downloads nothing may still move: the reachability preflight's handshakes. */
export const NO_TRANSFER_ALLOWANCE_BYTES = 1024 ** 2;

/** Bytes the first attempt moves before the harness forces its interruption. */
export const INTERRUPT_AFTER_BYTES = 20 * 1024 ** 2;

/** States in which Cadrumo counts an item as set up. */
export const USABLE_STATES = Object.freeze(["ready", "stale"]);

/** The one evidence source that may decide readiness: the item's own full check. */
export const FULL_CHECK_SOURCE = "full_check";

const ITEM_ID = /^(?:browser|local_ai)$/;

function strictlyInside(parent, child) {
  const inside = relative(resolve(parent), resolve(child));
  return !!inside && !inside.startsWith("..") && !isAbsolute(inside);
}

/**
 * The setup run may start: it was asked for, the run directory is a
 * throwaway root inside the build's testing directory, and the storage root
 * is a fresh, empty directory inside it, so no developer's or person's
 * storage is ever set up or overwritten.
 */
export function setupHostVerdict({
  env,
  storageRoot,
  storageEntries,
  runDirectory,
  testingRoot,
}) {
  if (env?.[SETUP_VARIABLE] !== "1") {
    return fail(
      `refused: set ${SETUP_VARIABLE}=1 to run the setup acceptance; it downloads hundreds of megabytes`,
    );
  }
  if (
    ![storageRoot, runDirectory, testingRoot].every(
      (path) => typeof path === "string" && isAbsolute(path),
    )
  ) {
    return fail(
      "refused: the storage root, the run directory and the testing directory must be absolute paths",
    );
  }
  if (!strictlyInside(testingRoot, runDirectory)) {
    return fail(
      "refused: the run directory is not a throwaway root inside the build's testing directory",
      { runDirectory, testingRoot },
    );
  }
  if (!strictlyInside(runDirectory, storageRoot)) {
    return fail(
      "refused: the storage root is not a directory inside this run's own directory",
      {
        storageRoot,
        runDirectory,
      },
    );
  }
  if (!Array.isArray(storageEntries) || storageEntries.length > 0) {
    return fail("refused: the storage root is not clean", {
      entries: Array.isArray(storageEntries)
        ? storageEntries.slice(0, 10)
        : null,
    });
  }
  return pass(
    "a clean storage root inside a throwaway run directory under the build's testing directory",
  );
}

/** The volume holding the throwaway root has room for the run and more. */
export function freeSpaceVerdict({
  freeBytes,
  floorBytes = FREE_SPACE_FLOOR_BYTES,
}) {
  if (!Number.isSafeInteger(freeBytes) || freeBytes < 0) {
    return fail("refused: the free space of the volume could not be read");
  }
  if (freeBytes < floorBytes) {
    return fail(
      `refused: the volume has ${freeBytes} bytes free, under the ${floorBytes}-byte floor`,
      { freeBytes, floorBytes },
    );
  }
  return pass(`${freeBytes} bytes free, over the ${floorBytes}-byte floor`, {
    freeBytes,
    floorBytes,
  });
}

/** The items a setup must cover, read from the registry rows the host reported. */
export function setupItemsFrom(rows) {
  return rows.map((row) => row.itemId);
}

/**
 * One approval set up everything: exactly one plan was approved before any
 * byte moved, it named every item the registry reported and nothing else, and
 * no other approval was asked for.
 */
export function planApprovalVerdict({
  approvals,
  requiredItemIds,
  firstTransferAt,
}) {
  if (!Array.isArray(requiredItemIds) || requiredItemIds.length === 0) {
    return fail(
      "the host reported no setup items, so the plan was checked against nothing",
    );
  }
  if (!Array.isArray(approvals) || approvals.length !== 1) {
    return fail(
      `expected one approval for the whole setup, saw ${approvals?.length ?? 0}`,
    );
  }
  const [approval] = approvals;
  const planned = new Set(approval.itemIds);
  const missing = requiredItemIds.filter((itemId) => !planned.has(itemId));
  if (missing.length > 0) {
    return fail("the approved plan left items out", { missing });
  }
  const extra = [...planned].filter(
    (itemId) => !requiredItemIds.includes(itemId),
  );
  if (extra.length > 0) {
    return fail("the approved plan names items the host did not report", {
      extra,
    });
  }
  if (!approval.digest) {
    return fail(
      "the approval carries no plan digest, so it could approve something other than what downloads",
    );
  }
  if (
    firstTransferAt !== undefined &&
    !(Date.parse(approval.at) <= Date.parse(firstTransferAt))
  ) {
    return fail("bytes moved before the plan was approved", {
      approvedAt: approval.at,
      firstTransferAt,
    });
  }
  return pass(`one approval covered ${requiredItemIds.length} items`, {
    digest: approval.digest,
    itemIds: [...planned],
  });
}

/**
 * An item is set up only on its own full check, run after setup settled. A
 * receipt, a completion marker, an installer's exit code or the registry's
 * declaration is authored or self-reported, never evidence that it works.
 */
export function itemEvidenceVerdict({
  itemId,
  state,
  evidence,
  setupSettledAt,
}) {
  if (!ITEM_ID.test(itemId ?? "")) {
    return fail(`not a setup item identity: ${JSON.stringify(itemId)}`);
  }
  if (!evidence) {
    return fail(`${itemId}: no evidence was recorded`);
  }
  if (evidence.source !== FULL_CHECK_SOURCE || evidence.mode !== "full") {
    return fail(
      `${itemId}: readiness rests on ${evidence.source ?? "nothing"}, not on its full check`,
      {
        evidence,
      },
    );
  }
  if (!(Date.parse(evidence.checkedAt) >= Date.parse(setupSettledAt))) {
    return fail(
      `${itemId}: the full check ran before setup settled, so it checked the old install`,
      {
        checkedAt: evidence.checkedAt,
        setupSettledAt,
      },
    );
  }
  if (!USABLE_STATES.includes(state)) {
    return fail(`${itemId}: full check left the item ${state}`, { evidence });
  }
  return pass(`${itemId}: ${state} on its full check`, { evidence });
}

/**
 * A forced interruption is recovered by Resume: the interrupted item reads as
 * failed with category interrupted, Resume asks for no second approval while
 * the plan digest is unchanged, the transfer continues from the bytes already
 * on disk instead of starting again, and the item ends usable.
 */
export function resumeVerdict({ interrupted, resumed }) {
  if (!interrupted || !resumed) {
    return fail("no interruption was forced, so Resume was never exercised");
  }
  if (
    interrupted.state !== "failed" ||
    interrupted.failureCategory !== "interrupted"
  ) {
    return fail(
      `after the interruption the item read ${interrupted.state}/${interrupted.failureCategory ?? "none"}, not failed/interrupted`,
    );
  }
  if (!(interrupted.completedBytes > 0)) {
    return fail(
      "the interruption came before any byte moved, so a restart and a resume look alike",
    );
  }
  if (resumed.approvalsShown !== 0 || resumed.digest !== interrupted.digest) {
    return fail(
      "Resume of an unchanged plan asked for approval again or ran a different plan",
      {
        approvalsShown: resumed.approvalsShown,
        sameDigest: resumed.digest === interrupted.digest,
      },
    );
  }
  if (!(resumed.firstCompletedBytes >= interrupted.completedBytes)) {
    return fail("the transfer started again from zero instead of resuming", {
      before: interrupted.completedBytes,
      afterResume: resumed.firstCompletedBytes,
    });
  }
  if (!USABLE_STATES.includes(resumed.finalState)) {
    return fail(`after Resume the item ended ${resumed.finalState}`);
  }
  return pass(
    `resumed at ${resumed.firstCompletedBytes} of ${interrupted.totalBytes ?? "unknown"} bytes`,
  );
}

/** Writes each item's evidence to its own file, so one item's record never stands for another's. */
export function recordItemEvidence(results, items) {
  return items.map((item) =>
    results.evidence(`setup-${item.itemId}.json`, item),
  );
}

/**
 * Resume of an interrupted browser setup, judged on what the person saw and
 * what moved. The cut came mid-download, so bytes had moved; the window then
 * offered Resume, its click asked to resume, no second plan was rendered and
 * no second answer was sent, no build finished before the cut was downloaded
 * again, and the item ended usable.
 */
export function browserResumeVerdict({ interrupted, resumed }) {
  if (!interrupted || !resumed) {
    return fail("no interruption was forced, so Resume was never exercised");
  }
  if (!(interrupted.wireBytes > 0)) {
    return fail(
      "the interruption came before any byte moved, so a restart and a resume look alike",
    );
  }
  if (interrupted.offered !== "resume") {
    return fail(
      `after the interruption the window offered ${interrupted.offered ?? "nothing"}, not Resume`,
      {
        outcome: interrupted.outcome ?? null,
        row: interrupted.row ?? null,
      },
    );
  }
  if (resumed.resumeRequested !== true) {
    return fail("the click the window offered did not ask to resume");
  }
  const renewed = interrupted.windowChanged === true;
  if (
    renewed &&
    (!Number.isSafeInteger(interrupted.oldPid) ||
      !Number.isSafeInteger(interrupted.newPid) ||
      interrupted.oldPid === interrupted.newPid)
  )
    return fail(
      "the crash recovery did not establish a different owned window",
    );
  const reviews = renewed ? 1 : 0;
  if (resumed.reviewsShown !== reviews || resumed.answersSent !== reviews) {
    return fail("Resume of an unchanged plan showed the plan again", {
      reviewsShown: resumed.reviewsShown,
      answersSent: resumed.answersSent,
    });
  }
  if (!Array.isArray(resumed.rebuilt) || resumed.rebuilt.length > 0) {
    return fail(
      "a build finished before the interruption was downloaded again",
      {
        rebuilt: resumed.rebuilt ?? null,
      },
    );
  }
  if (!USABLE_STATES.includes(resumed.finalState)) {
    return fail(`after Resume the item ended ${resumed.finalState}`);
  }
  return pass(
    `${renewed ? "resumed in a new window after its fresh review" : "resumed without a second review"}; ${resumed.wireBytes} bytes moved after Resume`,
  );
}

/**
 * A second setup of an item that is set up changes nothing: it settles as
 * nothing to do without showing a plan, moves no more than the preflight does,
 * and leaves the installed files as they were.
 */
export function secondSetupVerdict({
  outcome,
  reviewsShown,
  wireBytes,
  changedPaths,
  allowanceBytes = NO_TRANSFER_ALLOWANCE_BYTES,
}) {
  if (outcome !== "nothing_to_do") {
    return fail(`the second setup ended ${outcome ?? "without an outcome"}`);
  }
  if (reviewsShown !== 0) {
    return fail("the second setup showed a plan for an item already set up");
  }
  if (!Number.isSafeInteger(wireBytes) || wireBytes > allowanceBytes) {
    return fail(
      `the second setup moved ${wireBytes} bytes, over the ${allowanceBytes}-byte allowance`,
    );
  }
  if (!Array.isArray(changedPaths) || changedPaths.length > 0) {
    return fail("the second setup changed installed files", {
      changed: Array.isArray(changedPaths) ? changedPaths.slice(0, 10) : null,
    });
  }
  return pass(`nothing to do; ${wireBytes} bytes moved, no file changed`);
}

const GUARDED_MEMBERS = new Set([
  "components",
  "models",
  "buckets",
  "active-profile",
  "keystore",
  "secrets",
  "tokens",
]);

/** The log a Chromium build writes beside its executable while it runs, whichever program launched it. */
const BROWSER_RUNTIME_LOG = "debug.log";

/**
 * Whether a real-storage change is one a setup or a profile of this run could
 * have made, rather than another program's. A change naming one of `marks` or
 * lying outside every watched root always counts. Under the per-user browser
 * cache every change counts but one: a browser's own runtime log, written
 * while no process of this run ran a browser from that cache. Another program
 * running its browser writes that log; a setup installing there would add,
 * replace or remove build files, and a browser this run launched from there
 * would itself be a failure of isolation.
 */
export function guardedChange(
  change,
  { roots, marks, browserCache, runCommandLines },
) {
  const kind = change.slice(0, change.indexOf(" "));
  const path = change.slice(change.indexOf(" ") + 1).replace(/\|absent$/, "");
  if (
    marks.some(
      (mark) => mark && path.toLowerCase().includes(mark.toLowerCase()),
    )
  )
    return true;
  const root = roots.find(
    (candidate) => path === candidate || path.startsWith(candidate + sep),
  );
  if (!root) return true;
  if (browserCache && root.toLowerCase() === browserCache.toLowerCase()) {
    const cache = browserCache.toLowerCase();
    const runUsedCache = runCommandLines.some((line) =>
      (line ?? "").toLowerCase().includes(cache),
    );
    return (
      runUsedCache ||
      kind === "removed" ||
      basename(path).toLowerCase() !== BROWSER_RUNTIME_LOG
    );
  }
  const parts = relative(root, path).split(sep).filter(Boolean);
  const member = parts[0] === "development" ? parts[1] : parts[0];
  return (
    member !== undefined &&
    (GUARDED_MEMBERS.has(member) || member.startsWith("profile-custody"))
  );
}

/**
 * Real storage is unchanged: no path changed under the places a setup or a
 * profile writes to. Other changes under the watched roots belong to whatever
 * else runs on the host and are reported, never hidden.
 */
export function realStorageVerdict({ guarded, observed }) {
  if (!Array.isArray(guarded) || !Array.isArray(observed)) {
    return fail("real storage was not listed before and after the run");
  }
  if (guarded.length > 0) {
    return fail(`${guarded.length} path(s) changed in real storage`, {
      changed: guarded.slice(0, 20),
    });
  }
  return pass(
    observed.length === 0
      ? "no path changed under any watched real storage root"
      : `no setup or profile path changed; ${observed.length} other change(s) under the watched roots, listed`,
    { otherChanges: observed.slice(0, 50) },
  );
}

// ---------------------------------------------------------------------------
// Isolation, measurement and cleanup
// ---------------------------------------------------------------------------

const STRIPPED_PREFIX = /^(CADRUMO_|WEBVIEW2_|PLAYWRIGHT_|OLLAMA_)/i;
const STRIPPED_PROXY = new Set([
  "http_proxy",
  "https_proxy",
  "all_proxy",
  "no_proxy",
]);
const BROWSER_BUILDS = ["chromium", "chromium_headless_shell"];
const COMPLETE_MARKER = "INSTALLATION_COMPLETE";

/** Every image a run may start, directly or through the runtime and its workers. */
export const TRACKED_PROCESSES = Object.freeze([
  "cadrumo.exe",
  "cadrumo-runtime.exe",
  "cadrumo-agent.exe",
  "cadrumo-agent-service.exe",
  "cadrumo-mcp.exe",
  "aeat.exe",
  "python.exe",
  "node.exe",
  "chrome.exe",
  "chrome-headless-shell.exe",
  "headless_shell.exe",
  "msedgewebview2.exe",
  "ollama.exe",
  "ollama_llama_server.exe",
  "llama-server.exe",
  "conhost.exe",
]);

/** Every location of one run, all inside its throwaway root. */
export function scratchLayout(root) {
  const storage = resolve(root, "storage");
  return {
    root,
    storage,
    local: resolve(root, "home", "local"),
    roaming: resolve(root, "home", "roaming"),
    temporary: resolve(root, "tmp"),
    browsers: resolve(storage, "components", "playwright"),
  };
}

/**
 * The environment of every process the run starts: the caller's, without
 * any Cadrumo, WebView2, Playwright, Ollama or proxy setting, with the storage
 * root, the per-user application data and the temporary directory inside the
 * throwaway root. Every other Cadrumo location derives from the storage root.
 */
export function isolatedEnvironment(base, layout, storageVariable) {
  const env = {};
  for (const [key, value] of Object.entries(base))
    if (!STRIPPED_PREFIX.test(key) && !STRIPPED_PROXY.has(key.toLowerCase()))
      env[key] = value;
  env[storageVariable] = layout.storage;
  env.LOCALAPPDATA = layout.local;
  env.APPDATA = layout.roaming;
  env.TEMP = layout.temporary;
  env.TMP = layout.temporary;
  env.TMPDIR = layout.temporary;
  return env;
}

/** Bytes of every regular file under `root`, by path, without following links. */
export function treeBytes(root) {
  let total = 0;
  const pending = [root];
  while (pending.length) {
    const directory = pending.pop();
    let entries;
    try {
      entries = readdirSync(directory, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const path = join(directory, entry.name);
      try {
        if (entry.isDirectory()) pending.push(path);
        else if (entry.isFile()) total += lstatSync(path).size;
      } catch {
        // A file removed while the tree is walked counts nothing.
      }
    }
  }
  return total;
}

/** Every file and directory under `roots` with its size and modification time. */
export function fingerprint(roots) {
  const found = new Map();
  for (const root of roots) {
    if (!existsSync(root)) {
      found.set(`${root}|absent`, "absent");
      continue;
    }
    const pending = [root];
    while (pending.length) {
      const path = pending.pop();
      let stat;
      try {
        stat = lstatSync(path, { bigint: true });
      } catch {
        continue;
      }
      const directory = stat.isDirectory();
      found.set(path, `${directory ? 0n : stat.size}:${stat.mtimeNs}`);
      if (!directory) continue;
      try {
        for (const entry of readdirSync(path)) pending.push(join(path, entry));
      } catch {
        // An unreadable directory keeps its own entry.
      }
    }
  }
  return found;
}

/** Every path added, removed or changed between two fingerprints. */
export function fingerprintChanges(before, after) {
  const changes = [];
  for (const path of after.keys())
    if (!before.has(path)) changes.push(`added ${path}`);
  for (const path of before.keys())
    if (!after.has(path)) changes.push(`removed ${path}`);
  for (const [path, value] of before)
    if (after.has(path) && after.get(path) !== value)
      changes.push(`changed ${path}`);
  return changes.sort();
}

/** The browser builds whose completion marker is present, with its time. */
export function completedBuilds(browsersRoot) {
  const found = {};
  let entries = [];
  try {
    entries = readdirSync(browsersRoot);
  } catch {
    return found;
  }
  for (const name of entries) {
    if (!BROWSER_BUILDS.some((build) => name.startsWith(build))) continue;
    const marker = resolve(browsersRoot, name, COMPLETE_MARKER);
    if (existsSync(marker)) found[name] = statSync(marker).mtimeMs;
  }
  return found;
}

/** Removes `root`, which must sit directly inside `parent`, and says whether it is gone. */
export async function removeScratch(root, parent) {
  if (resolve(root, "..") !== resolve(parent))
    throw new Error(
      `refusing to remove ${root}: it is not a run root inside ${parent}`,
    );
  try {
    rmSync(root, { recursive: true, force: true });
  } catch {
    return false;
  }
  return !existsSync(root);
}

/** Runs setup_probe.py under the packaged interpreter with `env`. */
export function probe(python, env, args, input) {
  const script = fileURLToPath(new URL("./setup_probe.py", import.meta.url));
  const result = spawnSync(python, ["-I", "-B", script, ...args], {
    env,
    input: input === undefined ? undefined : JSON.stringify(input),
    encoding: "utf8",
    timeout: 120000,
    maxBuffer: 4 * 1024 * 1024,
    windowsHide: true,
  });
  if (result.status !== 0)
    throw new Error(
      `setup probe ${args[0]} exited ${result.status}: ${(result.stderr ?? "").trim().split("\n").pop()}`,
    );
  return JSON.parse(result.stdout);
}

/**
 * A loopback CONNECT proxy that counts tunnelled bytes, so what a setup moved
 * is measured on the wire rather than taken from the installer's word.
 */
export class CountingProxy {
  constructor() {
    this.downstream = 0;
    this.upstream = 0;
    this.tunnels = 0;
    this.hosts = new Set();
    this.sockets = new Set();
    this.refusing = false;
    this.refusals = 0;
    this.gates = new Set();
  }

  /** Hold real encrypted transfer bytes after a bounded amount has passed. */
  hold(hosts, afterBytes = 512 * 1024) {
    const gate = {
      hosts: new Set(hosts),
      bytes: 0,
      sockets: new Set(),
      released: false,
    };
    gate.held = new Promise((resolve) => {
      gate.resolve = resolve;
    });
    gate.release = () => {
      gate.released = true;
      for (const socket of gate.sockets) socket.resume();
      this.gates.delete(gate);
    };
    gate.afterBytes = afterBytes;
    this.gates.add(gate);
    return gate;
  }

  /** Change only this harness-owned network boundary; no product switch. */
  refuse(value) {
    this.refusing = value;
    for (const socket of this.sockets) socket.destroy();
  }

  async start() {
    this.server = createServer((_request, response) => {
      response.writeHead(405, { "content-length": 0 });
      response.end();
    });
    this.server.on("connect", (request, client, head) => {
      if (this.refusing) {
        this.refusals += 1;
        client.end(
          "HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n",
        );
        return;
      }
      const authority = String(request.url ?? "");
      const split = authority.lastIndexOf(":");
      const host = authority.slice(0, split).replace(/^\[|\]$/g, "");
      const port = authority.slice(split + 1);
      if (split <= 0 || !/^\d+$/.test(port)) {
        client.end(
          "HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n",
        );
        return;
      }
      this.tunnels += 1;
      this.hosts.add(host);
      const upstream = netConnect(Number(port), host);
      for (const socket of [client, upstream]) {
        this.sockets.add(socket);
        socket.on("close", () => this.sockets.delete(socket));
        socket.on("error", () => undefined);
      }
      upstream.once("connect", () => {
        client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
        if (head?.length) {
          this.upstream += head.length;
          upstream.write(head);
        }
        upstream.on("data", (chunk) => {
          this.downstream += chunk.length;
          for (const gate of this.gates) {
            if (gate.released || !gate.hosts.has(host)) continue;
            gate.bytes += chunk.length;
            if (gate.bytes >= gate.afterBytes) {
              gate.sockets.add(upstream);
              upstream.pause();
              gate.resolve({
                host,
                bytes: gate.bytes,
                at: new Date().toISOString(),
              });
            }
          }
        });
        client.on("data", (chunk) => {
          this.upstream += chunk.length;
        });
        upstream.pipe(client);
        client.pipe(upstream);
      });
      upstream.once("error", () => {
        if (!client.destroyed)
          client.end("HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n");
      });
      client.on("close", () => upstream.destroy());
      upstream.on("close", () => client.destroy());
    });
    await new Promise((done) => this.server.listen(0, "127.0.0.1", done));
    this.port = this.server.address().port;
    return this;
  }

  get url() {
    return `http://127.0.0.1:${this.port}`;
  }

  async stop() {
    for (const gate of [...this.gates]) gate.release();
    for (const socket of this.sockets) socket.destroy();
    if (this.server) await new Promise((done) => this.server.close(done));
  }
}

// ---------------------------------------------------------------------------
// The window driver
// ---------------------------------------------------------------------------

// The one provisioning panel: one row per element, each with its own
// action, plan review and approval. Settings' provisioning section opens it.
const DIALOG = ".setup-dialog";
const ROW = (item) => `${DIALOG} .setup-components [data-setup-row="${item}"]`;
const ROW_BUTTON = (item) => `${ROW(item)} > button`;
/** The row's plan review; its last button approves the plan. */
const APPROVE_BUTTON = (item) => `${ROW(item)} [data-setup-review] button`;
const OPEN_PANEL = "[data-settings-provisioning] button";

/** Install once per document: records every time a plan is rendered for review. */
function watchReviews() {
  if (window.__setupReviews) return;
  const seen = [];
  window.__setupReviews = seen;
  const scan = () => {
    const items = [...document.querySelectorAll("[data-setup-plan]")].map(
      (element) => element.getAttribute("data-setup-plan"),
    );
    const last = seen[seen.length - 1];
    if (items.length && (!last || last.gone))
      seen.push({ at: Date.now(), items, gone: null });
    else if (!items.length && last && !last.gone) last.gone = Date.now();
  };
  new MutationObserver(scan).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  scan();
}

/** The closed fields of each row that a run records. */
export function compactRows(rows) {
  return rows.map((row) => ({
    item: row.item,
    mode: row.mode,
    state: row.state,
    failure: row.failure,
    recovery: row.recovery,
    size_bytes: row.size_bytes,
    version: row.version,
    note: row.note,
  }));
}

/** The item's own setup in a snapshot: each item runs on its own. */
export function runOf(snapshot, item) {
  return snapshot?.runs?.find((run) => run.item === item) ?? null;
}

/** Await the existing UI subscription, without replacing its sole listener. */
export function waitSetupSignal(session, wanted, timeout = 120000) {
  return session.shell(
    ({ wanted, timeout }) =>
      new Promise((resolve, reject) => {
        const matches = (value) => {
          const snapshot = value?.snapshot;
          if (!snapshot) return false;
          return wanted.every(
            ({
              item,
              stage,
              outcome,
              operationId,
              state,
              failure,
              recovery,
            }) => {
              const wantsRow =
                state !== undefined ||
                failure !== undefined ||
                recovery !== undefined;
              const wantsRun =
                !wantsRow ||
                stage !== undefined ||
                outcome !== undefined ||
                operationId !== undefined;
              const row = snapshot.rows?.find((entry) => entry.item === item);
              if (
                wantsRow &&
                (!row ||
                  (state !== undefined && row.state !== state) ||
                  (failure !== undefined && row.failure !== failure) ||
                  (recovery !== undefined && row.recovery !== recovery))
              )
                return false;
              const run = snapshot.runs?.find((entry) => entry.item === item);
              return (
                !wantsRun ||
                (run &&
                  (!stage || run.stage === stage) &&
                  (!outcome || run.outcome === outcome) &&
                  (!operationId || run.operation_id === operationId))
              );
            },
          );
        };
        let timer;
        const finish = (value, error) => {
          clearTimeout(timer);
          window.removeEventListener("packaged-setup-snapshot", receive);
          if (error) reject(error);
          else resolve(value);
        };
        const receive = (event) => {
          if (matches(event.detail)) finish(event.detail);
        };
        window.addEventListener("packaged-setup-snapshot", receive);
        timer = setTimeout(
          () => finish(null, new Error("setup signal deadline")),
          timeout,
        );
        if (matches(window.__s10.setupLatest)) finish(window.__s10.setupLatest);
      }),
    { wanted, timeout },
  );
}

/** DOM updates, rather than elapsed time, decide when the rail has rendered. */
async function spinnerSignal(session, present) {
  return session.shell(
    (present) =>
      new Promise((resolve, reject) => {
        const selector = '[data-rail="settings"] [data-pin="busy"]';
        let timer;
        const observer = new MutationObserver(check);
        function check() {
          if (!!document.querySelector(selector) !== present) return;
          observer.disconnect();
          clearTimeout(timer);
          const spinner = document.querySelector(selector);
          const pin = spinner?.getBoundingClientRect();
          const button = spinner?.closest("button")?.getBoundingClientRect();
          const overlay =
            !present ||
            !!(
              pin &&
              button &&
              pin.width < button.width &&
              pin.x + pin.width / 2 > button.x + button.width / 2 &&
              pin.y + pin.height / 2 < button.y + button.height / 2
            );
          resolve({ present, overlay });
        }
        observer.observe(document.documentElement, {
          childList: true,
          subtree: true,
          attributes: true,
        });
        timer = setTimeout(() => {
          observer.disconnect();
          reject(new Error("rail spinner deadline"));
        }, 10000);
        check();
      }),
    present,
  );
}

export function concurrentSetupVerdict(evidence) {
  const browser = runOf(evidence?.overlap?.snapshot, "browser");
  const localAi = runOf(evidence?.overlap?.snapshot, "local_ai");
  if (browser?.stage !== "running" || localAi?.stage !== "running")
    return fail("the two real setup runs did not overlap", evidence);
  if (!evidence.browserWire?.bytes || !evidence.localAiWire?.bytes)
    return fail("both real transfers were not observed", evidence);
  if (
    !evidence.controls?.browserCancel ||
    !evidence.controls?.localAiCancel ||
    !evidence.controls?.modelHeld
  )
    return fail(
      "the rows did not keep independent cancel controls while holding model downloads",
      evidence,
    );
  if (evidence.browserActionAfterCancel !== true)
    return fail(
      "the idle browser stayed busy while only local AI ran",
      evidence,
    );
  const cancelled = runOf(evidence?.cancelled?.snapshot, "browser");
  const surviving = runOf(evidence?.cancelled?.snapshot, "local_ai");
  if (
    cancelled?.outcome !== "cancelled" ||
    surviving?.stage !== "running" ||
    surviving.operation_id !== localAi.operation_id
  )
    return fail(
      "cancelling the browser did not leave the same local AI run live",
      evidence,
    );
  if (
    evidence?.spinnerDuring?.present !== true ||
    evidence?.spinnerAfterCancel?.present !== true ||
    evidence?.spinnerAfter?.present !== false
  )
    return fail("the global spinner did not follow all live runs", evidence);
  if (!evidence.spinnerDuring.overlay || !evidence.spinnerAfterCancel.overlay)
    return fail(
      "the rail spinner was not an overlay on the Settings button",
      evidence,
    );
  return pass(
    "real browser and local AI transfers overlapped; browser cancellation left local AI live; the rail followed both",
    evidence,
  );
}

/** Leaves both runs cancelled so the existing browser resume lane can follow. */
export async function runConcurrentSetup(
  driver,
  { lane, model },
  onReview = async () => {},
) {
  const { session, proxy } = driver;
  const evidence = {};
  const gates = [];
  try {
    await driver.openComponents();
    const disclosure = session.page.locator(
      `${DIALOG} [data-setup-element="local_ai"] > button`,
    );
    if ((await disclosure.getAttribute("aria-expanded")) !== "true")
      await disclosure.click();
    await driver.click(ROW_BUTTON("browser"), "browser setup");
    await waitSetupSignal(session, [{ item: "browser", stage: "review" }]);
    await session.page
      .locator(`${DIALOG} [data-model="${CSSescape(model)}"] button`)
      .first()
      .click();
    const reviews = await waitSetupSignal(session, [
      { item: "browser", stage: "review" },
      { item: "local_ai", stage: "review" },
    ]);
    await onReview(reviews.snapshot);
    for (const item of ["browser", "local_ai"]) {
      const run = runOf(reviews.snapshot, item);
      const hosts = [
        ...new Set(run.review.entries.flatMap((entry) => entry.source_hosts)),
      ];
      if (!Array.isArray(hosts) || hosts.length === 0)
        throw new Error(`${item} review names no hosts`);
      gates.push(proxy.hold(hosts));
      await driver.click(
        `${APPROVE_BUTTON(item)}:last-child`,
        `${item} approval`,
      );
      if (item === "browser") {
        const answer = (await driver.setupCommands())
          .filter(
            (entry) =>
              entry.cmd === "desktop_setup_answer" &&
              entry.args?.decision === "apply",
          )
          .at(-1);
        driver.approvals.push({
          itemIds: [item],
          digest: run.review.plan_digest,
          at: new Date(answer.at).toISOString(),
        });
      }
    }
    evidence.overlap = await waitSetupSignal(session, [
      { item: "browser", stage: "running" },
      { item: "local_ai", stage: "running" },
    ]);
    await Promise.all(
      ["browser", "local_ai"].map((item) =>
        session.page
          .locator(`${ROW(item)} [data-setup-progress]`)
          .waitFor({ state: "visible", timeout: 30000 }),
      ),
    );
    evidence.controls = await session.shell((model) => {
      const cancel = (item) => {
        const button = document.querySelector(
          `[data-setup-row="${item}"] button`,
        );
        return !!button && !button.disabled;
      };
      const modelButton = document.querySelector(
        `[data-model="${CSS.escape(model)}"] button`,
      );
      return {
        browserCancel: cancel("browser"),
        localAiCancel: cancel("local_ai"),
        modelHeld: !!modelButton?.disabled,
      };
    }, model);
    [evidence.browserWire, evidence.localAiWire] = await Promise.all(
      gates.map((gate) =>
        Promise.race([
          gate.held,
          new Promise((_, reject) => {
            const timer = setTimeout(
              () => reject(new Error("real transfer gate deadline")),
              120000,
            );
            gate.held.finally(() => clearTimeout(timer));
          }),
        ]),
      ),
    );
    evidence.spinnerDuring = await spinnerSignal(session, true);
    const browser = runOf(evidence.overlap.snapshot, "browser");
    driver.operationId = browser.operation_id;
    driver.review = runOf(reviews.snapshot, "browser").review;
    driver.completeAtCut = completedBuilds(driver.layout.browsers);
    await driver.click(`${ROW("browser")} button`, "cancel browser only");
    gates[0].release();
    evidence.cancelled = await waitSetupSignal(session, [
      {
        item: "browser",
        stage: "settled",
        outcome: "cancelled",
        operationId: browser.operation_id,
      },
      {
        item: "local_ai",
        stage: "running",
        operationId: runOf(evidence.overlap.snapshot, "local_ai").operation_id,
      },
    ]);
    evidence.spinnerAfterCancel = await spinnerSignal(session, true);
    evidence.browserActionAfterCancel = await session.shell(
      () =>
        new Promise((resolve, reject) => {
          const inspect = () => {
            const row = document.querySelector('[data-setup-row="browser"]');
            const button = row?.querySelector("button");
            if (
              button &&
              !button.disabled &&
              !row.querySelector("[data-setup-progress], [data-setup-review]")
            ) {
              observer.disconnect();
              clearTimeout(timer);
              resolve(true);
            }
          };
          const observer = new MutationObserver(inspect);
          observer.observe(document, {
            childList: true,
            subtree: true,
            attributes: true,
          });
          const timer = setTimeout(() => {
            observer.disconnect();
            reject(new Error("idle browser remained busy"));
          }, 10000);
          inspect();
        }),
    );
    driver.cancelledTransfer = {
      wireBytes: evidence.browserWire.bytes,
      offered: evidence.cancelled.snapshot.rows.find(
        (row) => row.item === "browser",
      )?.recovery,
      outcome: "cancelled",
    };
    driver.firstTransferAt = evidence.browserWire.at;
    driver.concurrencyChecked = true;
    await driver.click(
      `${ROW("local_ai")} button`,
      "cancel local AI independently",
    );
    gates[1].release();
    evidence.settled = await waitSetupSignal(session, [
      { item: "browser", stage: "settled", outcome: "cancelled" },
      { item: "local_ai", stage: "settled", outcome: "cancelled" },
    ]);
    evidence.spinnerAfter = await spinnerSignal(session, false);
    driver.note("concurrent-setup", { lane, model, ...evidence });
    return concurrentSetupVerdict(evidence);
  } finally {
    for (const gate of gates) gate.release();
  }
}

function CSSescape(value) {
  return String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

/** Judge the actual failed run, its rendered sentence and its local records. */
export function setupFailureVerdict(observation) {
  const {
    run,
    expectedSentence,
    sentences,
    action,
    refusals,
    events,
    records,
  } = observation;
  if (!(refusals > 0))
    return fail(
      "the packaged engine never reached the refusing proxy",
      observation,
    );
  if (
    run?.stage !== "settled" ||
    run.outcome !== "failed" ||
    run.failure !== "blocked_by_network"
  )
    return fail(
      "the setup did not settle with the induced network failure",
      observation,
    );
  if (
    !expectedSentence ||
    /Cadrumo refused that request[.!]?/i.test(expectedSentence) ||
    sentences?.length !== 1 ||
    sentences[0] !== expectedSentence
  )
    return fail(
      "the row does not show the canonical failure sentence exactly once",
      observation,
    );
  if (!action?.trim())
    return fail("the failed row offers no recovery action", observation);
  const matches = (event) =>
    event.kind === "failure" &&
    event.source === "desktop" &&
    event.failure?.code === "setup_failed" &&
    event.failure?.reason === "setup_browser_failed" &&
    event.failure?.causes?.some(
      (cause) =>
        cause.kind === "application" &&
        cause.code === "setup_failed" &&
        cause.reason === "blocked_by_network",
    );
  if (events?.length !== 1 || !matches(events[0]))
    return fail(
      "the setup failure was not recorded exactly once in diagnostics",
      observation,
    );
  if (
    records?.length !== 1 ||
    !matches(records[0]) ||
    records[0].sequence !== events[0].sequence ||
    records[0].hostPid !== events[0].hostPid
  )
    return fail(
      "the same failure was not persisted exactly once in the local log",
      observation,
    );
  return pass(
    "the setup failed with its plain sentence, recovery action and one local failure record",
    observation,
  );
}

/** Before successful setup: refuse real CONNECTs, then restore the normal route. */
export async function runSetupFailureAcceptance({ driver, expectedSentence }) {
  if (driver.item !== "browser")
    throw new Error("the failure acceptance requires the browser row");
  const before = await driver.session.call("diagnostics_snapshot", {
    after: 0,
  });
  if (!before.ok)
    return fail("diagnostics could not be read before inducing failure");
  const prior = new Set(
    before.value.events.map((event) => `${event.hostPid}:${event.sequence}`),
  );
  const refusals = driver.proxy.refusals;
  driver.proxy.refuse(true);
  try {
    const started = await driver.session.call("desktop_setup_start", {
      item: driver.item,
      resume: false,
    });
    if (!started.ok)
      return fail(
        "the normal setup start was refused before a run was created",
        started,
      );
    const operation = runOf(started.value.snapshot, driver.item)?.operation_id;
    const setup = await driver.wait(
      async () => {
        const read = await driver.read();
        const run = runOf(read.snapshot, driver.item);
        return run &&
          (!operation || run.operation_id === operation) &&
          run.stage === "settled"
          ? read
          : null;
      },
      { timeout: 30000, what: "the real setup's network refusal" },
    );
    await driver.openComponents();
    const row = driver.session.page.locator(ROW(driver.item));
    await row
      .locator("[data-setup-sentence]")
      .filter({ hasText: expectedSentence })
      .waitFor({ state: "visible", timeout: 10000 });
    const sentences = await row
      .locator("[data-setup-sentence]")
      .allTextContents();
    const action = await row
      .locator("button:visible")
      .first()
      .innerText()
      .catch(() => "");
    const fresh = (event) =>
      !prior.has(`${event.hostPid}:${event.sequence}`) &&
      event.kind === "failure" &&
      event.failure?.reason === "setup_browser_failed";
    // Diagnostics writes Event JSON lines asynchronously; await its actual persisted record.
    const evidence = await driver.wait(
      async () => {
        const answer = await driver.session.call("diagnostics_snapshot", {
          after: 0,
        });
        if (!answer.ok || !answer.value.paths?.current) return null;
        const path = answer.value.paths.current;
        if (!strictlyInside(driver.layout.root, path))
          throw new Error("the native log escaped the throwaway root");
        let records;
        try {
          const lines = readFileSync(path, "utf8").split("\n");
          lines.pop(); // An incomplete final line is still being written.
          records = lines
            .filter(Boolean)
            .map((line) => JSON.parse(line))
            .filter(fresh);
        } catch {
          return null;
        }
        return records.length
          ? { events: answer.value.events.filter(fresh), records }
          : null;
      },
      {
        timeout: 10000,
        what: "the setup failure's persisted local log event",
        fatal: (error) =>
          /escaped the throwaway root/.test(error?.message ?? ""),
      },
    );
    const observation = {
      run: runOf(setup.snapshot, driver.item),
      expectedSentence,
      sentences: sentences.map((sentence) => sentence.trim()),
      action,
      refusals: driver.proxy.refusals - refusals,
      ...evidence,
    };
    driver.note("induced-setup-failure", observation);
    return setupFailureVerdict(observation);
  } finally {
    driver.proxy.refuse(false);
  }
}

/**
 * Drives the packaged window through the browser setup as a person would:
 * Settings, the provisioning panel, the row's own button, the plan, the
 * row's approval, then Resume after a forced interruption. Clicks go through the page; every
 * reading comes from the host's own setup commands, the window's IPC trace
 * and the rendered document.
 */
export class SetupDriver {
  constructor({
    session,
    input,
    signIn,
    layout,
    proxy,
    item = "browser",
    restartAfterCrash,
  }) {
    this.session = session;
    this.input = input;
    this.signIn = signIn;
    this.layout = layout;
    this.proxy = proxy;
    this.item = item;
    this.restartAfterCrash = restartAfterCrash;
    this.abortReason = null;
    this.approvals = [];
    this.timeline = [];
  }

  /** Stops every wait: the watchdog or a failed step ended the run. */
  abort(reason) {
    this.abortReason ??= reason;
  }

  note(event, data = {}) {
    this.timeline.push({ at: new Date().toISOString(), event, ...data });
  }

  async wait(read, options) {
    return waitFor(
      async () => {
        if (this.abortReason) throw new Error(`aborted: ${this.abortReason}`);
        return read();
      },
      {
        interval: 250,
        ...options,
        fatal: (error) =>
          String(error?.message).startsWith("aborted:") ||
          options?.fatal?.(error) === true,
      },
    );
  }

  async read() {
    const answer = await this.session.call("desktop_setup_read");
    if (!answer.ok)
      throw new Error(
        `desktop_setup_read failed: ${answer.error?.code ?? "unknown"}`,
      );
    return answer.value;
  }

  row(setup, item = this.item) {
    return setup?.snapshot?.rows.find((row) => row.item === item) ?? null;
  }

  async setupCommands(after = 0) {
    return this.session.shell(
      (after) =>
        window.__s10.ipc
          .filter(
            (entry) =>
              entry.by === "shell" &&
              entry.seq > after &&
              entry.cmd.startsWith("desktop_setup_"),
          )
          .map(({ seq, at, cmd, args, ok, code }) => ({
            seq,
            at,
            cmd,
            args,
            ok,
            code,
          })),
      after,
    );
  }

  async lastSequence() {
    return this.session.shell(() => window.__s10.ipc.at(-1)?.seq ?? 0);
  }

  async reviewsRendered() {
    return this.session.shell(() =>
      window.__setupReviews
        ? window.__setupReviews.map((review) => ({ ...review }))
        : null,
    );
  }

  async visible(selector) {
    return this.session.page
      .locator(selector)
      .first()
      .isVisible()
      .catch(() => false);
  }

  async click(selector, what) {
    const target = this.session.page.locator(selector).last();
    await target.waitFor({ state: "visible", timeout: 30000 });
    const label = (await target.innerText()).trim();
    await target.click();
    this.note("click", { what, label });
    return label;
  }

  async closeDialog() {
    for (
      let attempt = 0;
      attempt < 5 && (await this.visible(DIALOG));
      attempt += 1
    ) {
      await this.session.page.keyboard.press("Escape");
      await this.session.page
        .locator(DIALOG)
        .waitFor({ state: "hidden", timeout: 10000 });
    }
    return !(await this.visible(DIALOG));
  }

  /** The provisioning panel, opened from Settings' one section, with this item's row. */
  async openComponents() {
    if (await this.visible(ROW(this.item))) return;
    await this.closeDialog();
    if (!(await this.visible(OPEN_PANEL)))
      await this.click("[data-rail=settings]", "the Settings rail item");
    await this.click(OPEN_PANEL, "Settings' provisioning button");
    await this.session.page
      .locator(ROW(this.item))
      .waitFor({ state: "visible", timeout: 60000 });
  }

  /** The signed-in window's first reading of the components, on a clean root. */
  async rowsBefore() {
    await this.session.shell(watchReviews);
    const setup = await this.wait(
      async () => {
        const read = await this.read();
        return read.state === "ready" && read.snapshot?.rows.length
          ? read
          : null;
      },
      { timeout: 180000, what: "the first status read of the components" },
    );
    this.rows = setup.snapshot.rows;
    const row = this.row(setup);
    this.note("rows-before", { rows: compactRows(this.rows) });
    const dismissed = await this.closeDialog();
    if (row?.state !== "absent")
      return fail(`a clean root read the ${this.item} as ${row?.state}`, {
        rows: compactRows(this.rows),
      });
    return pass(
      `${this.rows.length} rows; ${this.item} absent on the clean root${dismissed ? "; the first-run panel closed" : ""}`,
      { rows: compactRows(this.rows) },
    );
  }

  /** The row's own button in the panel shows the plan inside the row. */
  async showPlan() {
    await this.openComponents();
    this.rowLabel = await this.click(ROW_BUTTON(this.item), "the row's button");
    const setup = await this.wait(
      async () => {
        const read = await this.read();
        return runOf(read.snapshot, this.item)?.stage === "review" &&
          (await this.visible(`${ROW(this.item)} [data-setup-plan]`))
          ? read
          : null;
      },
      { timeout: 240000, what: "the setup plan for review" },
    );
    const run = runOf(setup.snapshot, this.item);
    this.operationId = run.operation_id;
    this.review = run.review;
    const rendered = await this.session.shell(() =>
      [...document.querySelectorAll("[data-setup-plan]")].map((entry) => ({
        item: entry.getAttribute("data-setup-plan"),
        text: entry.innerText.slice(0, 400),
      })),
    );
    this.note("review", { review: this.review, rendered });
    const items = this.review.entries.map((entry) => entry.item);
    if (items.length !== 1 || items[0] !== this.item)
      return fail(`the plan names ${items.join(", ")}, not only ${this.item}`);
    if (!(this.review.known_download_bytes > 0))
      return fail("the plan does not state what it downloads");
    if (!this.review.space_sufficient)
      return fail("the plan says the volume is too full");
    return pass(
      `"${this.rowLabel}": ${this.review.known_download_bytes} bytes from ${this.review.entries[0].source_hosts.join(", ")}`,
      { review: this.review, rendered },
    );
  }

  /** The person approves the plan the row shows. */
  async approve() {
    const before = await this.lastSequence();
    this.phaseApprovalStart = this.approvals.length;
    if (this.restartAfterCrash) {
      this.crashGate = this.proxy.hold(
        [
          ...new Set(
            this.review.entries.flatMap((entry) => entry.source_hosts),
          ),
        ],
        INTERRUPT_AFTER_BYTES,
      );
    }
    this.approveLabel = await this.click(
      APPROVE_BUTTON(this.item),
      "the row's approve button",
    );
    const answer = await this.wait(
      async () =>
        (await this.setupCommands(before)).find(
          (entry) => entry.cmd === "desktop_setup_answer" && entry.ok !== null,
        ),
      { timeout: 30000, what: "the window's answer to the plan" },
    );
    if (answer.ok !== true || answer.args?.decision !== "apply")
      return fail(
        `the answer was ${JSON.stringify(answer.args)} (${answer.code})`,
      );
    if (answer.args.planDigest !== this.review.plan_digest)
      return fail("the window answered a plan other than the one it showed");
    this.approvals.push({
      itemIds: this.review.entries.map((entry) => entry.item),
      digest: answer.args.planDigest,
      at: new Date(answer.at).toISOString(),
    });
    this.wireAtApproval = this.proxy.downstream;
    return pass(`approved with "${this.approveLabel}"`, {
      digest: answer.args.planDigest,
    });
  }

  /** Interrupt this native run once real transfer bytes cross the threshold. */
  async interrupt() {
    if (this.restartAfterCrash) {
      if (!this.crashGate)
        return fail("the browser transfer was not gated before approval");
      let timer;
      try {
        const transfer = await Promise.race([
          this.crashGate.held,
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(new Error("transfer threshold deadline")),
              20 * 60 * 1000,
            );
          }),
        ]);
        const setup = await this.read();
        const run = runOf(setup.snapshot, this.item);
        if (run?.stage !== "running")
          return fail(
            "the browser was no longer running at the crash boundary",
            { run },
          );
        this.completeAtCut = completedBuilds(this.layout.browsers);
        this.firstTransferAt = transfer.at;
        this.cut = {
          at: new Date().toISOString(),
          wireBytes: transfer.bytes,
          movedBytes: transfer.bytes,
          operationId: run.operation_id,
          completeBuilds: Object.keys(this.completeAtCut),
          priorPlanDigest: this.review.plan_digest,
        };
        const restarted = await this.restartAfterCrash(this.cut);
        if (
          !restarted?.session ||
          !Number.isSafeInteger(restarted.oldPid) ||
          !Number.isSafeInteger(restarted.newPid) ||
          restarted.oldPid === restarted.newPid
        )
          return fail(
            "the crash callback did not return a different owned window",
          );
        this.session = restarted.session;
        this.crashWindows = {
          oldPid: restarted.oldPid,
          newPid: restarted.newPid,
        };
        await this.session.shell(watchReviews);
        this.note("crash-relaunch", { ...this.cut, ...this.crashWindows });
        return pass(
          "the owned GUI was killed during a held transfer and relaunched",
          { ...this.cut, ...this.crashWindows },
        );
      } finally {
        clearTimeout(timer);
        this.crashGate.release();
        this.crashGate = null;
      }
    }
    const cut = await this.session.shell(
      ({ item, threshold }) =>
        new Promise((resolve, reject) => {
          let timer;
          const receive = (event) => {
            const run = event.detail?.snapshot?.runs.find(
              (entry) => entry.item === item,
            );
            const progress = run?.items.find((entry) => entry.item === item);
            if (run?.stage === "settled")
              finish(
                null,
                new Error(
                  `setup settled ${run.outcome} before transfer threshold`,
                ),
              );
            else if ((progress?.completed ?? 0) >= threshold)
              finish({ operationId: run.operation_id, progress });
          };
          const finish = (value, error) => {
            clearTimeout(timer);
            window.removeEventListener("packaged-setup-snapshot", receive);
            if (error) reject(error);
            else resolve(value);
          };
          window.addEventListener("packaged-setup-snapshot", receive);
          timer = setTimeout(
            () => finish(null, new Error("transfer threshold deadline")),
            20 * 60 * 1000,
          );
          receive({ detail: window.__s10.setupLatest });
        }),
      { item: this.item, threshold: INTERRUPT_AFTER_BYTES },
    );
    this.completeAtCut = completedBuilds(this.layout.browsers);
    const answer = await this.session.call("desktop_setup_cancel", {
      operationId: cut.operationId,
    });
    if (!answer.ok)
      return fail("the per-item native cancellation was refused", answer);
    this.cut = {
      at: new Date().toISOString(),
      wireBytes: this.proxy.downstream - this.wireAtApproval,
      movedBytes: cut.progress.completed,
      completed: cut.progress.completed,
      total: cut.progress.total,
      step: cut.progress.step,
      completeBuilds: Object.keys(this.completeAtCut),
      operationId: cut.operationId,
    };
    this.note("cancel", this.cut);
    await waitSetupSignal(this.session, [
      {
        item: this.item,
        stage: "settled",
        outcome: "cancelled",
        operationId: cut.operationId,
      },
    ]);
    return pass(
      "cancelled this native setup after real transfer progress",
      this.cut,
    );
  }

  /** What the window shows once the interruption settled, signing in again if it ended the session. */
  async afterInterruption() {
    if (this.crashWindows) {
      const setup = await waitSetupSignal(
        this.session,
        [
          {
            item: this.item,
            state: "failed",
            failure: "interrupted",
            recovery: "resume",
          },
        ],
        120000,
      );
      await this.openComponents();
      this.interrupted = {
        wireBytes: this.cut.movedBytes,
        offered: this.row(setup).recovery,
        outcome: "interrupted",
        row: compactRows([this.row(setup)])[0],
        windowChanged: true,
        ...this.crashWindows,
      };
      this.note("after-interruption", this.interrupted);
      return pass(
        "the relaunched app reports failed/interrupted and offers Resume",
        this.interrupted,
      );
    }
    const signedInAgain = false;
    const setup = await waitSetupSignal(this.session, [
      {
        item: this.item,
        stage: "settled",
        outcome: "cancelled",
        operationId: this.operationId,
      },
    ]);
    const run = runOf(setup.snapshot, this.item);
    const row = this.row(setup);
    const dialog = await this.visible(DIALOG);
    const outcome = run?.operation_id === this.operationId ? run.outcome : null;
    // The button the window offers is the row's own, worded from its
    // recovery, whether or not the panel is open.
    const offered = row?.recovery ?? null;
    this.interrupted = {
      wireBytes: this.cut?.movedBytes ?? 0,
      outcome,
      offered,
      dialog,
      signedInAgain,
      row: row && compactRows([row])[0],
    };
    this.note("after-interruption", this.interrupted);
    const detail = `${signedInAgain ? "signed in again; " : ""}${dialog ? `dialog outcome ${outcome}` : "no dialog"}; row ${row?.state}/${row?.failure ?? "none"}, offers ${offered ?? "nothing"}`;
    return row && ["failed", "absent"].includes(row.state)
      ? pass(detail, this.interrupted)
      : fail(detail, this.interrupted);
  }

  /** The person clicks what the window offers, then the setup runs to its end. */
  async resume() {
    const reviewsBefore = (await this.reviewsRendered())?.length ?? 0;
    const before = await this.lastSequence();
    await this.openComponents();
    this.resumeLabel = await this.click(
      ROW_BUTTON(this.item),
      "the row's button",
    );
    const started = await this.wait(
      async () =>
        (await this.setupCommands(before)).find(
          (entry) => entry.cmd === "desktop_setup_start" && entry.ok !== null,
        ),
      { timeout: 30000, what: "the window's setup start" },
    );
    if (started.ok !== true)
      return fail(
        `the window's start after the interruption was refused: ${started.code}`,
        { started },
      );
    const wireAtResume = this.proxy.downstream;
    let answersSent = 0;
    let resumedOperation = null;
    const settled = await this.wait(
      async () => {
        const read = await this.read();
        const run = runOf(read.snapshot, this.item);
        if (!run || run.operation_id === this.operationId) return null;
        resumedOperation = run.operation_id;
        if (run.stage === "review" && run.review) {
          // A second plan on show: record it, then approve it so the run
          // still reaches the full check and the second setup.
          const sequence = await this.lastSequence();
          await this.click(
            APPROVE_BUTTON(this.item),
            "the row's approve button of a second plan",
          );
          const answer = await this.wait(
            async () =>
              (await this.setupCommands(sequence)).find(
                (entry) =>
                  entry.cmd === "desktop_setup_answer" && entry.ok !== null,
              ),
            { timeout: 30000, what: "the answer to the second plan" },
          );
          if (
            !answer.ok ||
            answer.args?.decision !== "apply" ||
            answer.args?.planDigest !== run.review.plan_digest
          )
            throw new Error(
              "the new window did not approve the exact plan it showed",
            );
          answersSent += 1;
          this.approvals.push({
            itemIds: run.review.entries.map((entry) => entry.item),
            digest: answer.args?.planDigest ?? null,
            at: new Date(answer.at).toISOString(),
          });
          return null;
        }
        return run.stage === "settled" ? read : null;
      },
      { timeout: 30 * 60 * 1000, what: "the resumed setup to finish" },
    );
    this.setupSettledAt = new Date().toISOString();
    const reviews = (await this.reviewsRendered()) ?? [];
    const after = completedBuilds(this.layout.browsers);
    const run = runOf(settled.snapshot, this.item);
    this.resumed = {
      label: this.resumeLabel,
      resumeRequested: started.args?.resume === true,
      reviewsShown: reviews.length - reviewsBefore,
      answersSent,
      operationId: resumedOperation,
      outcome: run.outcome,
      items: run.items,
      wireBytes: this.proxy.downstream - wireAtResume,
      rebuilt: Object.keys(this.completeAtCut ?? {}).filter(
        (name) => after[name] !== this.completeAtCut[name],
      ),
      completeBuilds: Object.keys(after),
      finalState: this.row(settled)?.state ?? null,
    };
    this.note("resumed", this.resumed);
    if (this.interrupted?.outcome !== "cancelled")
      return browserResumeVerdict({
        interrupted: this.interrupted,
        resumed: this.resumed,
      });
    const reviewedRetry =
      this.resumed.resumeRequested === false &&
      this.resumed.reviewsShown === 1 &&
      this.resumed.answersSent === 1;
    return reviewedRetry && USABLE_STATES.includes(this.resumed.finalState)
      ? pass(
          "cancelled setup retried after one fresh plan review and finished usable",
          this.resumed,
        )
      : fail(
          "cancelled setup did not retry through its fresh plan review",
          this.resumed,
        );
  }

  /** The app's own full check of the item, asked for after setup settled. */
  async fullCheck() {
    this.setupSettledAt ??= new Date().toISOString();
    const requested = await this.session.call("desktop_setup_verify", {
      items: [this.item],
    });
    if (!requested.ok)
      return fail(
        `desktop_setup_verify refused: ${requested.error?.code ?? "unknown"}`,
      );
    const operation = requested.value.snapshot?.check?.operation_id ?? null;
    const setup = await this.wait(
      async () => {
        const read = await this.read();
        const check = read.snapshot?.check;
        return check &&
          check.kind === "verify" &&
          (!operation || check.operation_id === operation) &&
          check.stage !== "running"
          ? read
          : null;
      },
      { timeout: 180000, what: "the full check to settle" },
    );
    const checkedAt = new Date().toISOString();
    const row = this.row(setup);
    this.rowsAfter = setup.snapshot.rows;
    await this.openComponents();
    const shown = await this.session.page.locator(ROW(this.item)).innerText();
    this.evidence = {
      itemId: this.item,
      state: row?.state ?? null,
      check: setup.snapshot.check,
      shown,
      evidence: {
        source:
          row?.mode === "full"
            ? FULL_CHECK_SOURCE
            : `${row?.mode ?? "no"}_check`,
        mode: row?.mode ?? null,
        checkedAt,
      },
      setupSettledAt: this.setupSettledAt,
      row: row && compactRows([row])[0],
      rows: compactRows(this.rowsAfter),
    };
    this.note("full-check", this.evidence);
    if (setup.snapshot.check.stage !== "done")
      return fail(
        `the full check ended ${setup.snapshot.check.stage}`,
        this.evidence,
      );
    return itemEvidenceVerdict(this.evidence);
  }

  /** A second setup of the item, now set up, through the window's own command. */
  async secondSetup() {
    const tree = fingerprint([this.layout.browsers]);
    const reviewsBefore = (await this.reviewsRendered())?.length ?? 0;
    const wire = this.proxy.downstream;
    const previous =
      runOf((await this.read()).snapshot, this.item)?.operation_id ?? null;
    const started = await this.session.call("desktop_setup_start", {
      item: this.item,
      resume: false,
    });
    if (!started.ok)
      return fail(
        `desktop_setup_start refused: ${started.error?.code ?? "unknown"}`,
      );
    let reviewed = false;
    const settled = await this.wait(
      async () => {
        const read = await this.read();
        const run = runOf(read.snapshot, this.item);
        if (!run || run.operation_id === previous) return null;
        if (run.stage === "review" && run.review && !reviewed) {
          reviewed = true;
          await this.session.call("desktop_setup_answer", {
            operationId: run.operation_id,
            planDigest: run.review.plan_digest,
            decision: "reject",
          });
          return null;
        }
        return run.stage === "settled" ? read : null;
      },
      { timeout: 300000, what: "the second setup to settle" },
    );
    const run = runOf(settled.snapshot, this.item);
    const reviews = (await this.reviewsRendered()) ?? [];
    this.second = {
      outcome: run.outcome,
      reviewsShown: Math.max(reviews.length - reviewsBefore, reviewed ? 1 : 0),
      wireBytes: this.proxy.downstream - wire,
      changedPaths: fingerprintChanges(
        tree,
        fingerprint([this.layout.browsers]),
      ),
      items: run.items,
    };
    this.note("second-setup", this.second);
    return secondSetupVerdict(this.second);
  }
}

/**
 * The setup acceptance in order. `check` records one PASS, FAIL or SKIP per
 * step. A step the next ones cannot run without stops them; Resume, the
 * approval count and the interruption reading each judge something of their
 * own and stop nothing.
 */
export async function runSetupAcceptance({ driver, check, results }) {
  const initial = [
    [
      "setup-review",
      "Settings' provisioning button and the browser row's button show its plan",
      () => driver.showPlan(),
    ],
    [
      "setup-approval",
      "the person approves exactly the plan shown",
      () => driver.approve(),
    ],
    [
      "setup-interrupt",
      "the download is interrupted mid-transfer",
      () => driver.interrupt(),
    ],
    [
      "setup-interrupted",
      "the window shows the interruption and how to resume",
      () => driver.afterInterruption(),
    ],
  ];
  const steps = [
    ...initial,
    [
      "setup-recovery",
      "the interrupted browser resumes under this window's approval and finishes",
      () => driver.resume(),
    ],
    [
      "setup-one-approval",
      "one approval covered the browser before any byte moved",
      () =>
        planApprovalVerdict({
          approvals: driver.approvals.slice(
            driver.phaseApprovalStart ?? 0,
            driver.crashWindows
              ? (driver.phaseApprovalStart ?? 0) + 1
              : undefined,
          ),
          requiredItemIds: [driver.item],
          firstTransferAt: driver.firstTransferAt,
        }),
    ],
    [
      "setup-full-check",
      "the app's own full check reads the browser ready",
      () => driver.fullCheck(),
    ],
    [
      "setup-second-run",
      "a second setup changes nothing",
      () => driver.secondSetup(),
    ],
  ];
  const independent = new Set([
    "setup-interrupted",
    "setup-recovery",
    "setup-one-approval",
  ]);
  const outcomes = {};
  let blocked = null;
  for (const [id, title, run] of steps) {
    const entry = await check(id, title, async () => {
      if (driver.abortReason)
        return {
          verdict: "SKIP",
          detail: `the run was stopped: ${driver.abortReason}`,
        };
      if (blocked) return { verdict: "SKIP", detail: `depends on ${blocked}` };
      return run();
    });
    outcomes[id] = entry.verdict;
    // An interruption that left children running still happened.
    const happened =
      id === "setup-interrupt" &&
      driver.cut &&
      (!driver.restartAfterCrash || driver.crashWindows);
    if (entry.verdict !== PASS && !independent.has(id) && !happened)
      blocked ??= id;
  }
  if (driver.evidence) recordItemEvidence(results, [driver.evidence]);
  results.evidence("setup-timeline.json", driver.timeline);
  return outcomes;
}
