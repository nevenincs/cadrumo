// Window driver for the UX audit specs. Copied, minimal, from
// ../personas/window-persona.test.mjs (that file is a test and cannot be
// imported without running it): launch(), teardown(), signIn(), waitFor(),
// the chrome-string label lookup and the page-side helpers. It reads the host
// from CADRUMO_PERSONA_HOST and the world from CADRUMO_PERSONA_WORLD, exactly
// as that spec does, and stages nothing.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import {
  closeSync,
  cpSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  focusLiveWindow,
  hostEnvironment,
  inspectProcess,
  isHostCommand,
  proveOwnership,
  verifyListener,
  waitForWebDriver,
} from "../automation/session.mjs";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { remote } = require("webdriverio");
export const repository = fileURLToPath(new URL("../../../../", import.meta.url));
export const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

const PROFILE = process.env.CADRUMO_PERSONA_PROFILE || "persona";
const CREDENTIAL_SOURCE = resolve(
  repository,
  "src/cadrumo/entrypoints/tests/persona_materialisation.py",
);

export const win = { browser: null, child: null, closed: true, pid: null };
export let label = (key) => key;

export const exec = (fn, ...args) => win.browser.execute(fn, ...args);

export async function live() {
  try {
    await focusLiveWindow(win.browser);
  } catch {
    // Reported by the command that follows.
  }
}

export async function waitFor(read, { timeout, what, interval = 400, soft = false }) {
  const end = Date.now() + timeout;
  let last;
  for (;;) {
    await live();
    try {
      const value = await read();
      if (value) return value;
    } catch (error) {
      last = error;
    }
    if (Date.now() > end) {
      if (soft) return null;
      throw new Error(
        `Timed out after ${timeout} ms waiting for ${what}${last ? `: ${last.message}` : ""}`,
      );
    }
    await sleep(interval);
  }
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

export async function launch(world, runDir) {
  const storage = resolve(runDir, "storage");
  mkdirSync(runDir, { mode: 0o700, recursive: true });
  const source = resolve(world.storage_root);
  assert(
    existsSync(source) && statSync(source).isDirectory(),
    `the world's storage_root is not a directory: ${source}`,
  );
  assert(
    !existsSync(storage) || readdirSync(storage).length === 0,
    `the run's storage directory must be absent or empty: ${storage}`,
  );
  cpSync(source, storage, { recursive: true, errorOnExist: true });
  for (const member of ["temporary", "fixtures", "exports"])
    mkdirSync(resolve(runDir, member), { mode: 0o700, recursive: true });
  const host = JSON.parse(process.env.CADRUMO_PERSONA_HOST);
  const port = await freePort();
  const nonce = randomBytes(32).toString("hex");
  const stdout = openSync(resolve(runDir, "host.stdout.log"), "a", 0o600);
  const stderr = openSync(resolve(runDir, "host.stderr.log"), "a", 0o600);
  const child = spawn(host.executable, ["--gui"], {
    cwd: host.package,
    env: hostEnvironment(process.env, runDir, host.package, port, nonce),
    detached: true,
    stdio: ["ignore", stdout, stderr],
  });
  closeSync(stdout);
  closeSync(stderr);
  child.unref();
  Object.assign(win, {
    child,
    pid: child.pid,
    executable: host.executable,
    closed: false,
  });
  process.once("exit", () => {
    if (win.closed || !win.pid) return;
    const check = inspectProcess(win.pid);
    if (check.status === 0 && isHostCommand(check.stdout, win.executable))
      process.kill(win.pid, "SIGTERM");
  });
  await waitForWebDriver(child, port, runDir);
  verifyListener({ pid: child.pid, executable: host.executable, port });
  win.browser = await remote({
    hostname: "127.0.0.1",
    port,
    path: "/",
    logLevel: "silent",
    connectionRetryCount: 0,
    capabilities: {},
  });
  await proveOwnership(win.browser, nonce);
  return runDir;
}

/** Stop only the host this driver started, by PID, after checking its identity. */
export async function teardown() {
  if (win.closed) return;
  win.closed = true;
  try {
    await win.browser?.deleteSession();
  } catch {
    // The process check below decides.
  }
  if (!win.pid) return;
  const check = inspectProcess(win.pid);
  if (check.status === 0 && isHostCommand(check.stdout, win.executable)) {
    process.kill(win.pid, "SIGTERM");
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await sleep(250);
      if (inspectProcess(win.pid).status !== 0) break;
    }
  }
}

