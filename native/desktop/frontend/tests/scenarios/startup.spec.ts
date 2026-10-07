import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

const calls = (page: Page, name: string) =>
  page.evaluate(
    (call) =>
      (window.__scenarioHostCalls ?? []).filter((made) => made === call).length,
    name,
  );
const ghost = (page: Page) => page.locator('[data-slot="account-loading"]');

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.clock.install();
});

test("ghost UI stays non-interactive until the native status confirms readiness", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=runtime-starting&latency=0");
  await expect(ghost(page).first()).toBeVisible();
  await expect(ghost(page).first()).toContainText(
    label("desktop.signin.starting_services"),
  );
  expect(label("desktop.signin.starting_services")).not.toBe(
    "desktop.signin.starting_services",
  );
  await expect(ghost(page).locator("input, button")).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await calls(page, "profiles")).toBe(0);
  expect(await calls(page, "startManager")).toBe(0);
  expect(await calls(page, "signIn")).toBe(0);
  await page.screenshot({
    path: "../../../build/runtime-startup-ui/loading.png",
  });
  await page.clock.runFor(5_000);
  await expect(ghost(page)).toHaveCount(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  expect(await calls(page, "profiles")).toBeGreaterThan(0);
  expect(await calls(page, "startManager")).toBe(0);
  expect(await calls(page, "signIn")).toBe(0);
});

test("settings remain usable during startup", async ({ page }) => {
  await page.goto("/scenarios.html?scenario=runtime-starting&latency=0");
  await expect(ghost(page).first()).toBeVisible();
  await page
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await expect(page.locator(".settings")).toBeVisible();
  expect(await calls(page, "signIn")).toBe(0);
  expect(await calls(page, "startManager")).toBe(0);
});

test("a failed initial readiness read exposes recovery without claiming readiness", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=runtime-startup-failed&latency=0");
  await expect(page.locator(".sign-in")).toContainText("timed_out");
  await expect(ghost(page)).toHaveCount(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  expect(await calls(page, "profiles")).toBe(0);
  expect(await calls(page, "startManager")).toBe(0);
});

test("leaving startup cancels its timer and status polling", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=runtime-starting&latency=0");
  await expect(ghost(page).first()).toBeVisible();
  await page.locator(".scenario-bar").click();
  await page
    .getByRole("button", { name: "Runtime unavailable", exact: true })
    .click();
  await expect(page.locator(".sign-in")).toBeVisible();
  const reads = await calls(page, "signInStatus");
  await page.clock.runFor(91_000);
  expect(await calls(page, "signInStatus")).toBe(reads);
  await expect(ghost(page)).toHaveCount(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
});

for (const scenario of ["manager-still-down", "runtime-startup-stalled"]) {
  test(`${scenario} exits skeleton loading at the startup deadline`, async ({
    page,
  }) => {
    await page.goto(`/scenarios.html?scenario=${scenario}&latency=0`);
    await expect(ghost(page).first()).toBeVisible();
    await page.clock.runFor(91_000);
    await expect(ghost(page)).toHaveCount(0);
    await expect(
      page.locator(".sign-in").getByRole("button", {
        name: label("desktop.signin.start_services"),
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByLabel(label("desktop.signin.password"), { exact: true }),
    ).toHaveCount(0);
    expect(await calls(page, "startManager")).toBe(0);
  });
}

test("reduced motion disables skeleton animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/scenarios.html?scenario=runtime-starting&latency=0");
  const shapes = ghost(page).first().locator('[aria-hidden="true"]');
  await expect(shapes).toBeVisible();
  await expect(shapes).toHaveCSS("animation-name", "none");
});

test("a timed-out initial read does not prevent a bounded retry", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=runtime-startup-stalled&latency=0");
  await page.clock.runFor(91_000);
  const retry = page.locator(".sign-in").getByRole("button", {
    name: label("desktop.signin.start_services"),
    exact: true,
  });
  await retry.click();
  await page.clock.runFor(10);
  expect(await calls(page, "startManager")).toBe(1);
  expect(await calls(page, "signInStatus")).toBe(2);
  await page.clock.runFor(91_000);
  await expect(retry).toBeVisible();
  await expect(ghost(page)).toHaveCount(0);
  expect(await calls(page, "signIn")).toBe(0);
});
