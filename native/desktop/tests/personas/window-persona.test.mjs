// One persona through the packaged native window: sign in, open each prepared
// declaration, calculate, verify and export it through the window's own
// controls, and read every box the form shows. Results are appended to a JSONL
// file in the acceptance column contract. No tax rule is encoded here: the
// window decides each outcome and this spec only records what it showed.
//
// Environment (all required unless noted):
//   CADRUMO_PERSONA_WORLD    path of the world JSON the Python world builder wrote
//   CADRUMO_PERSONA_RESULTS  path of the JSONL file to append
//   CADRUMO_TREE             the commit the window was built from
//   CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG   as the automation harness
//   CADRUMO_PERSONA_HOST     (optional) the JSON `dev.desktop_automation_stage`
//                            printed, when the caller staged the package once
//                            for several windows; default: stage here
//   CADRUMO_PERSONA_PROFILE  (optional) profile label, default "persona"
//   CADRUMO_PERSONA_LOADS_ONLY (optional) 1: sign in and wait for the
//                            declarations list, write only the persona line
//                            and open no declaration
//   CADRUMO_PERSONA_LANGUAGE (optional) chrome-string locale; default: the
//                            window's own document language, else "en"
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import {
  appendFileSync,
  closeSync,
  cpSync,
  existsSync,
  readdirSync,
  mkdirSync,
  openSync,
  readFileSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  focusLiveWindow,
  hostEnvironment,
  inspectionPlatform,
  inspectProcess,
  isHostCommand,
  proveOwnership,
  queuePickerSelection,
  verifyListener,
  waitForWebDriver,
} from "../automation/session.mjs";

const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { remote } = require("webdriverio");
const repository = fileURLToPath(new URL("../../../../", import.meta.url));
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

const PROFILE = process.env.CADRUMO_PERSONA_PROFILE || "persona";
const CREDENTIAL_SOURCE = resolve(
  repository,
  "src/cadrumo/entrypoints/tests/persona_materialisation.py",
);
const MARK = "data-persona-target";
const TIMEOUT = {
  signIn: 300_000,
  list: 300_000,
  calculate: 600_000,
  verify: 400_000,
  export: 400_000,
};
// The keys of `workspace.modelo.next_button.*`: the one next action the
// workspace header offers, by what it does.
const NEXT_ACTIONS = [
  "apply",
  "fill",
  "confirm",
  "calculate",
  "recalculate",
  "resolve",
  "verify",
  "export",
  "export_again",
  "record_after_file",
  "recorded",
];
const CALCULATING = ["calculate", "recalculate"];
const FILED = ["export", "export_again", "record_after_file", "recorded"];

// ---------------------------------------------------------------------------
// Page-side functions. Each is serialised into the window, so it may use only
// its arguments and the document.
// ---------------------------------------------------------------------------

/** Mark the first shown `item` under `scope` whose text matches; return its text. */
function pageMarkByText(scope, item, texts, mode, mark) {
  for (const old of document.querySelectorAll(`[${mark}]`))
    old.removeAttribute(mark);
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  for (const root of document.querySelectorAll(scope)) {
    if (!root.getClientRects().length) continue;
    for (const element of root.querySelectorAll(item)) {
      if (!element.getClientRects().length) continue;
      const text = norm(element.textContent);
      const hit = texts.some((wanted) =>
        mode === "startsWith" ? text.startsWith(wanted) : text === wanted,
      );
      if (hit) {
        element.setAttribute(mark, "1");
        return text;
      }
    }
  }
  return null;
}

/** Mark the nth shown `item` under `scope`. */
function pageMarkNth(scope, item, index, mark) {
  for (const old of document.querySelectorAll(`[${mark}]`))
    old.removeAttribute(mark);
  for (const root of document.querySelectorAll(scope)) {
    const shown = [...root.querySelectorAll(item)].filter(
      (element) => element.getClientRects().length > 0,
    );
    if (shown[index]) {
      shown[index].setAttribute(mark, "1");
      return true;
    }
  }
  return false;
}

/** The text of every shown `item` under `scope`. */
function pageTexts(scope, item) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const found = [];
  for (const root of document.querySelectorAll(scope))
    for (const element of root.querySelectorAll(item))
      if (element.getClientRects().length > 0)
        found.push(norm(element.textContent));
  return found;
}

function pageVisible(selector) {
  const node = document.querySelector(selector);
  return (
    !!node &&
    node.getClientRects().length > 0 &&
    getComputedStyle(node).visibility !== "hidden"
  );
}