export function profileCredential() {
  const match = /^(?:_|PERSONA_)PROFILE_CREDENTIAL\s*=\s*"([^"\n]+)"/m.exec(
    readFileSync(CREDENTIAL_SOURCE, "utf8"),
  );
  if (!match)
    throw new Error("no _PROFILE_CREDENTIAL in persona_materialisation.py");
  return match[1];
}

function pageSignIn() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const shown = (element) => element.getClientRects().length > 0;
  const form = document.querySelector(".sign-in");
  const password = document.querySelector("#profile-password");
  const choice = document.querySelector("#profile-choice");
  return {
    form: !!form && shown(form),
    password: !!password && shown(password),
    busy: password?.getAttribute("aria-busy") === "true",
    named:
      document
        .querySelector(".sign-in .profile-named span[title]")
        ?.getAttribute("title") ?? null,
    choice: choice
      ? { value: choice.value, options: [...choice.options].map((o) => o.value) }
      : null,
    words: [
      ...document.querySelectorAll(
        '.sign-in [role="alert"], .sign-in [data-slot="alert"], .sign-in [data-slot="field-error"]',
      ),
    ]
      .map((element) => norm(element.textContent))
      .filter(Boolean),
    text: norm(form?.textContent).slice(0, 300),
    rail: (() => {
      const rail = document.querySelector('[data-rail="declarations"]');
      return !!rail && shown(rail);
    })(),
  };
}

function pageChoose(value) {
  const node = document.querySelector("#profile-choice");
  const option = [...node.options].find((item) => item.value === value);
  if (!option || option.disabled) return false;
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set.call(
    node,
    value,
  );
  node.dispatchEvent(new Event("input", { bubbles: true }));
  node.dispatchEvent(new Event("change", { bubbles: true }));
  return node.value === value;
}

export async function clickSelector(selector) {
  const element = await win.browser.$(selector);
  await element.waitForExist({ timeout: 15_000 });
  await element.click();
}

export async function signIn(password) {
  const info = await waitFor(
    async () => {
      const found = await exec(pageSignIn);
      return found.password ? found : null;
    },
    { timeout: 300_000, what: "the sign-in form" },
  );
  if (info.choice && info.choice.value !== PROFILE) {
    if (!info.choice.options.includes(PROFILE))
      throw new Error(`profile "${PROFILE}" is not offered`);
    assert(await exec(pageChoose, PROFILE), "the profile choice did not take");
  }
  const field = await win.browser.$("#profile-password");
  await field.setValue(password);
  await clickSelector(".sign-in button[type=submit]");
  const answer = await waitFor(
    async () => {
      const now = await exec(pageSignIn);
      if (now.rail && !now.password) return { ok: true };
      if (now.words.length > 0 && !now.busy) return { ok: false, words: now.words };
      return null;
    },
    { timeout: 300_000, what: "the sign-in answer", soft: true },
  );
  if (!answer) throw new Error("no sign-in answer");
  if (!answer.ok) throw new Error(`sign-in refused: ${answer.words.join(" | ")}`);
}

/** Launch, sign in and load the chrome-string catalogue (sets `label`). */
export async function start(runDir) {
  const world = JSON.parse(readFileSync(process.env.CADRUMO_PERSONA_WORLD, "utf8"));
  const credential = profileCredential();
  await launch(world, runDir);
  await signIn(credential);
  const lang = (await exec(() => document.documentElement.lang)) || "en";
  const catalogue = JSON.parse(
    readFileSync(
      resolve(buildPath("desktop_frontend_generated"), "chrome-strings.json"),
      "utf8",
    ),
  );
  const strings = catalogue[lang] ?? catalogue[lang.split("-")[0]] ?? {};
  label = (key) => strings[key] ?? catalogue.en?.[key] ?? key;
  return { world, lang };
}

// ---------------------------------------------------------------------------
// Page-side helpers (serialised into the window: arguments and document only)
// ---------------------------------------------------------------------------

