import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

const calls = (page: Page, name: string) =>
  page.evaluate(
    (call) =>
      (window.__scenarioHostCalls ?? []).filter((made) => made === call).length,
    name,
  );

const start = (page: Page) =>
  page.locator(".sign-in").getByRole("button", {
    name: label("desktop.signin.start_services"),
    exact: true,
  });
const pending = (page: Page) =>
  page.locator(".sign-in").getByRole("button", {
    name: label("desktop.signin.starting_services"),
    exact: true,
  });

async function open(page: Page, scenario: string) {
  await page.clock.install();
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0`);
  // Initial automatic startup gets its bounded observation period before
  // these tests exercise an explicit recovery request.
  await page.clock.runFor(91_000);
  expect(await calls(page, "profiles")).toBe(0);
  expect(await calls(page, "startManager")).toBe(0);
  await expect(start(page)).toBeVisible();
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
});

test("manager start stays pending without duplicate dispatch or login", async ({
  page,
}) => {
  await open(page, "manager-pending");
  const before = await calls(page, "signInStatus");
  await start(page).click();
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  await expect(pending(page)).toHaveAttribute("aria-disabled", "true");
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.signin.starting_services"),
  );
  await pending(page).evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });
  await page.clock.runFor(5_000);
  expect(await calls(page, "startManager")).toBe(1);
  expect(await calls(page, "signInStatus")).toBe(before);
  expect(await calls(page, "signIn")).toBe(0);
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
});

test("availability reads recover the sign-in form after one manager dispatch", async ({
  page,
}) => {
  await open(page, "manager-recovers");
  const before = await calls(page, "signInStatus");
  await page.clock.runFor(3_000);
  expect(await calls(page, "signInStatus")).toBe(before);
  expect(await calls(page, "startManager")).toBe(0);
  await start(page).click();
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  await pending(page).evaluate((button: HTMLButtonElement) => button.click());
  await page.clock.runFor(8_000);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.signin.title"),
  );
  expect(await calls(page, "startManager")).toBe(1);
  expect(await calls(page, "signIn")).toBe(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveValue("");
});

for (const [scenario, code] of [
  ["manager-failed", "spawn_failed"],
  ["manager-unmanaged", "manager_unmanaged"],
  ["manager-unsupported", "manager_unsupported"],
] as const) {
  test(`manager refusal ${code} remains visible and permits a later request`, async ({
    page,
  }) => {
    await open(page, scenario);
    await start(page).click();
    await page.clock.runFor(10);
    await expect(page.locator(".sign-in")).toContainText(code);
    await expect(start(page)).toBeVisible();
    await expect(start(page)).not.toHaveAttribute("aria-busy", "true");
    expect(await calls(page, "startManager")).toBe(1);
    expect(await calls(page, "signIn")).toBe(0);
    await expect(
      page.getByLabel(label("desktop.signin.password"), { exact: true }),
    ).toHaveCount(0);
    await start(page).click();
    await page.clock.runFor(10);
    expect(await calls(page, "startManager")).toBe(2);
  });
}

test("dispatched manager keeps unavailability truthful after the bounded wait", async ({
  page,
}) => {
  test.setTimeout(60_000);
  await open(page, "manager-still-down");
  await start(page).click();
  await page.clock.runFor(10);
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  await page.clock.runFor(91_000);
  await expect(start(page)).toBeVisible();
  await expect(page.locator(".sign-in")).toContainText(
    label("desktop.signin.refused.runtime_unavailable"),
  );
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  expect(await calls(page, "startManager")).toBe(1);
  expect(await calls(page, "signIn")).toBe(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
});

test("a late readiness answer cannot revive an unmounted manager wait", async ({
  page,
}) => {
  await open(page, "manager-readiness-delayed");
  await start(page).click();
  await page.clock.runFor(10);
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  expect(await calls(page, "signInStatus")).toBeGreaterThan(1);
  expect(await calls(page, "managerReadinessResolved")).toBe(0);

  await page.keyboard.press("Escape");
  await page.locator(".scenario-bar").click();
  await page
    .getByRole("button", { name: "Runtime unavailable", exact: true })
    .click();
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  const statusReads = await calls(page, "signInStatus");
  const profileReads = await calls(page, "profiles");
  await page.clock.runFor(6_000);
  expect(await calls(page, "managerReadinessResolved")).toBe(1);
  expect(await calls(page, "signInStatus")).toBe(statusReads);
  expect(await calls(page, "profiles")).toBe(profileReads);
  expect(await calls(page, "startManager")).toBe(0);
  expect(await calls(page, "signIn")).toBe(0);
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
});

test("repeated retry clicks share the pending manager dispatch", async ({
  page,
}) => {
  await open(page, "manager-retry-delayed");
  await start(page).click();
  await page.clock.runFor(4_500);
  await expect(page.locator(".sign-in")).toContainText("spawn_failed");
  expect(await calls(page, "startManager")).toBe(1);

  await start(page).click();
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  await pending(page).evaluate((button: HTMLButtonElement) => {
    for (let click = 0; click < 10; click += 1) button.click();
  });
  await page.clock.runFor(2_000);
  await expect(pending(page)).toHaveAttribute("aria-busy", "true");
  expect(await calls(page, "startManager")).toBe(2);
  expect(await calls(page, "signIn")).toBe(0);
  await page.clock.runFor(2_500);
  await expect(start(page)).toBeVisible();
  expect(await calls(page, "startManager")).toBe(2);
});

test("a rejected readiness read preserves the previously unavailable runtime", async ({
  page,
}) => {
  await open(page, "manager-status-rejected");
  await start(page).click();
  await page.clock.runFor(2_000);
  expect(await calls(page, "managerStatusRejected")).toBeGreaterThan(0);
  expect(await calls(page, "startManager")).toBe(1);
  expect(await calls(page, "signIn")).toBe(0);
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(page.locator(".sign-in")).toContainText("timed_out");
  await expect(start(page)).toBeVisible();
  await expect(page.locator('[data-slot="account-loading"]')).toHaveCount(0);
});

test("an initial unreadable status keeps the existing unknown-state form", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=error&latency=0");
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".sign-in")).toContainText("timed_out");
  expect(await calls(page, "startManager")).toBe(0);
  expect(await calls(page, "signIn")).toBe(0);
});