/** What the workspace and any open dialog show right now. */
function pageState(actions) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const shown = (element) => element.getClientRects().length > 0;
  const header =
    [...document.querySelectorAll("header")]
      .filter((candidate) => candidate.querySelector("h1") && shown(candidate))
      .at(-1) ?? null;
  let action = null;
  let busy = false;
  if (header) {
    for (const button of header.querySelectorAll("button")) {
      if (!shown(button)) continue;
      const text = norm(button.textContent);
      const name = Object.keys(actions).find((key) => actions[key] === text);
      if (!name) continue;
      action = name;
      busy = button.getAttribute("aria-busy") === "true";
      break;
    }
  }
  const alerts = [...document.querySelectorAll('[data-slot="alert"]')]
    .filter(
      (alert) =>
        shown(alert) && ["warning", "danger"].includes(alert.dataset.tone),
    )
    .map((alert) => norm(alert.textContent).slice(0, 400));
  const refusals = [
    ...document.querySelectorAll('[data-slot="refusal-notice"]'),
  ]
    .filter(shown)
    .map((notice) => {
      const sentences = [...notice.querySelectorAll("p:not([id])")]
        .map((paragraph) => norm(paragraph.textContent))
        .filter(Boolean);
      return (sentences.join(" ") || norm(notice.textContent)).slice(0, 400);
    });
  const dialog =
    [...document.querySelectorAll('[role="dialog"]')]
      .filter((candidate) => shown(candidate) && !candidate.matches(".sign-in"))
      .at(-1) ?? null;
  const banner = header?.parentElement
    ? [...header.parentElement.children]
        .filter((child) => child.getAttribute("role") === "status")
        .map((child) => norm(child.textContent))
        .join(" ")
        .slice(0, 400)
    : "";
  return {
    workspace: header !== null,
    title: norm(header?.querySelector("h1")?.textContent),
    headerText: norm(header?.textContent).slice(0, 300),
    action,
    busy,
    alerts,
    refusals,
    unresolved: norm(
      document.querySelector("[data-calculation-unresolved]")?.textContent,
    ).slice(0, 400),
    dialogTitle: dialog
      ? norm(
          dialog.querySelector("h1,h2,h3,[data-slot='dialog-title']")
            ?.textContent,
        )
      : null,
    banner,
  };
}

function pageList(overview) {
  const grid = [...document.querySelectorAll('[role="grid"]')].find(
    (candidate) =>
      candidate.getAttribute("aria-label") === overview &&
      candidate.getClientRects().length > 0,
  );
  return {
    grid: !!grid,
    rows: grid
      ? grid.querySelectorAll('[data-slot="data-grid-row"][data-kind="data"]')
          .length
      : 0,
    failed: !!document.querySelector(".declarations-failed"),
    loading: !!document.querySelector(".declarations-loading"),
  };
}

/** The list row of a work unit: by its key, else the one row of that modelo and year. */
function pageRowKey(workUnitId, modelo, year) {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const rows = [
    ...document.querySelectorAll(
      '[role="row"][data-slot="data-grid-row"][data-kind="data"]',
    ),
  ];
  const exact = rows.find((row) => row.getAttribute("data-key") === workUnitId);
  if (exact) return { key: exact.getAttribute("data-key"), via: "key" };
  const near = rows.filter(
    (row) =>
      norm(row.querySelector('[data-column="modelo"]')?.textContent) ===
        modelo && norm(row.textContent).includes(year),
  );
  return near.length === 1
    ? { key: near[0].getAttribute("data-key"), via: "modelo-year" }
    : null;
}

/** Open a list row as a double click does; React listens for the native event. */
function pageDouble(key, mark) {
  for (const old of document.querySelectorAll(`[${mark}]`))
    old.removeAttribute(mark);
  const row = document.querySelector(
    `[role="row"][data-slot="data-grid-row"][data-key="${CSS.escape(key)}"]`,
  );
  const cell = row?.querySelector('[data-column="declaration"]') ?? row;
  if (!cell) return false;
  cell.setAttribute(mark, "1");
  cell.dispatchEvent(
    new MouseEvent("dblclick", {
      bubbles: true,
      cancelable: true,
      view: window,
      detail: 2,
    }),
  );
  return true;
}

/** Every box of the drawn part of the open form page, as displayed. */
function pageBoxes() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const root = document.querySelector("[data-modelo-form]");
  if (!root) return null;
  // The field's typed value, when the form serves it on the element
  // (`data-value-kind` and `data-value` carry the application's own scalar
  // kind and text); null when the form serves only its display words.
  const typedOf = (element) =>
    element?.hasAttribute("data-value-kind") &&
    element.hasAttribute("data-value")
      ? {
          kind: element.getAttribute("data-value-kind"),
          text: element.getAttribute("data-value"),
        }
      : null;
  const boxes = [];
  for (const row of root.querySelectorAll('div[role="row"][data-key]')) {
    const cells = [...row.children].filter(
      (child) => child.getAttribute("role") === "gridcell",
    );
    boxes.push({
      key: row.getAttribute("data-key"),
      box: norm(cells[0]?.textContent),
      value: norm((cells[2]?.querySelector("button") ?? cells[2])?.textContent),
      typed: typedOf(row),
    });
  }
  for (const cell of root.querySelectorAll("td[data-key]")) {
    const values = [...cell.querySelectorAll("button")]
      .map((button) => norm(button.textContent))
      .filter(Boolean);
    boxes.push({
      key: cell.getAttribute("data-key"),
      box: norm(cell.querySelector('[class*="font-mono"]')?.textContent),
      value: values.at(-1) ?? "",
      typed: typedOf(cell),
    });
  }
  // Repeating-record tables: a cell is a casilla only where the form names
  // its column's casilla (`data-casilla`); unnamed cells are not boxes.
  let table = 0;
  for (const scroll of root.querySelectorAll("[data-records-scroll]")) {
    table += 1;
    let line = 0;
    for (const tr of scroll.querySelectorAll("tbody tr")) {
      line += 1;
      for (const [index, cell] of [...tr.children].entries()) {
        const casilla = cell.getAttribute("data-casilla");
        if (!casilla) continue;
        boxes.push({
          key: `r:${table}:${line}:${index}:${casilla}`,
          box: casilla,
          value: norm(cell.textContent),
          typed: typedOf(cell),
        });
      }
    }
  }
  return boxes;
}

/** What the window's records tables name, for the run log only. */
function pageRecordsProbe() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  return [...document.querySelectorAll("[data-records-scroll]")].map(
    (scroll) => ({
      heads: [...scroll.querySelectorAll("thead th")].map((th) =>
        norm(th.textContent).slice(0, 40),
      ),
      rows: scroll.querySelectorAll("tbody tr").length,
      named: scroll.querySelectorAll("td[data-casilla]").length,
    }),
  );
}

