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
