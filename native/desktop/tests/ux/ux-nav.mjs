// Navigation helpers shared by the specs (built on ux-driver.mjs).
import { existsSync } from "node:fs";
import { join } from "node:path";
import { queuePickerSelection } from "../automation/session.mjs";
import {
  win,
  exec,
  label,
  sleep,
  waitFor,
  clickText,
  clickSelector,
} from "./ux-driver.mjs";

// ---------------------------------------------------------------------------
// Navigation helpers shared by the specs
// ---------------------------------------------------------------------------

export const tablist = (key) =>
  `[role="tablist"][aria-label=${JSON.stringify(label(key))}]`;

/** Dismiss the first-run setup dialog with its own "not now". */
export async function dismissSetup() {
  const shown = await exec(() =>
    [...document.querySelectorAll('[role="dialog"]')].some(
      (d) => d.getClientRects().length > 0,
    ),
  );
  if (!shown) return false;
  const done = await clickText('[role="dialog"]', "button", [
    label("desktop.setup.not_now"),
    label("desktop.setup.close"),
  ]);
  await sleep(600);
  return done;
}

/** Press a rail button by its id. */
export async function rail(id) {
  await clickSelector(`[data-rail="${id}"]`);
  await sleep(1500);
}

/** Show the declarations list (rail, then wait for its grid). */
export async function showList() {
  await dismissSetup();
  const ready = () =>
    exec(() => {
      const g = [...document.querySelectorAll('[role="grid"]')].find(
        (x) => x.getClientRects().length > 0,
      );
      return (
        !!g &&
        !document.querySelector(".declarations-loading") &&
        g.querySelectorAll('[data-slot="data-grid-row"][data-kind="data"]')
          .length > 0
      );
    });
  if (await ready()) return;
  const pressed = await exec(() =>
    document
      .querySelector('[data-rail="declarations"]')
      ?.getAttribute("aria-pressed"),
  );
  if (pressed !== "true") await rail("declarations");
  // The rail restores the declaration left open, not the list; its overview
  // destination returns to the list.
  const overview = label("workspace.declarations.destination.overview");
  await waitFor(
    async () => {
      if (await ready()) return true;
      await clickText("section.declarations-workspace header", "button", [
        overview,
      ]);
      return false;
    },
    { timeout: 120_000, what: "the declarations list" },
  );
}

/** Open the declaration of `row` (a world row) with the list's double click. */
export async function openDeclaration(row) {
  await showList();
  const search = await win.browser.$("input.declarations-search");
  await search.waitForExist({ timeout: 15_000 });
  await search.setValue(row.modelo);
  await clickText(
    ".declarations-view",
    '[data-slot="segmented-control-item"]',
    [label("workspace.declarations.list.filter.all")],
    "startsWith",
  );
  const key = await waitFor(
    () =>
      exec(
        (id, modelo, year) => {
          const rows = [
            ...document.querySelectorAll(
              '[role="row"][data-slot="data-grid-row"][data-kind="data"]',
            ),
          ];
          const exact = rows.find((r) => r.getAttribute("data-key") === id);
          if (exact) return exact.getAttribute("data-key");
          const near = rows.filter(
            (r) =>
              (
                r.querySelector('[data-column="modelo"]')?.textContent ?? ""
              ).trim() === modelo && r.textContent.includes(year),
          );
          return near.length >= 1 ? near[0].getAttribute("data-key") : null;
        },
        String(row.work_unit_id),
        row.modelo,
        String(row.year),
      ),
    { timeout: 30_000, what: `list row ${row.modelo}` },
  );
  await exec((k) => {
    const r = document.querySelector(
      `[role="row"][data-slot="data-grid-row"][data-key="${CSS.escape(k)}"]`,
    );
    const cell = r?.querySelector('[data-column="declaration"]') ?? r;
    cell.dispatchEvent(
      new MouseEvent("dblclick", {
        bubbles: true,
        cancelable: true,
        view: window,
        detail: 2,
      }),
    );
  }, key);
  await waitFor(
    () =>
      exec((sel) => {
        const n = document.querySelector(sel);
        return !!n && n.getClientRects().length > 0;
      }, tablist("desktop.modelo.views.label")),
    { timeout: 120_000, what: "the declaration workspace" },
  );
  await sleep(2500);
}

