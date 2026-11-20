import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// A real browser keeps Ctrl+K for its own chrome and never hands it to the
// page, so the window's palette chord opens the palette with the embedded
// browser focused, while the keys a page does receive still reach it.
const surface = (page: Page) => page.locator("[data-browser-surface]");
const sink = (page: Page) => surface(page).locator("textarea");
const palette = (page: Page) =>
  page.getByRole("dialog", { name: label("desktop.palette.label") });
const inputs = (page: Page) =>
  page.evaluate(() => window.__scenarioSedeView?.inputs() ?? []);
const keyEvents = async (page: Page) =>
  (await inputs(page)).filter((event) => event.type === "key");

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.browser.title"), exact: true })
    .click();
  await expect(sink(page)).toBeEditable();
  await surface(page).focus();
  await expect(sink(page)).toBeFocused();
});

test("the palette chord opens the palette from the focused browser and the page never sees it", async ({
  page,
}) => {
  await page.keyboard.press("Control+KeyK");
  await expect(palette(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette(page)).toBeHidden();
  // A bare modifier is forwarded before any chord is known, since the page
  // needs modifiers (Ctrl+click); the K key and any text are never sent.
  const received = await inputs(page);
  expect(received.filter((event) => event.type === "text")).toEqual([]);
  expect(
    received.filter((event) => event.type === "key" && event.code === "KeyK"),
  ).toEqual([]);
});

test("the keys a page receives still reach it with the browser focused", async ({
  page,
}) => {
  await page.keyboard.press("Alt+ArrowLeft");
  await page.keyboard.press("KeyA");
  await expect(palette(page)).toBeHidden();
  await expect
    .poll(async () =>
      (await keyEvents(page)).map((event) => `${event.action}:${event.code}`),
    )
    .toEqual(
      expect.arrayContaining(["down:ArrowLeft", "down:KeyA", "up:KeyA"]),
    );
});
