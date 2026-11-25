import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// An activation that sends only a click, as UI Automation's Invoke or a
// screen reader's default action does, without a pointer press, a key or the
// focus before it, works the period picker, a menu button and a tab as a
// person's press does.

/** A click and nothing before it: no pointer or mouse press, no key, and
 * nothing focused in the page. */
async function clickOnly(control: Locator) {
  await control.evaluate((element) => {
    (document.activeElement as HTMLElement | null)?.blur();
    (element as HTMLElement).click();
  });
}

const head = (page: Page) => page.locator(".pane-docs .pane-head");

test.beforeEach(async ({ page }) => {
  await page.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await page.locator("[data-rail=ledger]").click();
  await expect(page.locator(".ledger-page").getByRole("grid")).toBeVisible();
});

test("a click alone opens the period picker and chooses a period", async ({
  page,
}) => {
  const trigger = head(page).locator(".ledger-period");
  const periods = page.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  await clickOnly(trigger);
  await expect(periods).toBeVisible();
  const all = periods.locator(".ledger-period-all");
  await clickOnly(all);
  await expect(periods).toBeHidden();
  await expect(trigger).toHaveAccessibleName(
    label("desktop.ledger.period.named", {
      label: label("desktop.ledger.period.label"),
      period: label("desktop.ledger.period.all"),
    }),
  );
});

test("a click alone opens and closes a menu button, and a press or a key opens it once", async ({
  page,
}) => {
  // By its label rather than its role: an open menu hides the rest of the
  // window from assistive technology.
  const trigger = page.locator(
    `[data-dock-header="docs"] button[aria-label="${label("desktop.dock.arrange")}"]`,
  );
  const menu = page.getByRole("menu");
  await clickOnly(trigger);
  await expect(menu).toBeVisible();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await clickOnly(trigger);
  await expect(menu).toBeHidden();
  // A pointer press opens it once: the click that follows does not close it.
  await trigger.click();
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  for (const key of ["Enter", " "]) {
    await trigger.focus();
    await page.keyboard.press(key);
    await expect(menu).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu).toBeHidden();
  }
  // A key the menu answered leaves no click behind it, so the next bare
  // click still opens the menu.
  await clickOnly(trigger);
  await expect(menu).toBeVisible();
});

test("a click alone chooses a tab, and a press or Enter still does", async ({
  page,
}) => {
  const sections = page.getByRole("tablist", {
    name: label("desktop.ledger.sections"),
  });
  const tab = (key: string) =>
    sections.getByRole("tab", {
      name: label(`desktop.ledger.section.${key}`),
      exact: true,
    });
  await clickOnly(tab("invoices"));
  await expect(tab("invoices")).toHaveAttribute("aria-selected", "true");
  await tab("assets").click();
  await expect(tab("assets")).toHaveAttribute("aria-selected", "true");
  await tab("documents").focus();
  await page.keyboard.press("Enter");
  await expect(tab("documents")).toHaveAttribute("aria-selected", "true");
});

test("a click alone opens and closes the background tasks", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&jobs=progress",
  );
  const trigger = page.locator(".background-tasks-trigger");
  const panel = page.locator(".background-tasks-panel");
  await expect(trigger).toBeVisible();
  await clickOnly(trigger);
  await expect(panel).toBeVisible();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await clickOnly(trigger);
  await expect(panel).toBeHidden();
});