/** Choose a Modelo view tab by its label key. */
export async function openView(key) {
  const ok = await clickText(
    tablist("desktop.modelo.views.label"),
    '[role="tab"]',
    [label(key)],
    "startsWith",
  );
  if (!ok) throw new Error(`the view ${label(key)} is not offered`);
  await sleep(700);
}

/** Choose the tab whose text starts with `text` as a press does (Radix tabs
 * choose on mouse down; a WebDriver click did not change the page). */
export async function chooseTab(scope, text) {
  const chosen = await exec(
    (scope, text) => {
      const list = [...document.querySelectorAll(scope)].find(
        (l) => l.getClientRects().length,
      );
      const tab = [...(list?.querySelectorAll('[role="tab"]') ?? [])].find(
        (t) =>
          t.getClientRects().length &&
          (t.textContent ?? "").replace(/\s+/g, " ").trim().startsWith(text),
      );
      if (!tab) return null;
      tab.dispatchEvent(
        new MouseEvent("mousedown", {
          bubbles: true,
          cancelable: true,
          button: 0,
        }),
      );
      tab.focus();
      return tab.getAttribute("aria-selected");
    },
    scope,
    text,
  );
  await sleep(1200);
  if (chosen === null) return null;
  // The state is read after React has rendered the press, not in the same
  // script that dispatched it.
  return exec(
    (scope, text) => {
      const list = [...document.querySelectorAll(scope)].find(
        (l) => l.getClientRects().length,
      );
      const tab = [...(list?.querySelectorAll('[role="tab"]') ?? [])].find(
        (t) =>
          t.getClientRects().length &&
          (t.textContent ?? "").replace(/\s+/g, " ").trim().startsWith(text),
      );
      return tab ? tab.getAttribute("aria-selected") : null;
    },
    scope,
    text,
  );
}

/**
 * Open a rail page by its rail id and wait for its root. `attr` is the rail
 * button's state attribute (aria-pressed for pages, aria-expanded for the
 * popover). Answers { reached, reason }; it never throws for a missing page.
 */
export async function openRailPage(id, rootSel, attr = "aria-pressed") {
  await dismissSetup();
  const rootShown = () =>
    exec(
      (sel) =>
        [...document.querySelectorAll(sel)].some(
          (e) => e.getClientRects().length > 0,
        ),
      rootSel,
    );
  const state = await exec(
    (id, attr) => {
      const button = document.querySelector(`[data-rail="${id}"]`);
      if (!button || !button.getClientRects().length) return { offered: false };
      return {
        offered: true,
        disabled: button.getAttribute("aria-disabled") === "true",
        on: button.getAttribute(attr) === "true",
      };
    },
    id,
    attr,
  );
  if (!state.offered)
    return { reached: false, reason: `no shown rail button [data-rail=${id}]` };
  if (state.disabled)
    return {
      reached: false,
      reason: `rail button ${id} is held (aria-disabled)`,
    };
  if (!state.on || !(await rootShown())) {
    try {
      await rail(id);
    } catch (error) {
      return {
        reached: false,
        reason: `pressing rail ${id} failed: ${error.message}`,
      };
    }
  }
  const root = await waitFor(rootShown, {
    timeout: 20_000,
    what: `page ${rootSel}`,
    soft: true,
  });
  return root
    ? { reached: true }
    : {
        reached: false,
        reason: `${rootSel} not shown after pressing rail ${id}`,
      };
}