/** What the page shows when an expected pane does not: for the run log only. */
function pageDiagnosis() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  return {
    lang: document.documentElement.lang,
    grids: [...document.querySelectorAll('[role="grid"]')].map((grid) => ({
      label: grid.getAttribute("aria-label"),
      shown: grid.getClientRects().length > 0,
      rows: grid.querySelectorAll('[data-slot="data-grid-row"]').length,
    })),
    failed: norm(document.querySelector(".declarations-failed")?.textContent),
    loading: norm(document.querySelector(".declarations-loading")?.textContent),
    headings: [...document.querySelectorAll("h1,h2")].map((h) =>
      norm(h.textContent).slice(0, 80),
    ),
    dialogs: [...document.querySelectorAll('[role="dialog"]')].map((d) =>
      norm(d.textContent).slice(0, 200),
    ),
    body: norm(document.body.innerText).slice(0, 700),
  };
}

/** Choose the nth shown tab of `scope` as a person's press does. */
function pageChooseTab(scope, index) {
  const list = document.querySelector(scope);
  const tabs = [...(list?.querySelectorAll('[role="tab"]') ?? [])].filter(
    (tab) => tab.getClientRects().length > 0,
  );
  const tab = tabs[index];
  if (!tab) return null;
  tab.scrollIntoView({ block: "nearest", inline: "nearest" });
  tab.dispatchEvent(
    new MouseEvent("mousedown", { bubbles: true, cancelable: true, button: 0 }),
  );
  tab.focus();
  return {
    selected: tab.getAttribute("aria-selected"),
    label: (tab.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 60),
  };
}

/** The form's drawn structure, for the run log when its boxes are not found. */
function pageFormProbe() {
  const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
  const root = document.querySelector("[data-modelo-form]");
  if (!root)
    return { form: false, body: norm(document.body.innerText).slice(0, 400) };
  const keyed = [...root.querySelectorAll("[data-key]")];
  const rect = root.getBoundingClientRect();
  return {
    form: true,
    viewport: [window.innerWidth, window.innerHeight],
    rect: [Math.round(rect.top), Math.round(rect.height)],
    scroll: [root.scrollHeight, root.clientHeight],
    sections: root.querySelectorAll("section").length,
    rows: root.querySelectorAll('[role="row"]').length,
    keyed: keyed.length,
    keyedKinds: [
      ...new Set(
        keyed.map((node) => node.tagName + "/" + node.getAttribute("role")),
      ),
    ],
    sample: keyed.slice(0, 3).map((node) => ({
      key: node.getAttribute("data-key"),
      cells: [...node.children].map((child) =>
        norm(child.textContent).slice(0, 60),
      ),
    })),
    text: norm(root.innerText).slice(0, 300),
  };
}

function pageScroll(to) {
  const root = document.querySelector("[data-modelo-form]");
  if (!root) return null;
  const before = root.scrollTop;
  root.scrollTop =
    to === "top" ? 0 : before + Math.max(200, root.clientHeight * 0.75);
  return {
    top: root.scrollTop,
    last: root.scrollHeight - root.clientHeight,
    moved: root.scrollTop !== before,
  };
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
      ? {
          value: choice.value,
          options: [...choice.options].map((option) => option.value),
        }
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
  Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype,
    "value",
  ).set.call(node, value);
  node.dispatchEvent(new Event("input", { bubbles: true }));
  node.dispatchEvent(new Event("change", { bubbles: true }));
  return node.value === value;
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

const window_ = { browser: null, child: null, closed: true };
let logPath = null;
let label = (key) => key;

function log(event, data = {}) {
  if (logPath === null) return;
  appendFileSync(
    logPath,
    `${JSON.stringify({ at: new Date().toISOString(), event, ...data })}\n`,
  );
}

// WebView2 refuses a script while the view changes state (0x8007139F, "not in
// the correct state"); the same script a moment later runs. Retry only that.
async function exec(fn, ...args) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await window_.browser.execute(fn, ...args);
    } catch (error) {
      if (attempt >= 4 || !String(error?.message).includes("0x8007139F"))
        throw error;
      await sleep(750 * attempt);
    }
  }
}

async function live() {
  try {
    await focusLiveWindow(window_.browser);
  } catch {
    // Reported by the command that follows.
  }
}

