import { expect, test } from "@playwright/test";

test("person input renews once; polling and synthetic events never renew", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const count = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "noteActivity",
        ).length,
    );
  expect(await count()).toBe(0);
  await page.evaluate(() =>
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })),
  );
  expect(await count()).toBe(0);
  await page.keyboard.press("Shift");
  await expect.poll(count).toBe(1);
  await page.keyboard.press("Shift");
  expect(await count()).toBe(1);
});

test("mouse movement counts as input and remains throttled", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const count = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "noteActivity",
        ).length,
    );
  await page.evaluate(() =>
    window.dispatchEvent(new PointerEvent("pointermove")),
  );
  expect(await count()).toBe(0);
  await page.mouse.move(100, 100);
  await expect.poll(count).toBe(1);
  await page.mouse.move(150, 150);
  expect(await count()).toBe(1);
});
