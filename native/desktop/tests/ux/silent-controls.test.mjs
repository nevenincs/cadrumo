// Silent-controls audit of the packaged native window: every enabled control
// a person can press on every window view must do something they can see. The
// spec visits each rail page and each tab of its shown tablists, enumerates the
// shown, enabled buttons, menu items, tabs and links, presses each one and
// fails when, within the bound, the press changed nothing in the page (beyond
// what the view was already changing while idle, though never the control's
// own name or state), opened no dialog and asked no file chooser. A host log
// line alone is no effect a person sees; one that correlates with the press
// is named in the row. Controls under a modal layer or covered at their
// centre are listed and not pressed: a person could not press them there.
//
// A press is a pointer down and up at the control's centre through the
// WebDriver Actions API; each row says which method reached the control.
//
// Controls the register (silent-controls-register.json) marks destructive or
// remote, and every Button with data-variant=destructive, must instead open a
// confirmation, which the spec cancels. Controls marked external are listed
// and not pressed. Every file chooser the window asks is answered "cancel"
// through the automation host's queue, so no OS dialog opens.
//
// Environment: as window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_UX_RUN), plus
//   CADRUMO_SILENT_REPORT  (optional) path of the markdown table written at
//                          the end (a .jsonl with one line per control is
//                          written beside it)
//   CADRUMO_SILENT_ONLY    (optional) comma-separated rail ids to audit
//   CADRUMO_SILENT_BOUND_MS (optional) how long a press has to show an effect
//   CADRUMO_SILENT_RENEW_MS (optional) how long a sign-in is used before the
//                          audit signs out and in again (default 10 min)
//
// The automation host's WebDriver presses and keys are script events, which
// the window does not count as the person's input: the runtime ends the
// session at its idle window (15 minutes by default) however busy the audit
// is. The audit therefore signs out and in again through the account menu and
// the sign-in form before that, so a session that still ends was ended by
// something else, and the press after which it ended is named.
import assert from "node:assert/strict";
import {
  closeSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  openSync,
  readFileSync,
  readSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { after, before, test } from "node:test";
import { queuePickerSelection } from "../automation/session.mjs";
import {
  pageChooseSignOut,
  pageOpenAccountMenu,
} from "../automation/session-keys.mjs";
import {
  exec,
  label,
  profileCredential,
  signIn,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { dismissSetup, pickerAnswerPending } from "./ux-nav.mjs";

const BOUND_MS = Number(process.env.CADRUMO_SILENT_BOUND_MS ?? 4000);
const IDLE_MS = 2000;
const RENEW_MS = Number(process.env.CADRUMO_SILENT_RENEW_MS ?? 10 * 60_000);
/** How long a signed-out reading may last before it is believed: the account
 * menu can pass through a transient phase while its status is reread. */
const SESSION_GRACE_MS = 3000;
/** The most of one log file read after one press. */
const LOG_READ_LIMIT = 4 << 20;
/** The W3C key of a web element reference. */
const ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf";
const ONLY = (process.env.CADRUMO_SILENT_ONLY ?? "")
  .split(",")
  .map((part) => part.trim())
  .filter(Boolean);
const REGISTER = JSON.parse(
  readFileSync(new URL("./silent-controls-register.json", import.meta.url)),
);

let runDir;
const rows = [];
/** When the session the audit works in was signed in to. */
let signedInAt = 0;
/** The last control pressed, for naming what preceded a session's end. */
let lastPressed = null;
/** Signatures of the log lines the host wrote while the window was idle. */
const background = new Set();

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-silent-")), "run");
  await start(runDir);
  signedInAt = Date.now();
  await settleSetup();
});

// The first-run setup dialog arrives a while after sign-in; one that came
// during a press would be counted as that press's effect.
async function settleSetup() {
  await waitFor(() => dismissSetup(), {
    timeout: 20_000,
    what: "the first-run setup dialog",
    soft: true,
  });
}
after(async () => {
  writeReport();
  await teardown();
});

// ---------------------------------------------------------------------------
// Page side (serialised into the window: arguments and document only)
// ---------------------------------------------------------------------------

