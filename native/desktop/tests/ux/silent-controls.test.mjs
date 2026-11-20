// Silent-controls audit of the packaged native window: every enabled control
// a person can press on every window view must do something they can see. The
// spec visits each rail page and each tab of its shown tablists, enumerates the
// shown, enabled buttons, menu items, tabs and links, presses each one and
// fails when, within the bound, the press changed nothing in the page (beyond
// what the page was already changing while idle), opened no dialog or notice,
// asked no file chooser and wrote no host log line.
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
import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { after, before, test } from "node:test";
import { queuePickerSelection } from "../automation/session.mjs";
import {
  exec,
  label,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { dismissSetup, pickerAnswerPending } from "./ux-nav.mjs";

const BOUND_MS = Number(process.env.CADRUMO_SILENT_BOUND_MS ?? 4000);
const IDLE_MS = 2000;
const ONLY = (process.env.CADRUMO_SILENT_ONLY ?? "")
  .split(",")
  .map((part) => part.trim())
  .filter(Boolean);
const REGISTER = JSON.parse(
  readFileSync(new URL("./silent-controls-register.json", import.meta.url)),
);

let runDir;
const rows = [];

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-silent-")), "run");
  await start(runDir);
  // The first-run setup dialog arrives a while after sign-in; one that came
  // during the first press would be counted as that press's effect.
  await waitFor(() => dismissSetup(), {
    timeout: 20_000,
    what: "the first-run setup dialog",
    soft: true,
  });
});
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
        region.getAttribute("data-slot") ||
        region.className?.toString().split(" ")[0] ||
        region.tagName.toLowerCase(),
    ).slice(0, 40);
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

/** Mark the control whose key is `key` and start watching the page. */
function pageArm(key) {
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
        region.getAttribute("data-slot") ||
        region.className?.toString().split(" ")[0] ||
        region.tagName.toLowerCase(),
    ).slice(0, 40);
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
  if (!target) return false;
  target.setAttribute("data-silent-target", "1");
  window.__silent?.observer.disconnect();
  const state = {
    phase: "idle",
    noisy: new Set(),
    effects: [],
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
  const describe = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    if (!el) return "text";
    const role = el.getAttribute?.("role");
    return `${el.tagName.toLowerCase()}${role ? `[role=${role}]` : ""}${el.getAttribute?.("data-slot") ? `[${el.getAttribute("data-slot")}]` : ""}`;
  };
  // Where a change happens, by the element and its labelled ancestors, so a
  // place that changed while the page was idle (a clock, a status tick) is
  // known as noise for every later press, even after it was redrawn.
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
  window.__silentNoise ??= new Set();
  const noise = window.__silentNoise;
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (ignored(record.target)) continue;
      if (
        record.type === "attributes" &&
        (pointerOnly.has(record.attributeName) ||
          record.attributeName?.startsWith("data-silent"))
      ) {
        // data-state on the pressed control is ambiguous (a toggle's state is
        // an effect); data-state anywhere else is counted.
        if (!(
          record.attributeName === "data-state" &&
          record.target !== target &&
          !target.contains(record.target)
        ))
          continue;
      }
      if (state.phase === "idle") {
        state.noisy.add(record.target);
        noise.add(place(record.target));
        continue;
      }
      if (state.noisy.has(record.target) || noise.has(place(record.target)))
        continue;
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
  window.__silent = { observer, state };
  return true;
}

function pagePress() {
  window.__silent.state.phase = "press";
}

/** What the press has done so far. */
function pageEffect() {
  const state = window.__silent?.state;
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
  return {
    effects: state.effects.slice(0, 5),
    count: state.effects.length,
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

function pageSignedOutNow() {
  const field = document.querySelector("#profile-password");
  return !!field && field.getClientRects().length > 0;
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

/** Total bytes of the host's logs under the run's storage. */
function logBytes() {
  const storage = resolve(runDir, "storage");
  let total = 0;
  const walk = (dir, depth) => {
    if (depth > 6 || !existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path, depth + 1);
      else if (/\.(log|jsonl)$/i.test(entry.name)) {
        try {
          total += statSync(path).size;
        } catch {
          // A log rotated away between the listing and the stat is not counted.
        }
      }
    }
  };
  walk(storage, 0);
  return total;
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

function queueCancel() {
  if (pickerAnswerPending(runDir)) return;
  queuePickerSelection(runDir, "open", null);
}

async function press(view, control) {
  const kind = classify(control);
  const row = {
    view: view.name,
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
  await goTo(view);
  if (control.via) {
    // An item of a menu or list another control opens: open it first.
    if (await exec(pageArm, control.via)) {
      try {
        await (await win.browser.$("[data-silent-target]")).click();
      } catch {
        await exec(() =>
          document.querySelector("[data-silent-target]")?.click(),
        );
      }
      await exec(pageDisarm);
      await sleep(800);
    }
  }
  if (!(await exec(pageArm, control.key))) {
    row.effect = "not found again after returning to the view";
    return row;
  }
  await sleep(IDLE_MS);
  queueCancel();
  const logsBefore = logBytes();
  await exec(pagePress);
  try {
    await (await win.browser.$("[data-silent-target]")).click();
  } catch (error) {
    // Covered or detached: press it as a program would.
    await exec(() => document.querySelector("[data-silent-target]")?.click());
    row.note = `wdio click failed (${error.message.split("\n")[0].slice(0, 80)}); pressed by script`;
  }
  const end = Date.now() + BOUND_MS;
  let seen = null;
  for (;;) {
    await sleep(250);
    seen = await exec(pageEffect);
    const asked = !pickerAnswerPending(runDir);
    const logged = logBytes() > logsBefore;
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
      // person all the same: a failure must reach a visible notice too.
      row.effect = logged
        ? "host log written, nothing shown"
        : "nothing: no page change, dialog, notice, chooser or log";
      row.silent = true;
      break;
    }
  }
  await exec(pageDisarm);
  // A menu or list the press opened holds controls of its own.
  if (!control.via && !row.silent)
    row.opened = await exec(pageControls, '[role="menu"], [role="listbox"]');
  await settle(view);
  // A press that ended the session would make every later press look
  // silent: stop and name it, so the register can say what it is.
  if (await exec(pageSignedOutNow)) {
    row.effect = `the session ended: ${row.effect}`;
    row.silent = true;
    rows.push(row);
    throw new Error(
      `the session ended after pressing ${row.view} :: ${row.control}; register it (kind session) or make it ask first`,
    );
  }
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
    "| view | control | role | effect observed |",
    "|---|---|---|---|",
    ...rows.map(
      (r) =>
        `| ${cell(r.view)} | ${cell(r.control)} | ${cell(r.role)} | ${r.silent ? "**SILENT** " : ""}${cell(r.effect)}${r.note ? ` (${cell(r.note)})` : ""} |`,
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
