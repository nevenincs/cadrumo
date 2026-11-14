// Navigation helpers shared by the specs (built on ux-driver.mjs).
import { win, exec, label, sleep, waitFor, clickText, clickSelector } from "./ux-driver.mjs";

// ---------------------------------------------------------------------------
// Navigation helpers shared by the specs
// ---------------------------------------------------------------------------

export const tablist = (key) =>
  `[role="tablist"][aria-label=${JSON.stringify(label(key))}]`;

/** Dismiss the first-run setup dialog with its own "not now". */
export async function dismissSetup() {
  const shown = await exec(
    () =>
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
        g.querySelectorAll('[data-slot="data-grid-row"][data-kind="data"]').length > 0
      );
    });
  if (await ready()) return;
  const pressed = await exec(
    () => document.querySelector('[data-rail="declarations"]')?.getAttribute("aria-pressed"),
  );
  if (pressed !== "true") await rail("declarations");
  await waitFor(ready, { timeout: 120_000, what: "the declarations list" });
}

/** Open the declaration of `row` (a world row) with the list's double click. */
export async function openDeclaration(row) {
  await showList();
  const search = await win.browser.$("input.declarations-search");
  await search.waitForExist({ timeout: 15_000 });
  await search.setValue(row.modelo);
  await clickText(".declarations-view", '[data-slot="segmented-control-item"]', [
    label("workspace.declarations.list.filter.all"),
  ], "startsWith");
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
              (r.querySelector('[data-column="modelo"]')?.textContent ?? "").trim() === modelo &&
              r.textContent.includes(year),
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
      new MouseEvent("dblclick", { bubbles: true, cancelable: true, view: window, detail: 2 }),
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
  const ok = await clickText(tablist("desktop.modelo.views.label"), '[role="tab"]', [label(key)], "startsWith");
  if (!ok) throw new Error(`the view ${label(key)} is not offered`);
  await sleep(700);
}

/** Choose the tab whose text starts with `text` as a press does (Radix tabs
 * choose on mouse down; a WebDriver click did not change the page). */
export async function chooseTab(scope, text) {
  const chosen = await exec(
    (scope, text) => {
      const list = [...document.querySelectorAll(scope)].find((l) => l.getClientRects().length);
      const tab = [...(list?.querySelectorAll('[role="tab"]') ?? [])].find(
        (t) => t.getClientRects().length && (t.textContent ?? "").replace(/\s+/g, " ").trim().startsWith(text),
      );
      if (!tab) return null;
      tab.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, button: 0 }));
      tab.focus();
      return tab.getAttribute("aria-selected");
    },
    scope,
    text,
  );
  await sleep(1200);
  return chosen;
}

/**
 * Open a rail page by its rail id and wait for its root. `attr` is the rail
 * button's state attribute (aria-pressed for pages, aria-expanded for the
 * popover). Answers { reached, reason }; it never throws for a missing page.
 */
export async function openRailPage(id, rootSel, attr = "aria-pressed") {
  await dismissSetup();
  const rootShown = () =>
    exec((sel) => [...document.querySelectorAll(sel)].some((e) => e.getClientRects().length > 0), rootSel);
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
  if (!state.offered) return { reached: false, reason: `no shown rail button [data-rail=${id}]` };
  if (state.disabled) return { reached: false, reason: `rail button ${id} is held (aria-disabled)` };
  if (!state.on || !(await rootShown())) {
    try {
      await rail(id);
    } catch (error) {
      return { reached: false, reason: `pressing rail ${id} failed: ${error.message}` };
    }
  }
  const root = await waitFor(rootShown, { timeout: 20_000, what: `page ${rootSel}`, soft: true });
  return root ? { reached: true } : { reached: false, reason: `${rootSel} not shown after pressing rail ${id}` };
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
      : { reached: false, reason: chosen === null ? `no tab "${name}"` : `tab "${name}" not selected` };
  }
  const opened = await clickText(
    ".ledger-head",
    "button.ledger-setup",
    [label("desktop.ledger.setup"), ...setup.map((key) => label(`desktop.ledger.section.${key}`))],
  );
  if (!opened) return { reached: false, reason: "no setup menu button" };
  await sleep(500);
  const picked = await clickText('[role="menu"]', '[role="menuitem"]', [name], "startsWith");
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
  return now ? { reached: true } : { reached: false, reason: `setup button does not show "${name}"` };
}

/** Which page the window shows now: the roots drawn and the rail buttons pressed. */
export function pageNow() {
  const drawn = (sel) =>
    [...document.querySelectorAll(sel)].some((e) => e.getClientRects().length > 0);
  return {
    ledger: drawn("section.ledger-page"),
    profile: drawn("section.user-profile-page"),
    aeatSync: drawn("section.aeat-sync-page"),
    declarations: drawn("section.declarations-workspace"),
    pressed: [...document.querySelectorAll('[data-rail][aria-pressed="true"]')].map((b) =>
      b.getAttribute("data-rail"),
    ),
  };
}
