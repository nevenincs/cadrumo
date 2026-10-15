import { label as chromeLabel } from "../support/strings";
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

test("log follow icon uses the shared toggle surface and density", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await openPanelTab(page, "logs");
  const follow = page.locator("[data-follow]");
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  const selected = await follow.evaluate(
    (element) => getComputedStyle(element).backgroundColor,
  );
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await page.mouse.move(0, 0);
  await follow.blur();
  await expect
    .poll(() =>
      follow.evaluate((element) => getComputedStyle(element).backgroundColor),
    )
    .not.toBe(selected);
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--spacing-control-xs", "40px"),
  );
  await expect(follow).toHaveCSS("width", "40px");
  await expect(follow).toHaveCSS("height", "40px");
  for (const side of ["top", "right", "bottom", "left"])
    await expect(follow).toHaveCSS(`border-${side}-width`, "0px");
});

test("log toolbar reuses agent header button styles and separates action groups", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await openPanelTab(page, "logs");
  const history = page.locator(".pane-agent").getByRole("button", {
    name: chromeLabel("desktop.agent.history"),
    exact: true,
  });
  const filters = page.locator(".log-toolbar").getByRole("button", {
    name: chromeLabel("desktop.logs.filters"),
    exact: true,
  });
  const follow = page.locator("[data-follow]");
  const properties = [
    "width",
    "height",
    "border-radius",
    "color",
    "background-color",
    "border-top-width",
  ];
  for (const property of properties) {
    const expected = await history.evaluate(
      (element, property) =>
        getComputedStyle(element).getPropertyValue(property),
      property,
    );
    await expect(filters).toHaveCSS(property, expected);
  }
  await history.click();
  await page.mouse.move(0, 0);
  await history.blur();
  for (const property of properties) {
    const expected = await history.evaluate(
      (element, property) =>
        getComputedStyle(element).getPropertyValue(property),
      property,
    );
    await expect(follow).toHaveCSS(property, expected);
  }
  expect(
    await page
      .locator(".log-toolbar [data-log-group]")
      .evaluateAll((groups) =>
        groups.map((group) => group.getAttribute("data-log-group")),
      ),
  ).toEqual(["filters", "selection", "files", "follow"]);
  await expect(follow.locator(".lucide-circle-pause")).toHaveCount(1);
  await follow.click();
  await expect(follow.locator(".lucide-circle-play")).toHaveCount(1);
});