/** The shown, enabled controls outside the rail, one per distinct name. */
function pageControls(scopeSel) {
  const norm = (t) => (t ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => {
    if (!el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.pointerEvents !== "none";
  };
  const disabled = (el) =>
    el.disabled === true ||
    el.getAttribute("aria-disabled") === "true" ||
    !!el.closest("[inert], fieldset[disabled]");
  const nameOf = (el) =>
    norm(
      el.getAttribute("aria-label") ||
        (el.getAttribute("aria-labelledby") || "")
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ") ||
        el.textContent ||
        el.getAttribute("title") ||
        el.querySelector("[title]")?.getAttribute("title") ||
        "",
    ).slice(0, 120);
  const roleOf = (el) =>
    el.getAttribute("role") ||
    (el.tagName === "A" ? "link" : el.tagName.toLowerCase());
  const scopeOf = (el) => {
    const region = el.closest(
      '[role="dialog"], [role="alertdialog"], [role="menu"], [data-slot="pane-header"], header, nav, aside, main, section',
    );
    if (!region) return "page";
    return norm(
      region.getAttribute("aria-label") ||
        (region.getAttribute("aria-labelledby") || "")
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ") ||
        region.getAttribute("data-slot") ||
        region.className?.toString().split(" ")[0] ||
        region.tagName.toLowerCase(),
    ).slice(0, 40);
  };
  // The dock pane a control lies in, by its tab's title: the place a person
  // sees it, whichever rail or tab the audit came through.
  const paneOf = (el) => {
    const pane = el.closest("[data-dock-pane]");
    if (!pane)
      return el.closest('[role="dialog"], [role="alertdialog"]')
        ? "dialog"
        : "shell";
    const id = pane.getAttribute("data-dock-pane");
    return (
      norm(document.getElementById(`tab-${id}`)?.textContent).slice(0, 60) || id
    );
  };
  const seen = new Set();
  const out = [];
  const selector =
    'button, a[href], [role="button"], [role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"], [role="tab"], [role="link"], [role="option"], summary';
  const nodes = scopeSel
    ? [...document.querySelectorAll(scopeSel)]
        .filter((root) => root.getClientRects().length > 0)
        .flatMap((root) => [...root.querySelectorAll(selector)])
    : document.querySelectorAll(selector);
  for (const el of nodes) {
    if (el.closest("[data-rail], .rail, [data-silent-ignore]")) continue;
    if (!shown(el) || disabled(el)) continue;
    // A grid repeats the same control per row: one is enough.
    const name = nameOf(el);
    const role = roleOf(el);
    const key = `${role}|${scopeOf(el)}|${name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      key,
      role,
      name,
      scope: scopeOf(el),
      pane: paneOf(el),
      variant: el.getAttribute("data-variant"),
      selected:
        el.getAttribute("aria-selected") === "true" ||
        el.getAttribute("aria-pressed") === "true" ||
        el.getAttribute("aria-current") === "page",
      href: el.tagName === "A" ? el.getAttribute("href") : null,
      external:
        el.tagName === "A" &&
        /^(https?:|mailto:)/i.test(el.getAttribute("href") ?? ""),
    });
  }
  return out;
}

/**
 * Mark the control whose key is `key` and start watching the page. Returns
 * whether it was found and, when a person could not press it where it is (it
 * lies under a modal layer or something else is drawn over its centre), why.
 * Changes learned as idle noise are kept per `noiseScope` (the view), never
 * for the whole run.
 */
function pageArm(key, noiseScope) {
  const norm = (t) => (t ?? "").replace(/\s+/g, " ").trim();
  for (const old of document.querySelectorAll("[data-silent-target]"))
    old.removeAttribute("data-silent-target");
  const nameOf = (el) =>
    norm(
      el.getAttribute("aria-label") ||
        (el.getAttribute("aria-labelledby") || "")
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ") ||
        el.textContent ||
        el.getAttribute("title") ||
        el.querySelector("[title]")?.getAttribute("title") ||
        "",
    ).slice(0, 120);
  const roleOf = (el) =>
    el.getAttribute("role") ||
    (el.tagName === "A" ? "link" : el.tagName.toLowerCase());
  const scopeOf = (el) => {
    const region = el.closest(
      '[role="dialog"], [role="alertdialog"], [role="menu"], [data-slot="pane-header"], header, nav, aside, main, section',
    );
    if (!region) return "page";
    return norm(
      region.getAttribute("aria-label") ||
        (region.getAttribute("aria-labelledby") || "")
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ") ||
        region.getAttribute("data-slot") ||
        region.className?.toString().split(" ")[0] ||
        region.tagName.toLowerCase(),
    ).slice(0, 40);
  };
  const describe = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    if (!el) return "text";
    const role = el.getAttribute?.("role");
    const slot = el.getAttribute?.("data-slot");
    const name = el.getAttribute?.("aria-label");
    return `${el.tagName.toLowerCase()}${role ? `[role=${role}]` : ""}${slot ? `[${slot}]` : ""}${name ? `(${norm(name).slice(0, 40)})` : ""}`;
  };
  const target = [
    ...document.querySelectorAll(
      'button, a[href], [role="button"], [role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"], [role="tab"], [role="link"], [role="option"], summary',
    ),
  ].find(
    (el) =>
      el.getClientRects().length &&
      `${roleOf(el)}|${scopeOf(el)}|${nameOf(el)}` === key,
  );
  if (!target) return { found: false, covered: null };
  window.__silent?.observer.disconnect();
  window.__silent = null;
  // A person presses what is drawn on top where they point; a control a
  // modal layer hides from assistive technology, or one something else
  // covers at its centre, is not theirs to press there.
  target.scrollIntoView({ block: "nearest", inline: "nearest" });
  const hidden = target.closest('[aria-hidden="true"], [inert]');
  if (hidden)
    return {
      found: true,
      covered: `inside ${hidden.hasAttribute("inert") ? "an inert" : "an aria-hidden"} ${describe(hidden)}`,
    };
  const box = target.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2,
    box.top + box.height / 2,
  );
  if (!hit || !(hit === target || target.contains(hit)))
    return {
      found: true,
      covered: hit
        ? `${describe(hit)} is drawn over its centre`
        : "its centre lies outside the window",
    };
  target.setAttribute("data-silent-target", "1");
  const state = {
    phase: "idle",
    noisy: new Set(),
    effects: [],
    own: null,
    dialogs: document.querySelectorAll('[role="dialog"], [role="alertdialog"]')
      .length,
  };
  // Focus, hover and highlight are the press itself, not its effect.
  const pointerOnly = new Set([
    "class",
    "style",
    "tabindex",
    "data-highlighted",
    "data-focus",
    "data-focus-visible",
    "data-hovered",
    "data-pressed",
    "data-state",
    "data-silent-target",
    "aria-describedby",
  ]);
  const ignored = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    return !!el?.closest?.(
      '[role="tooltip"], [data-slot="tooltip-content"], [data-radix-popper-content-wrapper]:has([role="tooltip"])',
    );
  };
  const ownNode = (node) => node === target || target.contains(node);
  // Where a change happens, by the element and its labelled ancestors, so a
  // place that changed while the view was idle (a clock, a status tick) is
  // known as noise for later presses in the same view, even after it was
  // redrawn.
  const place = (node) => {
    const parts = [];
    let el = node.nodeType === 1 ? node : node.parentElement;
    for (let depth = 0; el && el !== document.body && depth < 6; depth += 1) {
      const name =
        el.getAttribute("aria-label") ||
        el.getAttribute("data-slot") ||
        el.getAttribute("role") ||
        (typeof el.className === "string" ? el.className.split(" ")[0] : "");
      parts.push(`${el.tagName.toLowerCase()}${name ? `(${name})` : ""}`);
      el = el.parentElement;
    }
    return parts.join("<");
  };
  window.__silentNoise ??= {};
  window.__silentNoise[noiseScope] ??= [];
  const noise = window.__silentNoise[noiseScope];
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (ignored(record.target)) continue;
      const own = ownNode(record.target);
      if (
        record.type === "attributes" &&
        (pointerOnly.has(record.attributeName) ||
          record.attributeName?.startsWith("data-silent"))
      ) {
        // data-state on the pressed control is ambiguous (a toggle's state is
        // an effect, a tooltip's opening is not); data-state anywhere else is
        // counted. The control's own state is compared before and after.
        if (!(record.attributeName === "data-state" && !own)) continue;
      }
      if (state.phase === "idle") {
        state.noisy.add(record.target);
        // The control's own changes are never learned as the view's noise.
        if (!own && !noise.includes(place(record.target)))
          noise.push(place(record.target));
        continue;
      }
      if (state.noisy.has(record.target)) continue;
      if (!own && noise.includes(place(record.target))) continue;
      const added = [...(record.addedNodes ?? [])].filter((n) => !ignored(n));
      if (
        record.type === "childList" &&
        !added.length &&
        !record.removedNodes.length
      )
        continue;
      state.effects.push(
        record.type === "attributes"
          ? `${describe(record.target)} @${record.attributeName}`
          : record.type === "characterData"
            ? `text of ${describe(record.target)}`
            : added.length
              ? `added ${describe(added[0])}`
              : `removed from ${describe(record.target)}`,
      );
    }
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  const ownState = () => {
    const out = { name: nameOf(target) };
    for (const attr of [
      "aria-pressed",
      "aria-expanded",
      "aria-checked",
      "aria-selected",
      "aria-current",
    ])
      out[attr] = target.getAttribute(attr);
    return out;
  };
  window.__silent = { observer, state, target, ownState };
  return { found: true, covered: null };
}

function pagePress() {
  const silent = window.__silent;
  silent.state.own = silent.ownState();
  silent.state.phase = "press";
}

/** What the press has done so far. */
function pageEffect() {
  const silent = window.__silent;
  const state = silent?.state;
  if (!state) return null;
  const shown = (el) => el.getClientRects().length > 0;
  const dialogs = [
    ...document.querySelectorAll('[role="dialog"], [role="alertdialog"]'),
  ].filter(shown);
  const notices = [
    ...document.querySelectorAll(
      '[role="alert"], [role="status"], [aria-live="assertive"], [aria-live="polite"], [data-slot="alert"], [data-slot="toast"]',
    ),
  ]
    .filter(shown)
    .map((el) => (el.textContent ?? "").replace(/\s+/g, " ").trim())
    .filter(Boolean);
  const trigger = [...document.querySelectorAll("button.profile-trigger")].find(
    shown,
  );
  const password = document.querySelector("#profile-password");
  // The control's own name or state changing is the press's effect even
  // where that place changed before (a toggle relabelling itself).
  const own = [];
  if (state.own && silent.target.isConnected) {
    const now = silent.ownState();
    for (const [attr, was] of Object.entries(state.own))
      if (now[attr] !== was)
        own.push(
          `the control's own ${attr} "${was ?? ""}" -> "${now[attr] ?? ""}"`,
        );
  }
  const effects = [...own, ...state.effects];
  return {
    signedIn:
      !!trigger?.querySelector(".profile-status.signed-in") &&
      !(password && shown(password)),
    effects: effects.slice(0, 5),
    count: effects.length,
    dialogs: dialogs.length,
    newDialog: dialogs.length > state.dialogs,
    dialogText: dialogs
      .map((d) =>
        (d.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 80),
      )
      .join(" | "),
    notices: notices.slice(0, 3),
  };
}

function pageDisarm() {
  window.__silent?.observer.disconnect();
  window.__silent = null;
  for (const old of document.querySelectorAll("[data-silent-target]"))
    old.removeAttribute("data-silent-target");
}

/** The shown rail buttons. */
function pageRails() {
  return [...document.querySelectorAll("[data-rail]")]
    .filter(
      (el) =>
        el.getClientRects().length &&
        el.getAttribute("aria-disabled") !== "true" &&
        !el.disabled,
    )
    .map((el) => ({
      id: el.getAttribute("data-rail"),
      name: (el.getAttribute("aria-label") || el.textContent || "").trim(),
      popover: el.hasAttribute("aria-expanded"),
    }));
}

/** The labels of the tabs of the shown tablists outside dialogs. */
function pageTabNames() {
  const out = [];
  for (const list of document.querySelectorAll('[role="tablist"]')) {
    if (!list.getClientRects().length) continue;
    if (list.closest('[role="dialog"], [data-rail]')) continue;
    for (const tab of list.querySelectorAll('[role="tab"]')) {
      if (!tab.getClientRects().length) continue;
      if (tab.getAttribute("aria-disabled") === "true" || tab.disabled)
        continue;
      out.push({
        list: list.getAttribute("aria-label") ?? "",
        tab: (tab.textContent ?? "").replace(/\s+/g, " ").trim(),
      });
    }
  }
  return out;
}

function pageChooseTab(list, name) {
  for (const l of document.querySelectorAll('[role="tablist"]')) {
    if (!l.getClientRects().length) continue;
    if ((l.getAttribute("aria-label") ?? "") !== list) continue;
    for (const tab of l.querySelectorAll('[role="tab"]')) {
      if ((tab.textContent ?? "").replace(/\s+/g, " ").trim() !== name)
        continue;
      // Radix tabs choose on mouse down.
      tab.dispatchEvent(
        new PointerEvent("pointerdown", { bubbles: true, button: 0 }),
      );
      tab.dispatchEvent(
        new MouseEvent("mousedown", { bubbles: true, button: 0 }),
      );
      tab.click();
      return true;
    }
  }
  return false;
}

/** The session as the window shows it: the account menu's signed-in dot,
 * which every other phase (signed out, locked, unknown) replaces, and the
 * sign-in form, which only a session that ended shows. */
function pageSession() {
  const norm = (t) => (t ?? "").replace(/\s+/g, " ").trim();
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const trigger = [...document.querySelectorAll("button.profile-trigger")].find(
    shown,
  );
  const form = shown(document.querySelector("#profile-password"));
  return {
    signedIn: !!trigger?.querySelector(".profile-status.signed-in") && !form,
    form,
    account: norm(trigger?.textContent).slice(0, 120),
  };
}

function pageOpenLayers() {
  return [
    ...document.querySelectorAll(
      '[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [data-radix-popper-content-wrapper]',
    ),
  ].filter((el) => el.getClientRects().length > 0).length;
}

// ---------------------------------------------------------------------------
// Node side
// ---------------------------------------------------------------------------

/** The sizes of the host's log files under the run's storage, by path. */
function logSizes() {
  const storage = resolve(runDir, "storage");
  const sizes = new Map();
  const walk = (dir, depth) => {
    if (depth > 6 || !existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path, depth + 1);
      else if (/\.(log|jsonl)$/i.test(entry.name)) {
        try {
          sizes.set(path, statSync(path).size);
        } catch {
          // A log rotated away between the listing and the stat is not counted.
        }
      }
    }
  };
  walk(storage, 0);
  return sizes;
}

