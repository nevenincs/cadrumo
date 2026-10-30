import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The Ledger page swept in whole: every area of the sections the other
// scenarios audit one part of is checked for accessibility violations in
// both schemes, and a walk by keyboard alone reaches each section's main
// actions and opens them. The sections' own scenarios hold the rest.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

const head = (target: Page) => target.locator(".pane-docs .pane-head");
const page = (target: Page) => target.locator(".ledger-page");

async function openLedger(target: Page, scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(page(target).getByRole("grid")).toBeVisible();
}

/** Opens a Setup section by the pointer, for the audit; the keyboard walk
 * does it by keys. */
async function openSetup(
  target: Page,
  section: "rules" | "registers" | "health",
) {
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", { name: label(`desktop.ledger.section.${section}`) })
    .click();
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  await expect(target.getByRole("menu")).toHaveCount(0);
}

async function area(target: Page, key: string) {
  await target.getByRole("tab", { name: label(key), exact: true }).click();
}

/** Axe over the whole window, once nothing is animating. */
async function audit(target: Page) {
  await target.evaluate(engine);
  await target.evaluate(async () => {
    for (let round = 0; round < 10; round += 1) {
      const running = document.documentElement
        .getAnimations({ subtree: true })
        .filter((animation) => animation.playState === "running");
      if (running.length === 0) return;
      await Promise.allSettled(running.map((animation) => animation.finished));
    }
  });
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      { exclude: [[".docs-frame"], [".xterm"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

for (const scheme of ["light", "dark"] as const)
  test(`every area of the Ledger page passes an accessibility audit in the ${scheme} scheme`, async ({
    page: target,
  }) => {
    await openLedger(target, scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    // The movements grid with its toolbar and readiness strip.
    expect(await audit(target)).toEqual([]);
    await openSetup(target, "rules");
    for (const name of ["rules", "ratios", "counterparties", "diagnostics"]) {
      await area(target, `desktop.ledger.rules.area.${name}`);
      expect(await audit(target), `rules ${name}`).toEqual([]);
    }
    await openSetup(target, "registers");
    for (const name of ["accounts", "prorrata", "capital"]) {
      await area(target, `desktop.ledger.registers.area.${name}`);
      expect(await audit(target), `registers ${name}`).toEqual([]);
    }
    await openSetup(target, "health");
    expect(await audit(target)).toEqual([]);
    await head(target)
      .getByRole("tab", { name: label("desktop.ledger.section.assets") })
      .click();
    for (const name of ["fixed", "stock"]) {
      await area(target, `desktop.ledger.assets.area.${name}`);
      expect(await audit(target), `assets ${name}`).toEqual([]);
    }
    for (const section of ["invoices", "documents"]) {
      await head(target)
        .getByRole("tab", { name: label(`desktop.ledger.section.${section}`) })
        .click();
      expect(await audit(target), section).toEqual([]);
    }
  });

/** What the focused element is called: its label, or its text. */
const focused = (target: Page) =>
  target.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    if (!element) return "";
    return (
      element.getAttribute("aria-label") ||
      element.textContent ||
      element.getAttribute("placeholder") ||
      ""
    ).trim();
  });

/** Presses Tab until the focus is on an element called `name`, within
 * `limit` presses, and returns the names passed on the way. */
async function tabTo(
  target: Page,
  name: string | RegExp,
  limit = 40,
): Promise<string[]> {
  const passed: string[] = [];
  const matches = (found: string) =>
    typeof name === "string" ? found === name : name.test(found);
  for (let at = 0; at < limit; at += 1) {
    await target.keyboard.press("Tab");
    // The focus lands after the key's own task.
    await target.evaluate(
      () => new Promise((done) => requestAnimationFrame(done)),
    );
    const found = await focused(target);
    passed.push(found);
    if (matches(found)) return passed;
  }
  expect(passed, `Tab never reached ${String(name)}`).toContain(String(name));
  return passed;
}

/** Whether the focus is inside the element matching `selector`. */
const focusIn = (target: Page, selector: string) =>
  target.evaluate(
    (within) => !!document.activeElement?.closest(within),
    selector,
  );

const selectedSection = (target: Page) =>
  head(target).getByRole("tab", { selected: true });

test("the Movements toolbar and its dialogs are reached and opened by keys alone", async ({
  page: target,
}) => {
  await openLedger(target);
  await head(target).locator(".ledger-period").focus();
  // The toolbar's actions come in order of the page, none skipped.
  for (const key of [
    "desktop.ledger.action.import",
    "desktop.ledger.action.export",
    "desktop.ledger.action.add_movement",
  ])
    await tabTo(target, label(key));
  await tabTo(target, label("desktop.ledger.search.label"));
  for (const key of [
    "desktop.ledger.filters.title",
    "desktop.ledger.group.title",
    "desktop.ledger.columns.title",
  ])
    await tabTo(target, new RegExp(`^${label(key)}`));
  // A grid cell takes the focus, and Escape leaves nothing open.
  await tabTo(target, "");
  expect(
    await target.evaluate(() => document.activeElement?.getAttribute("role")),
  ).toBe("gridcell");

  // Each dialog opens on Enter and closes on Escape.
  for (const [action, title] of [
    ["desktop.ledger.action.import", "desktop.ledger.import.title"],
    ["desktop.ledger.action.export", "desktop.ledger.export.title"],
  ] as const) {
    await head(target)
      .getByRole("button", { name: label(action), exact: true })
      .focus();
    await target.keyboard.press("Enter");
    const dialog = target.getByRole("dialog", { name: label(title) });
    await expect(dialog).toBeVisible();
    expect(await focusIn(target, "[role=dialog]")).toBe(true);
    await target.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  }

  // The filters open on Enter and close on Escape.
  await head(target).locator(".ledger-period").focus();
  await tabTo(target, new RegExp(`^${label("desktop.ledger.filters.title")}`));
  await target.keyboard.press("Enter");
  await expect(target.locator(".ledger-filters")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".ledger-filters")).toBeHidden();
});

test("the other sections are chosen by arrow keys and their actions reached by Tab", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=documents",
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(page(target).getByRole("grid")).toBeVisible();
  await selectedSection(target).focus();
  await target.keyboard.press("ArrowRight");
  await expect(
    head(target).getByRole("tab", {
      name: label("desktop.ledger.section.invoices"),
    }),
  ).toHaveAttribute("aria-selected", "true");
  for (const name of [
    label("desktop.ledger.invoices.action.add"),
    label("desktop.ledger.invoices.search"),
    label("desktop.ledger.invoices.class_filter"),
    label("desktop.ledger.invoices.payment_filter"),
  ])
    await tabTo(target, name);
  await tabTo(target, "PT-2026-0412");
  expect(
    await target.evaluate(() => document.activeElement?.getAttribute("role")),
  ).toBe("gridcell");

  await selectedSection(target).focus();
  await target.keyboard.press("ArrowRight");
  await expect(
    head(target).getByRole("tab", {
      name: label("desktop.ledger.section.documents"),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await tabTo(
    target,
    new RegExp(`^${label("desktop.ledger.documents.tab.review")}`),
  );
  await tabTo(target, label("desktop.ledger.documents.read_again"));
  await tabTo(target, label("desktop.ledger.documents.confirm"));
});

/** Opens a Setup section through the Setup menu by keys alone. */
async function setupByKeys(
  target: Page,
  section: "rules" | "registers" | "health",
) {
  await head(target).locator(".ledger-setup").focus();
  await target.keyboard.press("Enter");
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  // The menu opens on its first item; Arrow keys move through the rest.
  const items = ["rules", "registers", "health"] as const;
  const item = (name: string) =>
    menu.getByRole("menuitem", {
      name: label(`desktop.ledger.section.${name}`),
    });
  await expect(item("rules")).toBeFocused();
  for (let at = 1; at <= items.indexOf(section); at += 1) {
    await target.keyboard.press("ArrowDown");
    await expect(item(items[at]!)).toBeFocused();
  }
  await target.keyboard.press("Enter");
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  await expect(menu).toHaveCount(0);
}

test("Setup is opened by keys, and each area of its sections is chosen and entered by keys", async ({
  page: target,
}) => {
  await openLedger(target);
  const areas = [
    ["rules", 4, "desktop.ledger.rules.areas"],
    ["registers", 3, "desktop.ledger.registers.areas"],
  ] as const;
  for (const [section, count, group] of areas) {
    await setupByKeys(target, section);

    const tabs = target
      .getByRole("tablist", { name: label(group) })
      .getByRole("tab");
    await expect(tabs).toHaveCount(count);
    await tabs.first().focus();
    for (let at = 0; at < count; at += 1) {
      await expect(tabs.nth(at)).toHaveAttribute("aria-selected", "true");
      // From the area's tab, Tab enters its panel.
      await target.keyboard.press("Tab");
      await expect
        .poll(() => focusIn(target, `.ledger-setup-${section} [role=tabpanel]`))
        .toBe(true);
      await target.keyboard.press("Shift+Tab");
      await expect(tabs.nth(at)).toBeFocused();
      if (at < count - 1) await target.keyboard.press("ArrowRight");
    }
  }

  await setupByKeys(target, "health");
  await tabTo(target, label("desktop.ledger.health.run_check"));
  await tabTo(target, label("desktop.ledger.health.rebuild"));
  await tabTo(target, label("desktop.ledger.health.reset"));
});