async function waitFor(read, { timeout, what, interval = 500, soft = false }) {
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

async function clickSelector(selector) {
  const element = await window_.browser.$(selector);
  await element.waitForExist({ timeout: 15_000 });
  await element.click();
}

/** Click the first shown element under `scope` whose text matches; false if none. */
async function clickText(scope, item, texts, mode = "equals") {
  const text = await exec(pageMarkByText, scope, item, texts, mode, MARK);
  if (text === null) return false;
  await clickSelector(`[${MARK}]`);
  return true;
}

const readState = () =>
  exec(
    pageState,
    Object.fromEntries(
      NEXT_ACTIONS.map((action) => [
        action,
        label(`workspace.modelo.next_button.${action}`),
      ]),
    ),
  );

const tablist = (key) =>
  `[role="tablist"][aria-label=${JSON.stringify(label(key))}]`;

async function openView(key) {
  const opened = await clickText(
    tablist("desktop.modelo.views.label"),
    '[role="tab"]',
    [label(key)],
    "startsWith",
  );
  if (!opened) throw new Error(`the view ${label(key)} is not offered`);
  await sleep(500);
}

/** Wait for a write the header started to answer; dialogs return at once. */
async function settle(before, timeout) {
  const started = Date.now();
  let busySeen = false;
  for (;;) {
    await sleep(400);
    await live();
    const state = await readState();
    if (state.dialogTitle) return state;
    busySeen ||= state.busy;
    const fresh =
      state.alerts.some((text) => !before.alerts.includes(text)) ||
      state.refusals.some((text) => !before.refusals.includes(text));
    const changed =
      state.action !== before.action || fresh || state.unresolved !== "";
    const waited = Date.now() - started;
    if (!state.busy && changed && waited >= 1500) return state;
    if (!state.busy && !changed && !busySeen && waited > 8000) return state;
    if (waited > timeout) return { ...state, timedOut: true };
  }
}

const freshOf = (before, after) => [
  ...after.refusals.filter((text) => !before.refusals.includes(text)),
  ...after.alerts.filter((text) => !before.alerts.includes(text)),
];

async function findings() {
  await openView("workspace.modelo.step.review");
  return exec(() => {
    const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
    return [...document.querySelectorAll("[data-attention-level]")]
      .filter((element) => element.getClientRects().length > 0)
      .slice(0, 6)
      .map((element) => norm(element.textContent).slice(0, 200));
  });
}

/** Answer a dialog the calculation opened; never choose a tax fact the world lacks. */
async function answerDialog(title, row, notes) {
  const dialog = '[role="dialog"]';
  if (title === label("workspace.modelo.calculate.at_risk_title")) {
    await clickText(dialog, "button", [
      label("workspace.modelo.calculate.at_risk_proceed"),
    ]);
    notes.push("accepted the at-risk prompt");
    return null;
  }
  if (title === label("workspace.modelo.calculate.evidence.title")) {
    // The dialog asks whether a joint return was elected and, for the year's
    // last period, to confirm a Modelo 390 attestation the window authors
    // itself. The world carries the table request's attestation (attachment
    // id and digest, `m303_evidence`) but not the joint-return answer, so no
    // tax fact is chosen here: the dialog is cancelled and the stage is
    // incomplete.
    await clickText(dialog, "button", [
      label("workspace.modelo.calculate.evidence.cancel"),
    ]);
    return "m303 evidence dialog";
  }
  await window_.browser.keys("Escape");
  return `unexpected dialog: ${title}`;
}

async function runAction(action, before, timeout, row) {
  const clicked = await clickText("header", "button", [
    label(`workspace.modelo.next_button.${action}`),
  ]);
  if (!clicked) throw new Error(`the ${action} button is not shown`);
  const notes = [];
  const started = Date.now();
  for (;;) {
    const state = await settle(
      before,
      Math.max(timeout - (Date.now() - started), 1000),
    );
    if (!state.dialogTitle) {
      // A finished write that left the declaration unread holds the form until
      // it is read again; the operator presses the notice's button, and so do we.
      const reread = await clickText(".modelo-write-hold", "button", [
        label("workspace.modelo.read_again"),
      ]);
      if (!reread) return { state, notes, declined: null };
      notes.push("read the declaration again after the write");
      log("read-again", { action });
      return {
        state: await settle(
          before,
          Math.max(timeout - (Date.now() - started), 1000),
        ),
        notes,
        declined: null,
      };
    }
    const declined = await answerDialog(state.dialogTitle, row, notes);
    // The dialog leaves with an animation; settle must not see it again.
    await waitFor(async () => !(await readState()).dialogTitle, {
      timeout: 10_000,
      what: "the dialog to close",
      soft: true,
      interval: 300,
    });
    if (declined) return { state: await readState(), notes, declined };
  }
}

function describeNotPass(state, listed) {
  return [
    state.banner,
    state.unresolved,
    ...listed,
    state.action
      ? `next: ${label(`workspace.modelo.next_button.${state.action}`)}`
      : "",
  ]
    .filter(Boolean)
    .join(" | ");
}

/** Every box the form shows, page by page, scrolling to draw the lazy sections. */
async function readFigures() {
  await openView("desktop.modelo.view.form");
  const pages = await exec(
    pageTexts,
    tablist("desktop.modelo.form.pages"),
    '[role="tab"]',
  );
  const seen = new Map();
  const readPage = async (name) => {
    log("form-page", {
      name,
      probe: await exec(pageFormProbe),
      records: await exec(pageRecordsProbe),
    });
    const before = seen.size;
    await exec(pageScroll, "top");
    let atEnd = 0;
    for (let step = 0; step < 400 && atEnd < 2; step += 1) {
      await sleep(250);
      for (const box of (await exec(pageBoxes)) ?? [])
        if (!seen.has(box.key)) seen.set(box.key, box);
      const where = await exec(pageScroll, "down");
      if (!where || !where.moved || where.top >= where.last - 2) atEnd += 1;
      else atEnd = 0;
    }
    log("form-page-read", { name, new: seen.size - before, total: seen.size });
  };
  if (pages.length === 0) await readPage("(single)");
  for (let index = 0; index < pages.length; index += 1) {
    // Radix tabs choose on mouse down or focus; a WebDriver click did not
    // change the page, so the same events are sent from the page.
    const chosen = await exec(
      pageChooseTab,
      tablist("desktop.modelo.form.pages"),
      index,
    );
    log("form-tab", { index, chosen });
    await sleep(700);
    await readPage(pages[index]);
  }
  const figures = {};
  const conflicts = [];
  const language = await exec(() => document.documentElement.lang);
  let typedBoxes = 0;
  for (const { box, value, typed } of seen.values()) {
    if (!box || !value || value === "—" || isZeroText(value)) continue;
    // The typed scalar the form serves wins; without one, a number is
    // written as a plain decimal and any other text stays as displayed.
    const figure = typed ? typed.text : plainDecimal(value, language);
    if (typed) typedBoxes += 1;
    if (box in figures && figures[box] !== figure)
      conflicts.push({ box, kept: figures[box], other: figure });
    else figures[box] ??= figure;
  }
  log("figures", {
    typedBoxes,
    pages,
    boxes: seen.size,
    shown: Object.keys(figures).length,
    conflicts,
  });
  return figures;
}

/**
 * A fresh profile opens the "set up Cadrumo" dialog over the workspace. Local
 * AI and the browser stay unconfigured: the dialog is dismissed with its own
 * "not now" (or "close") button, and nothing in it is started.
 */
async function dismissSetup() {
  const title = label("desktop.setup.title");
  const open = await exec(
    (wanted) =>
      [...document.querySelectorAll('[role="dialog"]')].some(
        (dialog) =>
          dialog.getClientRects().length > 0 &&
          (dialog.textContent ?? "").includes(wanted),
      ),
    title,
  );
  if (!open) return false;
  const dismissed = await clickText('[role="dialog"]', "button", [
    label("desktop.setup.not_now"),
    label("desktop.setup.close"),
  ]);
  if (dismissed) log("setup-dismissed", { dialog: title });
  await sleep(600);
  return dismissed;
}

async function showList() {
  const overview = label("workspace.declarations.destination.overview");
  const ready = async () => {
    await dismissSetup();
    const list = await exec(pageList, overview);
    if (list.failed) throw new Error("the declarations list could not be read");
    return list.grid && !list.loading ? list : null;
  };
  let list = await ready();
  if (list) return list;
  if ((await readState()).workspace)
    await clickText("header", "button", [overview]);
  // The Debug build takes about a minute to draw the first list.
  list = await waitFor(ready, {
    timeout: 75_000,
    what: "the list",
    soft: true,
  });
  if (list) return list;
  // The rail toggles its pane: press it only when the pane is not open.
  const rail = await exec(() => {
    const node = document.querySelector('[data-rail="declarations"]');
    return node
      ? {
          pressed: node.getAttribute("aria-pressed"),
          disabled: node.getAttribute("aria-disabled"),
        }
      : null;
  });
  log("rail", { rail });
  if (rail?.pressed !== "true")
    await clickSelector('[data-rail="declarations"]');
  try {
    return await waitFor(ready, {
      timeout: TIMEOUT.list,
      what: "the declarations list",
    });
  } catch (error) {
    log("list-diagnosis", {
      wanted: overview,
      page: await exec(pageDiagnosis),
    });
    throw error;
  }
}

async function openWork(row) {
  await showList();
  const search = await window_.browser.$("input.declarations-search");
  await search.waitForExist({ timeout: 15_000 });
  await search.setValue(row.modelo);
  // Every group: the declaration may be listed under any of them.
  await clickText(
    ".declarations-view",
    '[data-slot="segmented-control-item"]',
    [label("workspace.declarations.list.filter.all")],
    "startsWith",
  );
  const found = await waitFor(
    () =>
      exec(pageRowKey, String(row.work_unit_id), row.modelo, String(row.year)),
    {
      timeout: 30_000,
      what: `the list row of ${row.modelo} ${row.year} ${row.period}`,
    },
  );
  log("row", { work_unit_id: row.work_unit_id, via: found.via });
  const views = () => exec(pageVisible, tablist("desktop.modelo.views.label"));
  await exec(pageDouble, found.key, MARK);
  const opened = await waitFor(views, {
    timeout: 60_000,
    what: "the declaration",
    soft: true,
  });
  if (!opened) {
    log("open-diagnosis", { page: await exec(pageDiagnosis) });
    // The synthetic event did not open it: a real double click on the cell,
    // when the list still draws it.
    const cell = await window_.browser.$(`[${MARK}]`);
    if (!(await cell.isExisting()))
      throw new Error("the list row was not opened and is no longer drawn");
    await cell.doubleClick();
    await waitFor(views, { timeout: 60_000, what: "the declaration" });
  }
  // Stable once the next action stops changing.
  let last = null;
  await waitFor(
    async () => {
      const state = await readState();
      const same = last !== null && last === `${state.action}|${state.busy}`;
      last = `${state.action}|${state.busy}`;
      return same && !state.busy;
    },
    { timeout: 120_000, what: "the declaration to be read", interval: 700 },
  );
  const now = await readState();
  log("workspace", {
    title: now.title,
    header: now.headerText,
    action: now.action,
  });
  if (!now.headerText.includes(String(row.year)))
    throw new Error(
      `the window opened a different declaration: "${now.headerText}"`,
    );
}

async function driveRow(row, runDir, persona) {
  const out = {
    calculate: "not-reached",
    verify: "not-reached",
    export: "not-reached",
    figures: {},
    reasons: [],
  };
  const say = (stage, text) => text && out.reasons.push(`${stage}: ${text}`);
  await openWork(row);
  let state = await readState();
  log("opened", {
    title: state.title,
    action: state.action,
    banner: state.banner,
  });

  // Calculate
  if (CALCULATING.includes(state.action)) {
    const run = await runAction(state.action, state, TIMEOUT.calculate, row);
    const words = freshOf(state, run.state);
    for (const note of run.notes) say("calculate", note);
    if (run.declined) {
      out.calculate = "incomplete";
      say("calculate", run.declined);
    } else if (run.state.timedOut) {
      out.calculate = "error";
      say("calculate", "no answer within the wait");
    } else if (words.length > 0) {
      out.calculate = "refused";
      say("calculate", words.join(" | "));
    } else if (
      [...FILED, "verify"].includes(run.state.action) &&
      run.state.unresolved === ""
    ) {
      out.calculate = "pass";
    } else if (CALCULATING.includes(run.state.action)) {
      out.calculate = "error";
      say(
        "calculate",
        "the calculate button is still offered and nothing was said",
      );
    } else {
      out.calculate = "incomplete";
      say("calculate", describeNotPass(run.state, await findings()));
    }
    state = run.state.dialogTitle ? await readState() : run.state;
  } else if (["verify", ...FILED].includes(state.action)) {
    out.calculate = "pass";
    say("calculate", "a calculation was already present; none was run");
  } else {
    out.calculate = "incomplete";
    say("calculate", describeNotPass(state, await findings()));
  }
  log("calculate", { stage: out.calculate });

  // The form, once calculated (also when it came out incomplete)
  if (out.calculate === "pass" || out.calculate === "incomplete")
    out.figures = await readFigures();

  // Verify
  const chain = out.calculate === "pass" || state.action === "verify";
  if (chain && state.action === "verify") {
    const before = await readState();
    const run = await runAction("verify", before, TIMEOUT.verify, row);
    const words = freshOf(before, run.state);
    if (run.state.timedOut) {
      out.verify = "error";
      say("verify", "no answer within the wait");
    } else if (words.length > 0) {
      out.verify = "refused";
      say("verify", words.join(" | "));
    } else if (FILED.includes(run.state.action)) {
      out.verify = "pass";
    } else if (run.state.action === "verify") {
      out.verify = "error";
      say(
        "verify",
        `the verify button is still offered; ${(await findings()).join(" | ")}`,
      );
    } else {
      out.verify = "incomplete";
      say("verify", describeNotPass(run.state, await findings()));
    }
    state = await readState();
  } else if (chain && FILED.includes(state.action)) {
    out.verify = "pass";
    say("verify", "already verified; none was run");
  } else if (out.calculate === "pass") {
    out.verify = "incomplete";
    say("verify", describeNotPass(state, await findings()));
  }
  log("verify", { stage: out.verify });

  // Export
  if (out.verify === "pass")
    out.export = await exportFile(row, runDir, persona, out);
  log("export", { stage: out.export });
  return out;
}

async function exportFile(row, runDir, persona, out) {
  await openView("workspace.modelo.filing.title");
  const names = [
    label("workspace.modelo.filing.export_file"),
    label("workspace.modelo.filing.export_again"),
  ];
  const panel = '[role="tabpanel"]';
  const text = await exec(
    pageMarkByText,
    panel,
    "button",
    names,
    "equals",
    MARK,
  );
  if (text === null) {
    sayExport(out, "the export button is not shown");
    return "incomplete";
  }
  const enabled = await exec(
    (mark) => !document.querySelector(`[${mark}]`).disabled,
    MARK,
  );
  if (!enabled) {
    const why = await exec(
      (mark) =>
        (document.querySelector(`[${mark}]`).parentElement?.innerText ?? "")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 400),
      MARK,
    );
    sayExport(out, `the export button is disabled: ${why}`);
    return "incomplete";
  }
  const stem = `${persona}-${row.modelo}-${row.year}-${row.period}`;
  let destination = join(runDir, "exports", `${stem}.boe`);
  if (existsSync(destination))
    destination = join(runDir, "exports", `${stem}-${Date.now()}.boe`);
  const before = await readState();
  queuePickerSelection(runDir, "save", destination);
  try {
    await clickSelector(`[${MARK}]`);
    const outcome = await waitFor(
      async () => {
        if (existsSync(destination) && statSync(destination).size > 0)
          return { pass: true };
        const state = await readState();
        const words = freshOf(before, state);
        return words.length > 0 ? { words } : null;
      },
      {
        timeout: TIMEOUT.export,
        what: "the export",
        soft: true,
        interval: 700,
      },
    );
    if (outcome?.pass) {
      await sleep(1500);
      log("exported", { bytes: statSync(destination).size, destination });
      return "pass";
    }
    if (outcome?.words) {
      sayExport(out, outcome.words.join(" | "));
      return "refused";
    }
    sayExport(
      out,
      "no file was written and the window said nothing within the wait",
    );
    return "error";
  } finally {
    const queued = join(runDir, "temporary", "native-picker-selection.json");
    if (existsSync(queued)) unlinkSync(queued);
  }
}