/** The lines the host's logs gained since `from` (a logSizes() reading). A
 * file that shrank was rotated and is read from its start. */
function logLinesSince(from) {
  const lines = [];
  for (const [path, size] of logSizes()) {
    const start = (from.get(path) ?? 0) > size ? 0 : (from.get(path) ?? 0);
    if (size <= start) continue;
    let fd;
    try {
      fd = openSync(path, "r");
      const buffer = Buffer.alloc(Math.min(size - start, LOG_READ_LIMIT));
      const read = readSync(fd, buffer, 0, buffer.length, start);
      lines.push(
        ...buffer
          .subarray(0, read)
          .toString("utf8")
          .split(/\r?\n/)
          .filter((line) => line.trim()),
      );
    } catch {
      // A log rotated away while it was read adds no lines.
    } finally {
      if (fd !== undefined) closeSync(fd);
    }
  }
  return lines;
}

/** What a log line says, without the times, counts and identifiers that
 * differ between two writes of the same periodic record. */
function logSignature(line) {
  return line
    .replace(/\d{4}-\d\d-\d\d[T ][\d:.,]+(?:Z|[+-]\d\d:?\d\d)?/g, "")
    .replace(
      /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi,
      "#",
    )
    .replace(/\b[0-9a-f]{12,}\b/gi, "#")
    .replace(/\d+(?:\.\d+)?/g, "#")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200);
}

