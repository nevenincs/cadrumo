import { expect, test } from "@playwright/test";
import { label } from "../support/strings";

const open = "/scenarios.html?scenario=signed-in&latency=0&bar=off";

const calls = (page: import("@playwright/test").Page) =>
  page.evaluate(() => window.__scenarioHostCalls ?? []);

test("a window after a close that ended a change says once that its outcome is unknown", async ({
  page,
}) => {
  await page.goto(`${open}&previous_close=interrupted`);
  const toast = page.locator('[data-slot="toast"]');
  // Literal English, so a missing catalogue key (shown as the key) fails.
  await expect(toast).toHaveText(
    "Cadrumo closed during a change; its outcome is unknown. Check it before you repeat it.",
  );
  await expect(toast).toHaveText(
    label("desktop.toast.previous_close_interrupted"),
  );
  // The host answers only once, so the window asks only once.
  expect(
    (await calls(page)).filter((call) => call === "previousClose"),
  ).toEqual(["previousClose"]);
});

test("a window after a settled close says nothing about it", async ({
  page,
}) => {
  await page.goto(open);
  await expect
    .poll(async () => (await calls(page)).includes("previousClose"))
    .toBe(true);
  await expect(
    page.getByRole("button", {
      name: label("desktop.rail.settings"),
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator('[data-slot="toast"]')).toHaveText("");
});