function sayExport(out, text) {
  out.reasons.push(`export: ${text}`);
}

// ---------------------------------------------------------------------------
// Launch and teardown (session.mjs start() and stop() with the world's storage)
// ---------------------------------------------------------------------------

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

async function launch(world, runDir) {
  const storage = resolve(runDir, "storage");
  // The world builder's storage root is the directory the profile lives in;
  // the window's picker answers only for <run>/storage, so the run holds a copy.
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
  const same = (left, right) =>
    inspectionPlatform() === "windows"
      ? left.toLowerCase() === right.toLowerCase()
      : left === right;
  // The window's picker answers only for <run>/storage with sibling
  // temporary/ fixtures/ exports/ directories, and hostEnvironment() derives
  // the storage root from the run directory.
  assert(
    same(storage, resolve(runDir, "storage")),
    `the run's storage directory must be named "storage": ${storage}`,
  );
  for (const member of ["temporary", "fixtures", "exports"])
    mkdirSync(resolve(runDir, member), { mode: 0o700, recursive: true });
  let hostJson = process.env.CADRUMO_PERSONA_HOST;
  if (!hostJson) {
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
    hostJson = staged.stdout.trim();
  }
  const host = JSON.parse(hostJson);
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
  Object.assign(window_, {
    child,
    pid: child.pid,
    executable: host.executable,
    closed: false,
  });
  // A crashed spec must not leave the host running.
  process.once("exit", () => {
    if (window_.closed || !window_.pid) return;
    const check = inspectProcess(window_.pid);
    if (check.status === 0 && isHostCommand(check.stdout, window_.executable))
      process.kill(window_.pid, "SIGTERM");
  });
  log("launched", { pid: child.pid, port, runDir });
  await waitForWebDriver(child, port, runDir);
  verifyListener({ pid: child.pid, executable: host.executable, port });
  window_.browser = await remote({
    hostname: "127.0.0.1",
    port,
    path: "/",
    logLevel: "silent",
    connectionRetryCount: 0,
    capabilities: {},
  });
  await proveOwnership(window_.browser, nonce);
  return runDir;
}