/**
 * The lines written after a press that correlate with it: written after the
 * press began and not of a kind the host also wrote while the window was left
 * idle before a press of this run (periodic polling, ticks, background
 * work), which are `background` signatures.
 */
function pressLogLines(lines, background) {
  return lines.filter((line) => !background.has(logSignature(line)));
}

/**
 * Press the marked control as a person's press reaches it: through the
 * WebDriver Actions API, a pointer moved to the control's centre, then button
 * down and up there, which dispatches pointerdown, mousedown, pointerup,
 * mouseup and click on what is drawn at that point (a bare element click
 * dispatches only click, which Radix menu triggers ignore). Where the actions
 * are refused, a control that opens a popup is focused and given Enter, as a
 * keyboard user would; only then is it clicked by script. Returns the method
 * used; whichever it was, the press must still show its effect.
 */
async function pressLikeAPerson() {
  let pointerFailure;
  try {
    const element = await win.browser.$("[data-silent-target]");
    await win.browser.performActions([
      {
        type: "pointer",
        id: "silent-mouse",
        parameters: { pointerType: "mouse" },
        actions: [
          {
            type: "pointerMove",
            duration: 0,
            origin: { [ELEMENT_KEY]: element.elementId },
            x: 0,
            y: 0,
          },
          { type: "pointerDown", button: 0 },
          { type: "pointerUp", button: 0 },
        ],
      },
    ]);
    try {
      await win.browser.releaseActions();
    } catch {
      // Nothing is held after the release above.
    }
    return "pointer";
  } catch (error) {
    pointerFailure = error.message.split("\n")[0].slice(0, 80);
  }
  const popup = await exec(() => {
    const target = document.querySelector("[data-silent-target]");
    if (!target) return false;
    target.focus();
    return (
      document.activeElement === target &&
      (target.hasAttribute("aria-haspopup") ||
        target.hasAttribute("aria-expanded"))
    );
  });
  if (popup) {
    await win.browser.keys("Enter");
    return `keyboard Enter (pointer actions failed: ${pointerFailure})`;
  }
  await exec(() => document.querySelector("[data-silent-target]")?.click());
  return `script click (pointer actions failed: ${pointerFailure})`;
}