/** Close the settings popover with Escape. */
export async function closeSettings() {
  await win.browser.keys("Escape");
  await sleep(600);
}

/**
 * Choose a Ledger section by its id: a tab for the tabbed sections, the setup
 * menu for the others. Answers { reached, reason }.
 */
export async function openLedgerSection(id, setup) {
  const name = label(`desktop.ledger.section.${id}`);
  if (!setup) {
    const chosen = await chooseTab(tablist("desktop.ledger.sections"), name);
    return chosen === "true"
      ? { reached: true }
      : {
          reached: false,
          reason:
            chosen === null ? `no tab "${name}"` : `tab "${name}" not selected`,
        };
  }
  // The setup menu is a Radix dropdown: it opens on pointerdown, which the
  // WebDriver click does not send, and selects an item on click. A menu still
  // closing from the last pick swallows the press, so the open is judged by the
  // expanded button and a shown menu, and tried once more when the item is not
  // there.
  const open = () =>
    exec(() => {
      const button = [...document.querySelectorAll("button.ledger-setup")].find(
        (b) => b.getClientRects().length,
      );
      if (!button) return false;
      if (button.getAttribute("aria-expanded") !== "true")
        button.dispatchEvent(
          new PointerEvent("pointerdown", {
            bubbles: true,
            cancelable: true,
            button: 0,
            pointerType: "mouse",
          }),
        );
      return true;
    });
  const shown = () =>
    waitFor(
      () =>
        exec(
          () =>
            [...document.querySelectorAll("button.ledger-setup")].some(
              (b) =>
                b.getClientRects().length &&
                b.getAttribute("aria-expanded") === "true",
            ) &&
            [...document.querySelectorAll('[role="menu"]')].some(
              (m) => m.getClientRects().length,
            ),
        ),
      {
        timeout: 3000,
        what: "the setup menu to open",
        soft: true,
        interval: 100,
      },
    );
  const pick = () =>
    exec((name) => {
      const item = [
        ...document.querySelectorAll('[role="menu"] [role="menuitem"]'),
      ].find(
        (e) =>
          e.getClientRects().length &&
          (e.textContent ?? "").replace(/\s+/g, " ").trim().startsWith(name),
      );
      if (!item) return false;
      item.click();
      return true;
    }, name);
  let picked = false;
  for (let attempt = 0; attempt < 2 && !picked; attempt += 1) {
    if (attempt > 0) {
      await win.browser.keys("Escape");
      await sleep(300);
    }
    if (!(await open()))
      return { reached: false, reason: "no setup menu button" };
    if (!(await shown())) continue;
    picked = await pick();
  }
  if (!picked) {
    await win.browser.keys("Escape");
    return { reached: false, reason: `no setup menu item "${name}"` };
  }
  await sleep(1200);
  const now = await exec(
    (name) =>
      (document.querySelector("button.ledger-setup")?.textContent ?? "")
        .replace(/\s+/g, " ")
        .trim()
        .startsWith(name),
    name,
  );
  return now
    ? { reached: true }
    : { reached: false, reason: `setup button does not show "${name}"` };
}

const LEDGER_DATA_ROWS =
  'section.ledger-page [role="grid"] [role="row"][data-kind="data"]';

/** How many elements the selector matches that the page draws. */
function pageShownCount(selector) {
  return [...document.querySelectorAll(selector)].filter(
    (el) => el.getClientRects().length > 0,
  ).length;
}

/**
 * Press the first drawn match as a pointer does. The period menu is a Radix
 * popover, which the WebDriver click does not always open.
 */