async function teardown() {
  if (window_.closed) return;
  window_.closed = true;
  try {
    await window_.browser?.deleteSession();
  } catch (error) {
    log("teardown", { deleteSession: error.message });
  }
  if (!window_.pid) return;
  const check = inspectProcess(window_.pid);
  if (check.status === 0 && isHostCommand(check.stdout, window_.executable)) {
    process.kill(window_.pid, "SIGTERM");
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await sleep(250);
      if (inspectProcess(window_.pid).status !== 0) break;
    }
    log("teardown", { terminated: window_.pid });
  } else {
    log("teardown", {
      status: check.status,
      note: "host identity not confirmed; not terminated",
    });
  }
}

async function signIn(password) {
  const info = await waitFor(
    async () => {
      const found = await exec(pageSignIn);
      return found.password ? found : null;
    },
    { timeout: TIMEOUT.signIn, what: "the sign-in form" },
  );
  if (info.choice && info.choice.value !== PROFILE) {
    if (!info.choice.options.includes(PROFILE))
      throw new Error(
        `profile "${PROFILE}" is not offered; offered: ${info.choice.options.join(", ")}`,
      );
    assert(await exec(pageChoose, PROFILE), "the profile choice did not take");
  } else if (!info.choice && info.named !== PROFILE) {
    throw new Error(`the sign-in form names profile "${info.named}"`);
  }
  const field = await window_.browser.$("#profile-password");
  await field.setValue(password);
  await clickSelector(".sign-in button[type=submit]");
  const answer = await waitFor(
    async () => {
      const now = await exec(pageSignIn);
      if (now.rail && !now.password) return { ok: true };
      if (now.words.length > 0 && !now.busy) {
        await sleep(1000);
        return { ok: false, words: (await exec(pageSignIn)).words };
      }
      return null;
    },
    { timeout: TIMEOUT.signIn, what: "the sign-in answer", soft: true },
  );
  if (!answer)
    throw new Error(`no sign-in answer: ${(await exec(pageSignIn)).text}`);
  if (!answer.ok)
    throw new Error(`sign-in refused: ${answer.words.join(" | ")}`);
}

