import { expect, test } from "@playwright/test";
import { label } from "../support/strings";

test("dialog limits respond to the shared overlay gutter", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 700 });
  await page.goto("/scenarios.html?scenario=signed-out&latency=0&bar=off");
  const dialog = page.locator(".sign-in");
  await expect(dialog).toBeVisible();
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--overlay-gutter", "200px"),
  );
  await expect
    .poll(async () => (await dialog.boundingBox())?.width)
    .toBeCloseTo(200, 0);
});

test("log column widths follow their shared token", async ({ page }) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const grid = page.locator(".log-record-grid").first();
  await expect(grid).toBeVisible();
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--log-time-width", "11em"),
  );
  const measured = await grid.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      first: parseFloat(style.gridTemplateColumns),
      type: parseFloat(style.fontSize),
    };
  });
  expect(measured.first).toBeCloseTo(11 * measured.type, 1);
});

test("calendar month packing follows the shared minimum", async ({ page }) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await page.keyboard.press("Control+Shift+D");
  const months = page.locator(".calendar-months");
  await expect(months).toBeVisible();
  const tracks = () =>
    months.evaluate(
      (element) =>
        getComputedStyle(element).gridTemplateColumns.split(" ").length,
    );
  const before = await tracks();
  expect(before).toBeGreaterThan(1);
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--calendar-month-min", "40rem"),
  );
  await expect.poll(tracks).toBe(1);
});