function pagePointerPress(selector) {
  const el = [...document.querySelectorAll(selector)].find(
    (e) => e.getClientRects().length > 0,
  );
  if (!el) return false;
  const at = el.getBoundingClientRect();
  const base = {
    bubbles: true,
    cancelable: true,
    composed: true,
    button: 0,
    clientX: at.left + at.width / 2,
    clientY: at.top + at.height / 2,
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
 * Show the Ledger movements of every period. The Libro opens on the current
 * quarter, and a world's movements can lie in an earlier year, so a grid read
 * before this step can be empty without the world being so. Waits for drawn
 * data rows; answers { reached, reason, rows, empty }, where empty is true
 * when the period was chosen and the grid still drew no data row.
 */
export async function openAllPeriods({ timeout = 60_000 } = {}) {
  const item = ".ledger-period-menu .ledger-period-all";
  if (!(await exec(pagePointerPress, "button.ledger-period")))
    return { reached: false, reason: "no period choice is shown", rows: 0 };
  const offered = await waitFor(() => exec(pageShownCount, item), {
    timeout: 10_000,
    what: "the All periods item",
    soft: true,
  });
  if (!offered)
    return {
      reached: false,
      reason: "the period menu did not offer All periods",
      rows: 0,
    };
  await exec(pagePointerPress, item);
  const closed = await waitFor(
    async () => (await exec(pageShownCount, ".ledger-period-menu")) === 0,
    { timeout: 10_000, what: "the period menu to close", soft: true },
  );
  if (!closed)
    return {
      reached: false,
      reason: "the period menu stayed open after All periods",
      rows: 0,
    };
  const rows = await waitFor(() => exec(pageShownCount, LEDGER_DATA_ROWS), {
    timeout,
    what: "movements in the grid",
    soft: true,
  });
  return rows
    ? { reached: true, rows }
    : {
        reached: false,
        reason: `no data row was drawn within ${timeout} ms of choosing All periods`,
        rows: 0,
        empty: true,
      };
}

/** Which page the window shows now: the roots drawn and the rail buttons pressed. */
export function pageNow() {
  const drawn = (sel) =>
    [...document.querySelectorAll(sel)].some(
      (e) => e.getClientRects().length > 0,
    );
  return {
    ledger: drawn("section.ledger-page"),
    profile: drawn("section.user-profile-page"),
    aeatSync: drawn("section.aeat-sync-page"),
    declarations: drawn("section.declarations-workspace"),
    pressed: [
      ...document.querySelectorAll('[data-rail][aria-pressed="true"]'),
    ].map((b) => b.getAttribute("data-rail")),
  };
}

/** The pressed state of a Modelo workspace pane toggle ("side", "details" or
 * "placement"): "true", "false", or null when the toggle is not drawn. */
export const paneToggleState = (pane) =>
  exec(
    (pane) =>
      document
        .querySelector(
          `section.declarations-workspace [data-pane-toggle="${pane}"]`,
        )
        ?.getAttribute("aria-pressed") ?? null,
    pane,
  );

/** Press a Modelo workspace pane toggle until it is `on`. Answers the state
 * it reached: "true", "false", or null when the toggle is not drawn. */
export async function setPaneToggle(pane, on) {
  let state = await paneToggleState(pane);
  if (state === null || state === String(on)) return state;
  await clickSelector(
    `section.declarations-workspace [data-pane-toggle="${pane}"]`,
  );
  await sleep(700);
  state = await paneToggleState(pane);
  return state;
}

/**
 * Every scroll container inside the shown `rootSel` (the root included): an
 * element whose overflow-y is auto or scroll, or that overflows its box with
 * overflow-y not visible. Each one is tagged `data-ux-scroll=<n>` so later
 * calls can find it again. Answers the numbers behind each container's
 * overflow and scrollbar; it judges nothing.
 */
export function pageScrollContainers(rootSel) {
  for (const old of document.querySelectorAll("[data-ux-scroll]"))
    old.removeAttribute("data-ux-scroll");
  const root = [...document.querySelectorAll(rootSel)].find(
    (e) => e.getClientRects().length > 0,
  );
  if (!root) return { found: false, containers: [] };
  const px = (value) => parseFloat(value) || 0;
  const describe = (el) => {
    const data = [...el.attributes]
      .filter((a) => a.name.startsWith("data-") && a.name !== "data-ux-scroll")
      .slice(0, 2)
      .map((a) => `[${a.name}${a.value ? `=${a.value.slice(0, 24)}` : ""}]`)
      .join("");
    const aria = el.getAttribute("aria-label");
    const cls =
      typeof el.className === "string" && el.className
        ? "." + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join(".")
        : "";
    return `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${cls}${data}${
      aria ? `[aria-label=${aria.slice(0, 30)}]` : ""
    }`;
  };
  const containers = [];
  for (const el of [root, ...root.querySelectorAll("*")]) {
    if (!el.getClientRects().length || el.clientHeight <= 2) continue;
    const cs = getComputedStyle(el);
    // The visually-hidden clip pattern is not a scroller a person can use.
    if (cs.position === "absolute" && px(cs.width) <= 1 && px(cs.height) <= 1)
      continue;
    const scrolling = cs.overflowY === "auto" || cs.overflowY === "scroll";
    const overflows = el.scrollHeight > el.clientHeight + 1;
    if (!scrolling && !(overflows && cs.overflowY !== "visible")) continue;
    const id = String(containers.length);
    el.setAttribute("data-ux-scroll", id);
    const classicWidth = Math.round(
      el.offsetWidth -
        el.clientWidth -
        px(cs.borderLeftWidth) -
        px(cs.borderRightWidth),
    );
    const bar = getComputedStyle(el, "::-webkit-scrollbar");
    containers.push({
      id,
      el: describe(el),
      overflowY: cs.overflowY,
      scrollable: scrolling,
      overflows,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      scrollTop: el.scrollTop,
      classicWidth,
      scrollbarWidth: cs.scrollbarWidth ?? null,
      webkitDisplay: bar.display,
      webkitWidth: bar.width,
      barVisible: classicWidth > 0,
    });
    if (containers.length >= 40) break;
  }
  return { found: true, containers };
}

/**
 * Add (`on`) or remove a scroller that is not the app's: a fixed 240x240 box
 * with 4000px of content, tagged `data-ux-scroll="control"`. A wheel that
 * moves it shows the WebDriver wheel reaches the page, so an app scroller the
 * same wheel leaves still is the app's defect, not the harness's.
 */
export function pageWheelControl(on) {
  document.querySelector('[data-ux-scroll="control"]')?.remove();
  if (!on) return true;
  const box = document.createElement("div");
  box.setAttribute("data-ux-scroll", "control");
  box.style.cssText =
    "position:fixed;left:40%;top:30%;width:240px;height:240px;" +
    "overflow-y:auto;z-index:2147483647;background:#fff";
  const inner = document.createElement("div");
  inner.style.height = "4000px";
  box.append(inner);
  document.body.append(box);
  return true;
}

/** Why a ledger section could not be chosen: dialogs, menus, what covers its tabs. */
export function pageLedgerBlocker() {
  const shown = (el) => el.getClientRects().length > 0;
  const name = (el) =>
    `${el.tagName.toLowerCase()}${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""}` +
    `${el.getAttribute("aria-label") ? `[aria-label=${el.getAttribute("aria-label").slice(0, 40)}]` : ""}` +
    `${typeof el.className === "string" && el.className ? "." + el.className.split(/\s+/).slice(0, 2).join(".") : ""}`;
  const overlays = [
    ...document.querySelectorAll(
      '[role="dialog"],[role="alertdialog"],[role="menu"],[data-state="open"]',
    ),
  ]
    .filter(shown)
    .map(name)
    .slice(0, 6);
  const tab = document.querySelector('.ledger-page [role="tab"]');
  let atTab = null;
  if (tab) {
    const b = tab.getBoundingClientRect();
    const hit = document.elementFromPoint(
      b.left + b.width / 2,
      b.top + b.height / 2,
    );
    atTab = hit ? `${name(hit)}${tab.contains(hit) ? " (the tab)" : ""}` : null;
  }
  return {
    overlays,
    atTab,
    ledgerShown:
      !!document.querySelector("section.ledger-page") &&
      shown(document.querySelector("section.ledger-page")),
    focused: document.activeElement ? name(document.activeElement) : null,
  };
}

/** Where to put a wheel over container `id`, and its scrollTop before. */
export function pageWheelTarget(id) {
  const el = document.querySelector(`[data-ux-scroll="${id}"]`);
  if (!el) return null;
  const box = () => {
    const b = el.getBoundingClientRect();
    return {
      left: Math.max(0, b.left),
      top: Math.max(0, b.top),
      right: Math.min(innerWidth, b.right),
      bottom: Math.min(innerHeight, b.bottom),
    };
  };
  let b = box();
  if (b.right - b.left < 4 || b.bottom - b.top < 4) {
    el.scrollIntoView({ block: "nearest" });
    b = box();
  }
  // The wheel scrolls the innermost scroller under the pointer first, so the
  // point must lie where no nested scroller with room to move covers el.
  const nestedScroller = (hit) => {
    for (let node = hit; node && node !== el; node = node.parentElement)
      if (
        /auto|scroll/.test(getComputedStyle(node).overflowY) &&
        node.scrollHeight > node.clientHeight + 1
      )
        return true;
    return false;
  };
  let x = Math.floor((b.left + b.right) / 2);
  let y = Math.floor((b.top + b.bottom) / 2);
  let hit = document.elementFromPoint(x, y);
  let nestedOnly = false;
  if (hit && el.contains(hit) && nestedScroller(hit)) {
    nestedOnly = true;
    search: for (let i = 1; i < 8; i += 1)
      for (let j = 1; j < 8; j += 1) {
        const px = Math.floor(b.left + ((b.right - b.left) * i) / 8);
        const py = Math.floor(b.top + ((b.bottom - b.top) * j) / 8);
        const at = document.elementFromPoint(px, py);
        if (at && el.contains(at) && !nestedScroller(at)) {
          [x, y, hit, nestedOnly] = [px, py, at, false];
          break search;
        }
      }
  }
  const max = el.scrollHeight - el.clientHeight;
  return {
    x,
    y,
    nestedOnly,
    before: el.scrollTop,
    // A container already at its end is wheeled the other way.
    direction: el.scrollTop >= max - 1 ? -1 : 1,
    pointInside: !!hit && el.contains(hit),
    pointInWindow: b.right - b.left >= 4 && b.bottom - b.top >= 4,
  };
}

/** scrollTop of container `id` now; restores it to `restore` when given. */
export function pageWheelResult(id, restore) {
  const el = document.querySelector(`[data-ux-scroll="${id}"]`);
  if (!el) return null;
  const after = el.scrollTop;
  if (restore !== undefined) el.scrollTop = restore;
  return after;
}

/**
 * Wheel over the centre of container `id` and answer whether its scrollTop
 * moved. The wheel is the trusted Chromium DevTools one when the run attached
 * it (CADRUMO_UX_DEVTOOLS=1, source "devtools"), else a WebDriver action
 * (source "webdriver", an untrusted synthetic event). The scrollTop is
 * restored afterwards.
 */
export async function wheelContainer(id, deltaY = 300) {
  const target = await exec(pageWheelTarget, id);
  if (!target) return { moved: false, error: "container gone" };
  const trusted = win.devtools?.trustedWheel;
  const source = trusted ? "devtools" : "webdriver";
  if (!target.pointInWindow)
    return {
      ...target,
      source,
      moved: false,
      error: "container not inside window",
    };
  if (target.nestedOnly)
    return {
      ...target,
      source,
      moved: false,
      unmeasured: true,
      error: "every point over the container lies over a nested scroller",
    };
  let error = null;
  try {
    if (trusted) await trusted(target.x, target.y, deltaY * target.direction);
    else
      await win.browser
        .action("wheel")
        .scroll({
          x: target.x,
          y: target.y,
          deltaX: 0,
          deltaY: deltaY * target.direction,
          duration: 100,
        })
        .perform();
  } catch (failure) {
    error = `wheel (${source}) failed: ${failure.message}`;
  }
  await sleep(400);
  const after = await exec(pageWheelResult, id, target.before);
  return { ...target, source, after, moved: after !== target.before, error };
}

/**
 * Queue the answer of the window's next native save picker: `destination`
 * must lie under the run's exports directory and not exist yet. The window
 * consumes the answer when it asks.
 */
export function queueSavePicker(run, destination) {
  return queuePickerSelection(run, "save", destination);
}

/** Whether a queued picker answer is still waiting to be taken by the window. */
export const pickerAnswerPending = (run) =>
  existsSync(join(run, "temporary", "native-picker-selection.json"));

/** The shown tabs of the first shown tablist matching `scope`, with their state. */
export function pageTabs(scope) {
  const list = [...document.querySelectorAll(scope)].find(
    (l) => l.getClientRects().length > 0,
  );
  const tabs = [...(list?.querySelectorAll('[role="tab"]') ?? [])]
    .filter((t) => t.getClientRects().length > 0)
    .map((t) => ({
      text: (t.textContent ?? "").replace(/\s+/g, " ").trim(),
      selected: t.getAttribute("aria-selected") === "true",
    }));
  return { found: !!list, tabs };
}

/**
 * Where a pointer press on shown tab `index` of the tablist `scope` lands: the
 * tab's centre in viewport pixels, and what the page draws at that point.
 */
export function pageTabCentre(scope, index) {
  const list = [...document.querySelectorAll(scope)].find(
    (l) => l.getClientRects().length > 0,
  );
  const tab = [...(list?.querySelectorAll('[role="tab"]') ?? [])].filter(
    (t) => t.getClientRects().length > 0,
  )[index];
  if (!tab) return null;
  tab.scrollIntoView({ block: "nearest", inline: "nearest" });
  const b = tab.getBoundingClientRect();
  const x = Math.round(b.left + b.width / 2);
  const y = Math.round(b.top + b.height / 2);
  const inWindow = x >= 0 && y >= 0 && x < innerWidth && y < innerHeight;
  const hit = inWindow ? document.elementFromPoint(x, y) : null;
  const describe = (el) =>
    `${el.tagName.toLowerCase()}` +
    `${el.getAttribute("role") ? `[role=${el.getAttribute("role")}]` : ""}` +
    `${typeof el.className === "string" && el.className ? "." + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join(".") : ""}`;
  return {
    x,
    y,
    rect: [b.left, b.top, b.right, b.bottom].map(Math.round),
    inWindow,
    hit: hit ? describe(hit) : null,
    hitIsTab: !!hit && tab.contains(hit),
    hitInsideTablist: !!hit && !!list && list.contains(hit),
  };
}

/** aria-selected of shown tab `index` of the tablist `scope` now, or null. */
export function pageTabSelectedAt(scope, index) {
  const list = [...document.querySelectorAll(scope)].find(
    (l) => l.getClientRects().length > 0,
  );
  const tab = [...(list?.querySelectorAll('[role="tab"]') ?? [])].filter(
    (t) => t.getClientRects().length > 0,
  )[index];
  return tab ? tab.getAttribute("aria-selected") : null;
}

/** One real pointer press and release at viewport point (x, y), as WebDriver actions. */
export async function pointerClickAt(x, y) {
  try {
    await win.browser
      .action("pointer", { parameters: { pointerType: "mouse" } })
      .move({ x, y, origin: "viewport" })
      .down()
      .up()
      .perform();
  } finally {
    await win.browser.releaseActions().catch(() => {});
  }
}