// ---------------------------------------------------------------------------
// The spec
// ---------------------------------------------------------------------------

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function profileCredential() {
  const match = /^_PROFILE_CREDENTIAL\s*=\s*"([^"\n]+)"/m.exec(
    readFileSync(CREDENTIAL_SOURCE, "utf8"),
  );
  if (!match)
    throw new Error("no _PROFILE_CREDENTIAL in persona_materialisation.py");
  return match[1];
}

// A value that reads as zero in the Spanish or the English number format
// ("0", "0,00 €", "0.00 %"): it holds digits and every digit is 0.
const isZeroText = (value) => {
  const bare = value.replace(/[\s €%$]/g, "");
  return /\d/.test(bare) && /^[-+]?[0.,]*$/.test(bare);
};

/**
 * A displayed number as a plain decimal string ("−2.158,99 €" -> "-2158.99").
 * Used only where the form serves no typed value. The grouping and decimal
 * marks are read from the shape of the text under the window's language
 * (Spanish, Catalan and Hungarian write a decimal comma; English a point);
 * text that is not wholly a number is returned unchanged.
 */
const plainDecimal = (value, language) => {
  const bare = value
    .replace(/[\s  ]/g, "")
    .replace(/[€%$]$/, "")
    .replace(/^[−‒–]/, "-");
  if (!/^[-+]?\d[\d.,]*$/.test(bare)) return value;
  const comma = !(language ?? "").toLowerCase().startsWith("en");
  const [group, decimal] = comma ? [".", ","] : [",", "."];
  const pattern = new RegExp(
    `^[-+]?(\\d+|\\d{1,3}(\\${group}\\d{3})+)(\\${decimal}\\d+)?$`,
  );
  if (!pattern.test(bare)) return value;
  return bare.split(group).join("").replace(decimal, ".").replace(/^\+/, "");
};

const STAGES = [
  "pass",
  "incomplete",
  "refused",
  "not-owed",
  "not-reached",
  "error",
];
const KEYS = [
  "surface",
  "tree",
  "persona",
  "modelo",
  "year",
  "period",
  "loads",
  "calculate",
  "verify",
  "export",
  "refusal_code",
  "figures",
  "reason",
  "log",
];