/** Click (via wdio) the first shown element under scope whose text matches. */
export async function clickText(scope, item, texts, mode = "equals") {
  const text = await exec(
    (scope, item, texts, mode) => {
      for (const old of document.querySelectorAll("[data-ux-target]"))
        old.removeAttribute("data-ux-target");
      const norm = (t) => (t ?? "").replace(/\s+/g, " ").trim();
      for (const root of document.querySelectorAll(scope)) {
        if (!root.getClientRects().length) continue;
        for (const el of root.querySelectorAll(item)) {
          if (!el.getClientRects().length) continue;
          const text = norm(el.textContent);
          if (
            texts.some((w) => (mode === "startsWith" ? text.startsWith(w) : text === w))
          ) {
            el.setAttribute("data-ux-target", "1");
            return text;
          }
        }
      }
      return null;
    },
    scope,
    item,
    texts,
    mode,
  );
  if (text === null) return false;
  await clickSelector("[data-ux-target]");
  return true;
}

/** Click an element found by selector with a JS click (for hidden-from-wdio cases). */
export const jsClick = (selector) =>
  exec((s) => {
    const el = document.querySelector(s);
    if (!el) return false;
    el.click();
    return true;
  }, selector);

/**
 * Geometry of a page: viewport, document scroll, every scroll container whose
 * content overflows its box, and every shown interactive element or heading
 * that lies outside the viewport or outside an ancestor that clips it without
 * scrolling.
 */
export function pageGeometry() {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const shown = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return (
      r.width > 0 &&
      r.height > 0 &&
      cs.visibility !== "hidden" &&
      cs.display !== "none" &&
      cs.opacity !== "0"
    );
  };
  const name = (el) =>
    (el.getAttribute("aria-label") || el.textContent || el.id || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 50);
  const describe = (el) =>
    `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${
      typeof el.className === "string" && el.className
        ? "." + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join(".")
        : ""
    }`;
  const clippedBy = (el) => {
    // The nearest ancestor that clips `el` on an axis without scrolling to it.
    const r = el.getBoundingClientRect();
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      const clipX = cs.overflowX !== "visible";
      const clipY = cs.overflowY !== "visible";
      if (!clipX && !clipY) continue;
      const pr = p.getBoundingClientRect();
      const outY = clipY && (r.bottom > pr.bottom + 1 || r.top < pr.top - 1);
      const outX = clipX && (r.right > pr.right + 1 || r.left < pr.left - 1);
      if (outY || outX) {
        const scrolls =
          (outY && /auto|scroll/.test(cs.overflowY)) ||
          (outX && /auto|scroll/.test(cs.overflowX));
        return { by: describe(p), scrolls, parent: [pr.top, pr.bottom, pr.left, pr.right].map(Math.round) };
      }
    }
    return null;
  };
  const out = {
    viewport: [vw, vh],
    docScroll: [
      document.documentElement.scrollWidth,
      document.documentElement.scrollHeight,
    ],
    bodyScroll: [document.body.scrollWidth, document.body.scrollHeight],
    unreachable: [],
    overflowHidden: [],
  };
  const interesting = document.querySelectorAll(
    'button, a[href], input, select, textarea, [role="tab"], [role="button"], h1, h2, [role="grid"]',
  );
  for (const el of interesting) {
    if (!shown(el)) continue;
    const r = el.getBoundingClientRect();
    const clip = clippedBy(el);
    const outOfWindow =
      r.bottom > vh + 1 || r.right > vw + 1 || r.top < -1 || r.left < -1;
    if (outOfWindow || (clip && !clip.scrolls)) {
      out.unreachable.push({
        el: describe(el),
        name: name(el),
        rect: [r.left, r.top, r.right, r.bottom].map(Math.round),
        outOfWindow,
        clip,
      });
    }
  }
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (
      (cs.overflowY === "hidden" && el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 0) ||
      (cs.overflowX === "hidden" && el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0)
    ) {
      if (!shown(el)) continue;
      out.overflowHidden.push({
        el: describe(el),
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
      });
    }
  }
  out.unreachable = out.unreachable.slice(0, 25);
  out.overflowHidden = out.overflowHidden.slice(0, 25);
  return out;
}

export async function setSize(width, height) {
  await win.browser.setWindowSize(width, height);
  await sleep(700);
  return exec(() => [window.innerWidth, window.innerHeight]);
}

/** An error boundary or crash message on the page. */
export function pageErrors() {
  const text = document.body.innerText || "";
  const boundary = document.querySelector(
    '[data-error-boundary], [data-slot="error-boundary"], .error-boundary',
  );
  return {
    boundary: !!boundary,
    text: text.slice(0, 200),
    crash: /something went wrong|unexpected error|internal error|Uncaught|TypeError|is not a function/i.test(text),
    empty: text.trim().length === 0,
  };
}