/** The register entry a control matches, or a destructive variant. */
function classify(control) {
  for (const entry of REGISTER.entries) {
    // A label with placeholders ("Update {area}") matches any filling.
    const words = entry.key ? label(entry.key) : null;
    const literal = (part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const shape = words
      ? words
          .split(/\{[^}]+\}/)
          .map(literal)
          .join(".+")
      : null;
    // A palette option or menu item carries its shortcut or group after the
    // label ("Cerrar sesiónCtrl+Q").
    const trailing = ["option", "menuitem"].includes(control.role)
      ? "(?:$|[A-Z0-9])"
      : "$";
    if (shape && new RegExp(`^${shape}${trailing}`).test(control.name))
      return entry;
    if (entry.pattern && new RegExp(entry.pattern).test(control.name))
      return entry;
  }
  if (control.external)
    return {
      kind: "external",
      reason: "an external link opens the system browser",
    };
  if (control.variant === "destructive")
    return { kind: "destructive", reason: "data-variant=destructive" };
  return null;
}

/** Close every layer a press opened, then come back to `view`. */
async function settle(view) {
  for (let i = 0; i < 4 && (await exec(pageOpenLayers)) > 0; i += 1) {
    await win.browser.keys("Escape");
    await sleep(300);
  }
  await goTo(view);
}

