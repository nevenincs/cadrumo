import { openPanelTab } from "../support/panel";
import { expect, test } from "@playwright/test";

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
  await openPanelTab(page, "logs");
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

test("calendar labels and windows share the canonical pill surface", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&calendar=busy&latency=0&bar=off",
  );
  await page.keyboard.press("Control+Shift+D");
  const label = page
    .locator('[data-slot="badge"][data-variant="neutral"]')
    .first();
  const window = page.locator('.calendar-bar[data-state="due"]').first();
  await expect(label).toBeVisible();
  await expect(window).toBeVisible();
  await page.evaluate(() => {
    document.documentElement.style.setProperty("--secondary", "rgb(40 60 80)");
    document.documentElement.style.setProperty("--spacing", "8px");
  });
  for (const pill of [label, window]) {
    await expect(pill).toHaveCSS("background-color", "rgb(40, 60, 80)");
    for (const side of ["top", "right", "bottom", "left"])
      await expect(pill).toHaveCSS(`border-${side}-width`, "0px");
  }
  await expect(label).toHaveCSS("padding-left", "16px");
});

test("log filter pills stay solid and borderless when toggled", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await openPanelTab(page, "logs");
  const pill = page.locator("[data-follow]:visible");
  await expect(pill).toHaveAttribute("aria-pressed", "true");
  const selected = await pill.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  await pill.click();
  await expect(pill).toHaveAttribute("aria-pressed", "false");
  await expect
    .poll(() =>
      pill.evaluate((element) => getComputedStyle(element).backgroundColor),
    )
    .not.toBe(selected);
  const unselected = await pill.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  expect(unselected).not.toBe(selected);
  expect(unselected).not.toBe("rgba(0, 0, 0, 0)");
  await pill.hover();
  const opaque = () =>
    pill.evaluate((element) => {
      const context = document.createElement("canvas").getContext("2d")!;
      context.fillStyle = getComputedStyle(element).backgroundColor;
      context.fillRect(0, 0, 1, 1);
      return context.getImageData(0, 0, 1, 1).data[3];
    });
  await expect.poll(opaque).toBe(255);
  await page.mouse.down();
  await expect.poll(opaque).toBe(255);
  await page.mouse.up();
  for (const side of ["top", "right", "bottom", "left"])
    await expect(pill).toHaveCSS(`border-${side}-width`, "0px");
});
