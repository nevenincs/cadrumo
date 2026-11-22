// Bulk editing in Libro, in the packaged native window, on a disposable
// synthetic world: the persona's movements plus unclassified synthetic ones
// (python -m dev.desktop_persona_world --extra-movements N). One window serves
// the whole file; each test leaves the window on the movements grid.
//
// LBE-01 Shift selects a range and Ctrl-click adds single movements.
// LBE-02 one category for ten movements: the review previews every row before
//        Save, Save writes one batch, and the per-row result is shown.
// LBE-03 the saved batch is undone by a new batch that writes the earlier
//        values back.
// LBE-04 one contact for every synthetic movement (the shown rows after a
//        search), previewed and saved: the large batch.
// LBE-05 properties copied from one movement are pasted onto a selection
//        through the preview; a row the ledger refuses is shown with its cause
//        and only the others are staged.
//
// Every test records how long the window took (the review's preview and the
// save, from the press to the drawn answer) and how long the host took to
// answer the batch definitions, one JSON object per line, to
// <run>/ledger-bulk-edit.jsonl. Screenshots go to CADRUMO_UX_SHOTS when set.
//
// Environment: as ./window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN; CADRUMO_UX_STAGED_SHA256 is compared with the executable the
// run drove when it is set), plus
//   CADRUMO_UX_SHOTS  (optional) directory for the screenshots
// The world must carry extra movements; their count is read from the world.
import assert from "node:assert/strict";
import { appendFileSync, mkdirSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import {
  clickText,
  exec,
  label,
  runIdentity,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { callsSince, pageTimeInvokes } from "./ux-calls.mjs";
import { dismissSetup, openRailPage } from "./ux-nav.mjs";

const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();
const SHOTS = process.env.CADRUMO_UX_SHOTS ?? null;
const ANSWER_MS = 120_000;
const PAGE = "section.ledger-page";
const SYNTHETIC = "MOVIMIENTO SINTETICO";
const PREVIEW = "ledger.update.batch.preview";
const APPLY = "ledger.update.batch";
const SMALL = 10;
const CATEGORY = "desktop.ledger.category.material_oficina";
const CONTACT = "Proveedor Sintetico SL";

/** A chrome string with its `{name}` slots filled. */
function words(key, values = {}) {
  const one = values.count === 1 ? label(`${key}_one`) : null;
  const text = one && one !== `${key}_one` ? one : label(key);
  return text.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
}

let runDir;
let results;
let world;
const extra = { count: 0 };

function record(line) {
  appendFileSync(results, `${JSON.stringify(line)}\n`);
  console.info(JSON.stringify(line));
}

async function shot(name) {
  if (!SHOTS) return null;
  mkdirSync(SHOTS, { recursive: true });
  const path = join(SHOTS, `${name}.png`);
  await win.browser.saveScreenshot(path);
  return path;
}

// ---------------------------------------------------------------------------
// Page-side readers and presses (serialised into the window)
// ---------------------------------------------------------------------------

/** What the movements grid and its selection show now. */
function pageLedger(synthetic) {
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const page = [...document.querySelectorAll("section.ledger-page")].find(
    shown,
  );
  const rows = page
    ? [...page.querySelectorAll('[role="grid"] [data-kind="data"]')].filter(
        shown,
      )
    : [];
  const text = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
  return {
    page: !!page,
    count: text(page?.querySelector(".ledger-count")),
    rows: rows.map((row) => ({
      key: row.getAttribute("data-key"),
      description: text(row.querySelector("[data-column=description]")),
      amount: text(row.querySelector("[data-column=amount]")),
      category: text(row.querySelector("[data-column=category]")),
      selected: row.getAttribute("aria-selected") === "true",
      synthetic: text(row.querySelector("[data-column=description]")).includes(
        synthetic,
      ),
    })),
  };
}

/**
 * Press an element as a pointer does: pointerdown, mousedown, pointerup,
 * mouseup and click, carrying the modifier keys. Radix menus open on
 * pointerdown, which the WebDriver click does not send with modifiers.
 */
function pagePress(selector, key, modifiers) {
  const root = key
    ? document.querySelector(
        `section.ledger-page [data-kind="data"][data-key="${CSS.escape(key)}"]`,
      )
    : document;
  const el = key ? root?.querySelector(selector) : root.querySelector(selector);
  if (!el || !el.getClientRects().length) return false;
  const mods = {
    shiftKey: modifiers.includes("shift"),
    ctrlKey: modifiers.includes("ctrl"),
    metaKey: false,
    altKey: false,
  };
  const at = el.getBoundingClientRect();
  const base = {
    bubbles: true,
    cancelable: true,
    composed: true,
    button: 0,
    clientX: at.left + at.width / 2,
    clientY: at.top + at.height / 2,
    ...mods,
  };
  el.dispatchEvent(
    new PointerEvent("pointerdown", {
      ...base,
      buttons: 1,
      pointerType: "mouse",
      isPrimary: true,
    }),
  );
  el.dispatchEvent(new MouseEvent("mousedown", { ...base, buttons: 1 }));
  el.dispatchEvent(
    new PointerEvent("pointerup", {
      ...base,
      pointerType: "mouse",
      isPrimary: true,
    }),
  );
  el.dispatchEvent(new MouseEvent("mouseup", base));
  el.dispatchEvent(new MouseEvent("click", base));
  return true;
}

/**
 * Scroll the movements grid's scroll container to `top` (null keeps it) and,
 * when `key` names a drawn row, bring that row into view. Answers where the
 * container is and how far it scrolls.
 */
function pageScroll(top, key) {
  const shown = (el) => !!el && el.getClientRects().length > 0;
  const page = [...document.querySelectorAll("section.ledger-page")].find(
    shown,
  );
  const grid = page?.querySelector('[role="grid"]');
  let box = grid;
  while (box && box !== document.body) {
    const style = getComputedStyle(box);
    if (
      /(auto|scroll)/.test(style.overflowY) &&
      box.scrollHeight > box.clientHeight + 2
    )
      break;
    box = box.parentElement;
  }
  if (!box || box === document.body) return null;
  if (top !== null) box.scrollTop = top;
  const row = key
    ? page.querySelector(`[data-kind="data"][data-key="${CSS.escape(key)}"]`)
    : null;
  if (row) row.scrollIntoView({ block: "center" });
  return {
    top: box.scrollTop,
    max: box.scrollHeight - box.clientHeight,
    step: Math.max(1, Math.floor(box.clientHeight * 0.75)),
    found: !!row,
  };
}

function pageShown(selector) {
  return [...document.querySelectorAll(selector)].some(
    (el) => el.getClientRects().length > 0,
  );
}

function pageText(selector) {
  const el = [...document.querySelectorAll(selector)].find(
    (e) => e.getClientRects().length > 0,
  );
  return el ? el.textContent.replace(/\s+/g, " ").trim() : null;
}

/** The rows a batch preview could not write, with their causes and words. */
function pageUnwritten(scope) {
  const root = [...document.querySelectorAll(scope)].find(
    (e) => e.getClientRects().length > 0,
  );
  return [
    ...(root?.querySelectorAll(".ledger-batch-unwritten [data-batch-row]") ??
      []),
  ].map((row) => ({
    outcome: row.getAttribute("data-batch-row"),
    cause: row.getAttribute("data-cause"),
    text: row.textContent.replace(/\s+/g, " ").trim().slice(0, 200),
  }));
}

// ---------------------------------------------------------------------------
// Window steps
// ---------------------------------------------------------------------------

const ledger = () => exec(pageLedger, SYNTHETIC);

/** Every movement in the grid, read by scrolling its drawn window through. */
async function allRows() {
  const seen = new Map();
  let at = await exec(pageScroll, 0, null);
  for (;;) {
    await sleep(250);
    for (const row of (await ledger()).rows)
      if (!seen.has(row.key)) seen.set(row.key, row);
    if (!at || at.top >= at.max) break;
    at = await exec(pageScroll, Math.min(at.max, at.top + at.step), null);
  }
  await exec(pageScroll, 0, null);
  await sleep(250);
  return [...seen.values()];
}

/** Scroll the grid until the row `key` is drawn, and centre it. */
async function reveal(key) {
  let at = await exec(pageScroll, null, key);
  if (at?.found) return sleep(150);
  at = await exec(pageScroll, 0, null);
  for (;;) {
    // The grid draws the rows of a new position after the scroll settles.
    await sleep(200);
    at = await exec(pageScroll, null, key);
    if (!at || at.found || at.top >= at.max) break;
    await exec(pageScroll, Math.min(at.max, at.top + at.step), null);
  }
  assert(at?.found, `row ${key} is not in the grid`);
  return sleep(150);
}

async function press(selector, key = null, modifiers = []) {
  if (key) await reveal(key);
  return exec(pagePress, selector, key, modifiers);
}

async function pressOrFail(selector, what, key = null, modifiers = []) {
  assert(await press(selector, key, modifiers), `${what} is not shown`);
}

let missed = 0;

async function shownWithin(selector, what, timeout = ANSWER_MS) {
  const shown = await waitFor(() => exec(pageShown, selector), {
    timeout,
    what,
    soft: true,
  });
  if (shown) return shown;
  missed += 1;
  const path = await shot(`missed-${missed}`);
  assert.fail(`${what} did not show within ${timeout} ms (screenshot ${path})`);
}

async function typeKeys(text) {
  await win.browser.keys([...text]);
}

async function enter() {
  await win.browser.keys([""]);
}

async function escape() {
  await win.browser.keys([""]);
}

/** Back to the movements grid with no selection, search or open dialog. */
async function resetGrid() {
  for (let i = 0; i < 3; i += 1) {
    if (!(await exec(pageShown, '[role="dialog"]'))) break;
    await escape();
    await sleep(400);
  }
  if (await exec(pageShown, `${PAGE} .ledger-search`)) {
    const search = await win.browser.$(`${PAGE} .ledger-search`);
    await search.clearValue();
  }
  const reached = await openRailPage("ledger", PAGE);
  assert(reached.reached, reached.reason ?? "the ledger did not open");
  // The Libro opens on the current quarter; the world's movements span the
  // horizon year, so every walk works on all periods.
  await pressOrFail("button.ledger-period", "the period choice");
  await shownWithin(
    ".ledger-period-menu .ledger-period-all",
    "All periods",
    10_000,
  );
  await pressOrFail(".ledger-period-menu .ledger-period-all", "All periods");
  await waitFor(async () => !(await exec(pageShown, ".ledger-period-menu")), {
    timeout: 10_000,
    what: "the period menu to close",
  });
  const filled = await waitFor(async () => (await ledger()).rows.length > 0, {
    timeout: ANSWER_MS,
    what: "movements in the grid",
    soft: true,
  });
  if (!filled) {
    const path = await shot("no-movements");
    const page = await exec(pageText, PAGE);
    assert.fail(
      `no movements in the grid (screenshot ${path}): ${(page ?? "no ledger page").slice(0, 600)}`,
    );
  }
  if ((await ledger()).rows.some((row) => row.selected)) await escape();
}

async function selectKeys(keys) {
  for (const [at, key] of keys.entries())
    await pressOrFail(
      "[data-column=status]",
      `row ${key}`,
      key,
      at === 0 ? [] : ["ctrl"],
    );
  await waitFor(
    async () =>
      (await ledger()).count.includes(
        words("desktop.ledger.selected", { count: keys.length }),
      ),
    { timeout: 10_000, what: `${keys.length} selected` },
  );
}

/** The longest host answer to `definition` among the calls since `since`. */
async function hostMs(since, definition) {
  const calls = (await callsSince(since)).filter(
    (call) => call.definition === definition && call.endMs !== null,
  );
  return {
    calls: calls.length,
    ms: calls.length
      ? Math.max(...calls.map((call) => call.endMs - call.startMs))
      : null,
    failed: calls.filter((call) => call.ok === false).length,
  };
}

/** Open the review from the tray and time it until the preview's counts show. */
async function reviewAndPreview() {
  const since = Date.now();
  await pressOrFail(".ledger-tray .ledger-tray-review", "the tray's review");
  await shownWithin(".ledger-review .ledger-batch-counts", "the batch preview");
  const windowMs = Date.now() - since;
  return {
    window_ms: windowMs,
    host: await hostMs(since, PREVIEW),
    counts: await exec(pageText, ".ledger-review .ledger-batch-counts"),
    unwritten: await exec(pageUnwritten, ".ledger-review"),
  };
}

/** Save the review and time it until the written result shows. */
async function saveAndWait() {
  await waitFor(
    () =>
      exec(() => {
        const save = document.querySelector(
          ".ledger-review .ledger-apply-save",
        );
        return !!save && save.getAttribute("aria-disabled") !== "true";
      }),
    { timeout: ANSWER_MS, what: "Save to take the batch" },
  );
  const since = Date.now();
  await pressOrFail(".ledger-review .ledger-apply-save", "Save");
  await shownWithin(".ledger-review .ledger-apply-done", "the saved result");
  return {
    window_ms: Date.now() - since,
    host: await hostMs(since, APPLY),
    written: await exec(pageText, ".ledger-review .ledger-batch-written"),
    unwritten: await exec(pageUnwritten, ".ledger-review"),
  };
}

async function done() {
  await pressOrFail(".ledger-review .ledger-apply-done", "Done");
  await waitFor(async () => !(await exec(pageShown, ".ledger-review")), {
    timeout: 10_000,
    what: "the review to close",
  });
}

/** Stage one category for the selection through the selection's actions menu. */
async function stageCategory(count, key) {
  await pressOrFail(
    `${PAGE} .ledger-selection-actions`,
    "the selection actions",
  );
  await shownWithin('[role="menu"]', "the selection actions menu", 10_000);
  assert(
    await clickText('[role="menu"]', '[role="menuitem"]', [
      `${label("desktop.ledger.group.category")}…`,
    ]),
    "no Category… in the selection actions",
  );
  await shownWithin(".ledger-classify", "the category dialog", 10_000);
  await pressOrFail(
    ".ledger-classify .ledger-classify-category",
    "the category choice",
  );
  await sleep(400);
  await typeKeys(label(key));
  await sleep(400);
  await enter();
  await sleep(400);
  await pressOrFail(
    ".ledger-classify .ledger-classify-stage",
    "the dialog's stage button",
  );
  await waitFor(async () => !(await exec(pageShown, ".ledger-classify")), {
    timeout: 10_000,
    what: "the category dialog to close",
  });
  await shownWithin(".ledger-tray", `the tray with ${count} staged`, 10_000);
}

async function ensurePanel() {
  if (await exec(pageShown, "aside.ledger-panel")) return;
  await win.browser.keys(["", "i"]);
  await win.browser.keys([""]);
  await shownWithin("aside.ledger-panel", "the inspector", 10_000);
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-bulk-edit-")), "run");
  results = join(runDir, "ledger-bulk-edit.jsonl");
  world = JSON.parse(readFileSync(process.env.CADRUMO_PERSONA_WORLD, "utf8"));
  extra.count = Number(world.extra_movements ?? 0);
  await start(runDir);
  await dismissSetup();
  assert(await exec(pageTimeInvokes), "the window's host calls are not timed");
});
after(async () => {
  if (!win.closed) await teardown();
});

test("LBE-00 the run records the host it drove and the world it edits", () => {
  const line = {
    case: "LBE-00",
    exe_sha256: runIdentity.exeSha256,
    bundle: runIdentity.bundle,
    persona: world.persona,
    extra_movements: extra.count,
  };
  record(line);
  assert.equal(runIdentity.error, null, runIdentity.error ?? "");
  if (STAGED_SHA256)
    assert.equal(runIdentity.exeSha256?.toLowerCase(), STAGED_SHA256);
  assert(extra.count >= SMALL, "the world carries no extra movements");
});

test("LBE-01 Shift selects a range and Ctrl-click adds single movements", async () => {
  await resetGrid();
  const rows = (await ledger()).rows;
  assert(rows.length >= 6, `only ${rows.length} movements shown`);
  await pressOrFail("[data-column=status]", "the first row", rows[0].key);
  await pressOrFail("[data-column=status]", "the fourth row", rows[3].key, [
    "shift",
  ]);
  const range = await waitFor(
    async () => {
      const now = await ledger();
      return now.count.includes(words("desktop.ledger.selected", { count: 4 }))
        ? now
        : null;
    },
    { timeout: 10_000, what: "4 selected after Shift", soft: true },
  );
  await pressOrFail("[data-column=status]", "the sixth row", rows[5].key, [
    "ctrl",
  ]);
  const added = await waitFor(
    async () => {
      const now = await ledger();
      return now.count.includes(words("desktop.ledger.selected", { count: 5 }))
        ? now
        : null;
    },
    { timeout: 10_000, what: "5 selected after Ctrl", soft: true },
  );
  const line = {
    case: "LBE-01",
    shift_range: range?.count ?? (await ledger()).count,
    ctrl_added: added?.count ?? (await ledger()).count,
    screenshot: await shot("lbe-01-selection"),
  };
  record(line);
  assert(range, `Shift did not select 4: ${line.shift_range}`);
  assert(added, `Ctrl did not add a fifth: ${line.ctrl_added}`);
  await escape();
});

const savedSmall = { keys: [], before: [] };

test("LBE-02 one category for ten movements is previewed per row, saved as one batch and reported per row", async () => {
  await resetGrid();
  const rows = (await allRows()).filter(
    (row) => !row.synthetic && row.category !== label(CATEGORY),
  );
  assert(rows.length >= SMALL, `only ${rows.length} persona movements shown`);
  const chosen = rows.slice(0, SMALL);
  savedSmall.keys = chosen.map((row) => row.key);
  savedSmall.before = chosen.map((row) => row.category);
  await selectKeys(savedSmall.keys);
  await stageCategory(SMALL, CATEGORY);
  const preview = await reviewAndPreview();
  const previewShot = await shot("lbe-02-preview");
  const saved = await saveAndWait();
  const savedShot = await shot("lbe-02-saved");
  record({
    case: "LBE-02",
    rows: SMALL,
    preview,
    saved,
    screenshots: [previewShot, savedShot],
  });
  assert.equal(
    preview.counts,
    words("desktop.ledger.batch.count.applied", { count: SMALL }),
  );
  assert.equal(preview.host.failed, 0, "a preview call failed");
  assert(preview.host.calls > 0, "the review asked the host for no preview");
  assert.equal(saved.host.calls, 1, "Save did not write one batch");
  assert.equal(
    saved.written,
    words("desktop.ledger.batch.written.applied", { count: SMALL }),
  );
});

test("LBE-03 the saved batch is undone by a new batch that writes each earlier value back", async () => {
  assert(savedSmall.keys.length === SMALL, "LBE-02 saved nothing to undo");
  await pressOrFail(".ledger-review .ledger-batch-undo", "Undo");
  await shownWithin(
    ".ledger-review .ledger-batch-counts",
    "the undo's preview",
  );
  const counts = await exec(pageText, ".ledger-review .ledger-batch-counts");
  const saved = await saveAndWait();
  await done();
  const after = (await allRows()).filter((row) =>
    savedSmall.keys.includes(row.key),
  );
  const restored = savedSmall.keys.every(
    (key, at) =>
      after.find((row) => row.key === key)?.category === savedSmall.before[at],
  );
  record({
    case: "LBE-03",
    rows: SMALL,
    undo_preview: counts,
    saved,
    restored,
    screenshot: await shot("lbe-03-undone"),
  });
  assert.equal(
    counts,
    words("desktop.ledger.batch.count.applied", { count: SMALL }),
  );
  assert.equal(saved.host.calls, 1, "the undo did not write one batch");
  assert(restored, "a movement did not get its earlier category back");
});

test("LBE-04 one contact for every synthetic movement is previewed and saved as one large batch", async () => {
  await resetGrid();
  const search = await win.browser.$(`${PAGE} .ledger-search`);
  await search.setValue(SYNTHETIC);
  await waitFor(
    async () => {
      const now = await ledger();
      return now.rows.length > 0 && now.rows.every((row) => row.synthetic);
    },
    { timeout: 20_000, what: "only synthetic movements shown" },
  );
  const box = await win.browser.$(
    `${PAGE} input[type="checkbox"][aria-label="${label("desktop.ledger.select.shown")}"]`,
  );
  await box.click();
  await waitFor(
    async () =>
      (await ledger()).count.includes(
        words("desktop.ledger.selected", { count: extra.count }),
      ),
    { timeout: 20_000, what: `${extra.count} selected` },
  );
  await ensurePanel();
  const field = await win.browser.$(
    'aside.ledger-panel .ledger-selection input[id$="-counterparty"]',
  );
  await field.setValue(CONTACT);
  const stage = await win.browser.$(
    'aside.ledger-panel .ledger-selection form:has(input[id$="-counterparty"]) button[type="submit"]',
  );
  await stage.click();
  await shownWithin(".ledger-tray", "the tray", 20_000);
  const preview = await reviewAndPreview();
  const previewShot = await shot("lbe-04-preview");
  const saved = await saveAndWait();
  const savedShot = await shot("lbe-04-saved");
  await done();
  record({
    case: "LBE-04",
    rows: extra.count,
    preview,
    saved,
    screenshots: [previewShot, savedShot],
  });
  assert.equal(
    preview.counts,
    words("desktop.ledger.batch.count.applied", { count: extra.count }),
  );
  assert.equal(saved.host.calls, 1, "Save did not write one batch");
  assert.equal(
    saved.written,
    words("desktop.ledger.batch.written.applied", { count: extra.count }),
  );
});

test("LBE-05 properties copied from one movement are pasted onto a selection, and a refused row shows its cause", async () => {
  await resetGrid();
  const rows = await allRows();
  const source = rows.find(
    (row) => !row.synthetic && row.category && row.category !== label(CATEGORY),
  );
  assert(source, "no classified persona movement to copy from");
  const persona = rows
    .filter(
      (row) =>
        !row.synthetic &&
        row.key !== source.key &&
        row.category !== source.category,
    )
    .slice(0, 2);
  const synthetic = rows.filter((row) => row.synthetic).slice(0, 3);
  assert(
    persona.length === 2 && synthetic.length === 3,
    "too few targets shown",
  );

  await pressOrFail("[data-column=status]", "the source row", source.key);
  await ensurePanel();
  await pressOrFail(
    `aside.ledger-panel button[aria-label="${label("desktop.ledger.inspector.actions")}"]`,
    "the movement's actions",
  );
  await shownWithin('[role="menu"]', "the movement's actions menu", 10_000);
  assert(
    await clickText('[role="menu"]', '[role="menuitem"]', [
      `${label("desktop.ledger.properties.copy_open")}…`,
    ]),
    "no Copy properties… in the movement's actions",
  );
  await shownWithin(".ledger-copy-properties", "the copy dialog", 10_000);
  await exec(() => {
    for (const box of document.querySelectorAll(
      ".ledger-copy-properties [data-copy-field]",
    )) {
      const want = box.getAttribute("data-copy-field") === "category_id";
      const on =
        box.getAttribute("aria-checked") === "true" ||
        box.getAttribute("data-state") === "checked" ||
        box.checked === true;
      if (want !== on) box.click();
    }
  });
  await pressOrFail(
    ".ledger-copy-properties .ledger-copy-properties-copy",
    "Copy",
  );
  await waitFor(
    async () => !(await exec(pageShown, ".ledger-copy-properties")),
    {
      timeout: 10_000,
      what: "the copy dialog to close",
    },
  );

  const targets = [...persona, ...synthetic].map((row) => row.key);
  await selectKeys(targets);
  const since = Date.now();
  await pressOrFail(
    "aside.ledger-panel .ledger-paste-properties-open",
    "Paste properties",
  );
  await shownWithin(
    ".ledger-paste-properties .ledger-batch-counts",
    "the paste preview",
  );
  const preview = {
    window_ms: Date.now() - since,
    host: await hostMs(since, PREVIEW),
    counts: await exec(
      pageText,
      ".ledger-paste-properties .ledger-batch-counts",
    ),
    unwritten: await exec(pageUnwritten, ".ledger-paste-properties"),
    value: await exec(
      pageText,
      ".ledger-paste-properties [data-paste-field=category_id]",
    ),
  };
  const previewShot = await shot("lbe-05-paste-preview");
  await pressOrFail(
    ".ledger-paste-properties .ledger-paste-properties-paste",
    "Paste",
  );
  await waitFor(
    async () => !(await exec(pageShown, ".ledger-paste-properties")),
    {
      timeout: 10_000,
      what: "the paste dialog to close",
    },
  );
  const staged = [];
  for (const key of targets) {
    await reveal(key);
    staged.push(
      await exec(
        (key) =>
          !!document.querySelector(
            `section.ledger-page [data-kind="data"][data-key="${CSS.escape(key)}"] [data-column=category] [data-staged]`,
          ),
        key,
      ),
    );
  }
  const stagedShot = await shot("lbe-05-pasted");
  record({
    case: "LBE-05",
    source: source.category,
    targets: targets.length,
    preview,
    staged,
    screenshots: [previewShot, stagedShot],
  });
  assert(
    preview.value?.includes(source.category),
    "the paste does not show the copied category",
  );
  const refused = preview.unwritten.filter((row) => row.outcome === "refused");
  assert(
    refused.length > 0,
    `no refused row in the paste preview: ${preview.counts}`,
  );
  assert(
    refused.every((row) => row.cause && row.text.length > 0),
    "a refused row has no cause shown",
  );
  assert(
    staged.slice(0, persona.length).every(Boolean),
    "a persona movement the preview accepted was not staged",
  );
  await escape();
});