async function goTo(view) {
  await dismissSetup();
  const on = await exec(
    (id, attr) =>
      document.querySelector(`[data-rail="${id}"]`)?.getAttribute(attr) ===
      "true",
    view.rail.id,
    view.rail.popover ? "aria-expanded" : "aria-pressed",
  );
  if (!on) {
    await exec(
      (id) => document.querySelector(`[data-rail="${id}"]`)?.click(),
      view.rail.id,
    );
    await sleep(1200);
  }
  if (view.tab) {
    await exec(pageChooseTab, view.tab.list, view.tab.tab);
    await sleep(700);
  }
}

/** The session as the window shows it, believing a signed-out reading only
 * once it has lasted SESSION_GRACE_MS. */
async function readSession() {
  let now = await exec(pageSession);
  const until = Date.now() + SESSION_GRACE_MS;
  while (!now.signedIn && Date.now() < until) {
    await sleep(250);
    now = await exec(pageSession);
  }
  return now;
}

function sinceSignIn() {
  return `${Math.round((Date.now() - signedInAt) / 1000)} s after the last sign-in`;
}

/** Record the row the session ended at and stop the audit, naming `cause`. */
function sessionEnded(row, cause, session) {
  row.effect = `the session ended ${cause} (${sinceSignIn()}; account menu: ${session.account || "absent"}${session.form ? "; sign-in form shown" : ""})${row.effect ? `: ${row.effect}` : ""}`;
  row.silent = true;
  rows.push(row);
  throw new Error(
    `the session ended ${cause}, ${sinceSignIn()}; register the control (kind session) or make it ask first`,
  );
}

/**
 * Sign out and in again through the account menu and the sign-in form once
 * the sign-in has been used for RENEW_MS: the runtime counts no script input
 * as the person's, so an older session would end at its idle window.
 */