/** The acceptance intake refuses unknown keys and unknown stages; so does this. */
function assertContract(line) {
  // The stage keys are required once a modelo is named; a persona line has none.
  const expected =
    line.modelo === null
      ? KEYS.filter((key) => !["calculate", "verify", "export"].includes(key))
      : KEYS;
  assert.deepEqual(Object.keys(line).sort(), [...expected].sort(), "line keys");
  assert.equal(line.surface, "window");
  assert.equal(typeof line.loads, "boolean");
  if (line.modelo === null) {
    assert(line.year === null && line.period === null, "persona line");
  } else {
    assert.equal(typeof line.modelo, "string");
    assert(Number.isInteger(line.year), "year is an integer");
    assert.equal(typeof line.period, "string");
    for (const stage of ["calculate", "verify", "export"])
      assert(STAGES.includes(line[stage]), `${stage}: ${line[stage]}`);
  }
  assert(line.refusal_code === null || typeof line.refusal_code === "string");
  assert(
    Object.values(line.figures).every((value) => typeof value === "string"),
  );
  assert.equal(typeof line.reason, "string");
  assert.equal(typeof line.log, "string");
}

const stageOfPre = (outcome) =>
  String(outcome).replace(/_/g, "-") === "not-owed" ? "not-owed" : "refused";

test(
  "the persona's declarations through the native window",
  { timeout: 6 * 3600 * 1000 },
  async (t) => {
    const worldPath = requiredEnv("CADRUMO_PERSONA_WORLD");
    const resultsPath = requiredEnv("CADRUMO_PERSONA_RESULTS");
    const tree = requiredEnv("CADRUMO_TREE");
    requiredEnv("CADRUMO_CMAKE_BINARY_DIR");
    requiredEnv("CADRUMO_BUILD_CONFIG");
    const world = JSON.parse(readFileSync(worldPath, "utf8"));
    assert(world.persona && world.storage_root && Array.isArray(world.rows));
    mkdirSync(dirname(resolve(resultsPath)), { recursive: true });
    logPath = join(
      dirname(resolve(resultsPath)),
      `window-${world.persona}.log`,
    );
    writeFileSync(logPath, "");
    const password = profileCredential();
    const emit = (line) => {
      const full = {
        surface: "window",
        tree,
        persona: world.persona,
        ...line,
        // The table's case id (persona@horizon) leads the free text, so a
        // line says which world, replayed under which horizon, it ran in.
        reason: `${world.persona}@${world.horizon}: ${line.reason}`,
        log: logPath,
      };
      assertContract(full);
      appendFileSync(resultsPath, `${JSON.stringify(full)}\n`);
    };

    let runDir = resolve(
      process.env.CADRUMO_PERSONA_RUN || dirname(resolve(resultsPath)),
    );
    const loadsOnly = process.env.CADRUMO_PERSONA_LOADS_ONLY === "1";
    let loadError = null;
    let rowCount = 0;
    try {
      runDir = await launch(world, runDir);
      await signIn(password);
      const lang =
        process.env.CADRUMO_PERSONA_LANGUAGE ||
        (await exec(() => document.documentElement.lang)) ||
        "en";
      const catalogue = JSON.parse(
        readFileSync(
          resolve(
            buildPath("desktop_frontend_generated"),
            "chrome-strings.json",
          ),
          "utf8",
        ),
      );
      const strings = catalogue[lang] ?? catalogue[lang.split("-")[0]] ?? {};
      label = (key) => strings[key] ?? catalogue.en?.[key] ?? key;
      const list = await showList();
      rowCount = list.rows;
      log("loaded", { lang, rows: list.rows });
    } catch (error) {
      loadError = error;
      log("load-failed", { message: error.message });
    }

    try {
      emit({
        modelo: null,
        year: null,
        period: null,
        loads: loadError === null,
        refusal_code: null,
        figures: {},
        reason:
          loadError === null
            ? `signed in to profile ${PROFILE}; the declarations list shows ${rowCount} rows`
            : `the window did not load the profile: ${loadError.message}`,
      });
      for (const row of loadsOnly ? [] : world.rows) {
        await t.test(`${row.modelo} ${row.year} ${row.period}`, async () => {
          const base = {
            modelo: row.modelo,
            year: Number(row.year),
            period: row.period,
            refusal_code: null,
          };
          if (!row.prepared) {
            const stage = stageOfPre(row.pre_calculate_outcome);
            emit({
              ...base,
              loads: loadError === null,
              calculate: stage,
              verify: stage === "refused" ? "not-reached" : stage,
              export: stage === "refused" ? "not-reached" : stage,
              figures: {},
              reason: row.reason || String(row.pre_calculate_outcome),
            });
            return;
          }
          if (loadError !== null) {
            emit({
              ...base,
              loads: false,
              calculate: "not-reached",
              verify: "not-reached",
              export: "not-reached",
              figures: {},
              reason: `the window did not load the profile: ${loadError.message}`,
            });
            return;
          }
          let out;
          try {
            out = await driveRow(row, runDir, world.persona);
          } catch (error) {
            log("row-error", { message: error.message });
            out = {
              calculate: "error",
              verify: "not-reached",
              export: "not-reached",
              figures: {},
              reasons: [error.message],
            };
            await live();
          }
          emit({
            ...base,
            loads: true,
            calculate: out.calculate,
            verify: out.verify,
            export: out.export,
            figures: out.figures,
            reason:
              out.reasons.join("; ").slice(0, 1200) ||
              (out.export === "pass"
                ? "calculated, verified and exported in the window"
                : ""),
          });
        });
      }
    } finally {
      await teardown();
    }
    if (loadError !== null) throw loadError;
  },
);