async function renewSession() {
  if (Date.now() - signedInAt < RENEW_MS) return false;
  for (let i = 0; i < 4 && (await exec(pageOpenLayers)) > 0; i += 1) {
    await win.browser.keys("Escape");
    await sleep(300);
  }
  assert.ok(
    (await readSession()).signedIn,
    `the session had ended before it was renewed (${sinceSignIn()}; last press: ${lastPressed ?? "none"})`,
  );
  assert.ok(await exec(pageOpenAccountMenu), "no account menu to sign out");
  await sleep(500);
  assert.ok(
    await exec(pageChooseSignOut, label("desktop.account.sign_out")),
    "the account menu offers no sign-out",
  );
  await waitFor(async () => (await exec(pageSession)).form, {
    timeout: 30_000,
    what: "the sign-in form after signing out to renew the session",
  });
  await signIn(profileCredential());
  signedInAt = Date.now();
  console.log("silent-controls: signed out and in again to renew the session");
  await settleSetup();
  return true;
}

function queueCancel() {
  if (pickerAnswerPending(runDir)) return;
  queuePickerSelection(runDir, "open", null);
}

async function press(view, control) {
  const kind = classify(control);
  const row = {
    view: view.name,
    pane: control.pane,
    control: control.name || `(unnamed ${control.role})`,
    role: control.role,
    scope: control.scope,
    effect: "",
    silent: false,
  };
  if (["external", "session", "window"].includes(kind?.kind)) {
    row.effect = `not pressed: ${kind.reason}`;
    return row;
  }
  const pressName = `${row.view} :: ${row.control}`;
  if (await renewSession()) view.renewed = true;
  // A session that ended between presses was not ended by this one.
  let session = await readSession();
  if (!session.signedIn)
    sessionEnded(
      row,
      `before pressing ${pressName}, after ${lastPressed ?? "no press"}`,
      session,
    );
  await goTo(view);
  if (control.via) {
    // An item of a menu or list another control opens: open it first.
    const opener = await exec(pageArm, control.via, view.name);
    if (opener.found && !opener.covered) {
      await pressLikeAPerson();
      await exec(pageDisarm);
      await sleep(800);
    }
  }
  const armed = await exec(pageArm, control.key, view.name);
  if (armed.found && armed.covered) {
    row.effect = `not pressed: covered (${armed.covered})`;
    return row;
  }
  if (!armed.found) {
    row.effect = "not found again after returning to the view";
    if (view.renewed)
      row.note =
        "the view was entered again after the session was renewed; a page reached by an earlier press may not have been restored";
    session = await readSession();
    if (!session.signedIn)
      sessionEnded(
        row,
        `before ${pressName} was found again, after ${lastPressed ?? "no press"}`,
        session,
      );
    return row;
  }
  const idleLogs = logSizes();
  await sleep(IDLE_MS);
  session = await exec(pageSession);
  if (!session.signedIn && !(session = await readSession()).signedIn)
    sessionEnded(
      row,
      `while waiting to press ${pressName}, after ${lastPressed ?? "no press"}`,
      session,
    );
  queueCancel();
  // What the host logged while the view stood idle is background, not any
  // press's doing; after opening a menu, the opener's lines may still be
  // arriving, so that wait teaches nothing. A late line of the previous
  // press can still be learned here: it then only stops being named, since
  // a log line never passes a press.
  if (!control.via)
    for (const line of logLinesSince(idleLogs))
      background.add(logSignature(line));
  const logsBefore = logSizes();
  lastPressed = pressName;
  await exec(pagePress);
  row.method = await pressLikeAPerson();
  const end = Date.now() + BOUND_MS;
  let seen = null;
  for (;;) {
    await sleep(250);
    seen = await exec(pageEffect);
    const asked = !pickerAnswerPending(runDir);
    // The account menu says at once when the press ended the session.
    if (seen && !seen.signedIn && !(await readSession()).signedIn) {
      row.effect = "the account menu left the signed-in state";
      break;
    }
    if (kind) {
      if (seen?.newDialog) {
        row.effect = `confirmation opened (${kind.kind}): ${seen.dialogText}`;
        break;
      }
      if (Date.now() > end) {
        row.effect = `${kind.kind} control opened no confirmation`;
        row.silent = true;
        break;
      }
      continue;
    }
    if (seen?.newDialog) {
      row.effect = `dialog: ${seen.dialogText}`;
      break;
    }
    if (asked) {
      row.effect = "asked a file chooser (answered cancel)";
      break;
    }
    if (seen?.count > 0) {
      row.effect = `page changed: ${seen.effects.join("; ")}`;
      break;
    }
    if (Date.now() > end) {
      // A press the host logged but the page never showed is silent to the
      // person all the same: a failure must reach a visible notice too. Only
      // lines that correlate with the press are named.
      const logged = pressLogLines(logLinesSince(logsBefore), background);
      row.effect = logged.length
        ? `host log written, nothing shown (${logged.length} line(s) new since the press and unlike the idle background, first: ${logSignature(logged[0]).slice(0, 100)})`
        : "nothing: no page change, dialog or chooser, and no log line beyond the idle background";
      row.silent = true;
      break;
    }
  }
  await exec(pageDisarm);
  // A menu or list the press opened holds controls of its own.
  if (!control.via && !row.silent)
    row.opened = await exec(pageControls, '[role="menu"], [role="listbox"]');
  // A press that ended the session would make every later press look
  // silent: stop and name it, so the register can say what it is.
  session = await readSession();
  if (!session.signedIn)
    sessionEnded(row, `after pressing ${pressName}`, session);
  await settle(view);
  session = await readSession();
  if (!session.signedIn)
    sessionEnded(
      row,
      `after pressing ${pressName} and closing what it opened`,
      session,
    );
  return row;
}

async function views() {
  const rails = (await exec(pageRails)).filter(
    (r) => !ONLY.length || ONLY.includes(r.id),
  );
  const out = [];
  for (const rail of rails) {
    const base = { name: rail.name || rail.id, rail };
    await goTo(base);
    out.push(base);
    // A rail that opens a surface (the palette) covers the page: the tabs
    // beneath it are the dock's, which the dock's own rails visit.
    if (rail.popover) continue;
    for (const tab of await exec(pageTabNames))
      out.push({ name: `${base.name} › ${tab.tab}`, rail, tab });
  }
  return out;
}

function writeReport() {
  const path =
    process.env.CADRUMO_SILENT_REPORT ?? join(runDir, "silent-controls.md");
  mkdirSync(dirname(path), { recursive: true });
  const cell = (text) => String(text ?? "").replace(/\|/g, "/");
  const lines = [
    "| view | pane | control | role | pressed by | effect observed |",
    "|---|---|---|---|---|---|",
    ...rows.map(
      (r) =>
        `| ${cell(r.view)} | ${cell(r.pane)} | ${cell(r.control)} | ${cell(r.role)} | ${cell(r.method)} | ${r.silent ? "**SILENT** " : ""}${cell(r.effect)}${r.note ? ` (${cell(r.note)})` : ""} |`,
    ),
  ];
  writeFileSync(path, `${lines.join("\n")}\n`);
  writeFileSync(
    path.replace(/\.md$/, "") + ".jsonl",
    rows.map((r) => JSON.stringify(r)).join("\n") + "\n",
  );
}

test(
  "every enabled control on every view shows an effect",
  { timeout: 4 * 3600_000 },
  async () => {
    const pressed = new Set();
    for (const view of await views()) {
      await goTo(view);
      const controls = await exec(pageControls);
      for (let i = 0; i < controls.length; i += 1) {
        const control = controls[i];
        // A control shared by several views (a header button) is pressed once.
        const once = `${view.rail.id}|${control.key}`;
        if (pressed.has(once) || pressed.has(`*|${control.key}`)) continue;
        pressed.add(once);
        if (control.scope === "header" || control.scope === "nav")
          pressed.add(`*|${control.key}`);
        // Choosing the tab already shown changes nothing, by design.
        if (control.role === "tab" && control.selected) continue;
        const row = await press(view, control);
        for (const item of row.opened ?? [])
          if (
            !controls.some((c) => c.key === item.key && c.via === control.key)
          )
            controls.push({ ...item, via: control.key });
        delete row.opened;
        rows.push(row);
      }
    }
    const silent = rows.filter((r) => r.silent);
    assert.ok(rows.length > 0, "the audit pressed no control");
    assert.deepEqual(
      silent.map((r) => `${r.view} :: ${r.control} (${r.role}): ${r.effect}`),
      [],
      `${silent.length} silent control(s)`,
    );
  },
);
