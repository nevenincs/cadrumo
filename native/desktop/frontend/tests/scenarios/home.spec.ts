import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { agentTurns, ask, settled } from "../support/agent";
import { windowToast } from "../support/toast";
import { calls, open, startFromDocs } from "../support/scenarioShell";

// Home is a page of the first pane that draws the product's Home and nothing
// else: its sentences, its states and its counts, zone by zone.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const homeButton = (target: Page) => target.locator('[data-rail="home"]');
const homePage = (target: Page) => target.locator(".home-page");
const zone = (target: Page, name: string) =>
  homePage(target).locator(`[data-zone="${name}"]`);
const homeReads = (target: Page) => calls(target, "home en");

test("Home is read when it is shown and draws what the product served", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  // Nothing is read for a page nobody is looking at.
  expect(await homeReads(target)()).toBe(0);
  await homeButton(target).click();
  await expect(homeButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.home.title"),
  );
  const page = homePage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(zone(target, "actions")).toContainText(
    "Synthetic: review the calculation",
  );
  await expect(zone(target, "actions").locator("li")).toHaveCount(2);
  await expect(zone(target, "declarations")).toContainText("Synthetic return");
  await expect(zone(target, "declarations")).toContainText(
    "Synthetic: needs review",
  );
  await expect(zone(target, "agenda")).toContainText(
    "Synthetic: recorded locally",
  );
  await expect(zone(target, "ledger")).toContainText("40 entries");
  await expect(zone(target, "messages")).toContainText(
    label("desktop.home.messages_attention", { count: 2 }),
  );
  // Every zone shows its data: none says it cannot.
  await expect(page.locator("[data-unavailable]")).toHaveCount(0);
  expect(await homeReads(target)()).toBe(1);
});

test("a zone that does not show its data says so and is never drawn as empty or as zero", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in", "&home=partial");
  await homeButton(target).click();
  const page = homePage(target);
  await expect(page).toBeVisible();
  // The product's own sentence where it served one.
  await expect(zone(target, "actions")).toContainText(
    "Synthetic: next actions appear once your records are checked",
  );
  // The window's generic words for each other standing.
  await expect(zone(target, "declarations")).toContainText(
    label("desktop.home.availability_never_captured"),
  );
  await expect(zone(target, "ledger")).toContainText(
    label("desktop.home.availability_locked"),
  );
  await expect(zone(target, "agenda")).toContainText(
    label("desktop.home.availability_stale"),
  );
  await expect(zone(target, "messages")).toContainText(
    label("desktop.home.availability_unavailable"),
  );
  await expect(page.locator("[data-unavailable]")).toHaveCount(5);
  // No zone claims there is nothing to show, and none shows a count.
  await expect(page.getByText(label("desktop.home.empty"))).toHaveCount(0);
  await expect(zone(target, "ledger")).not.toContainText("0");
  await expect(zone(target, "messages")).not.toContainText("0");
  await expect(page.locator("[data-zone] li")).toHaveCount(0);
});

test("a zone known to be empty says so, and its counts are zeros", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in", "&home=empty");
  await homeButton(target).click();
  const empty = label("desktop.home.empty");
  for (const name of ["actions", "declarations", "agenda"])
    await expect(zone(target, name)).toContainText(empty);
  await expect(zone(target, "ledger")).toContainText("0 entries");
  await expect(zone(target, "messages")).toContainText(
    label("desktop.home.messages_attention", { count: 0 }),
  );
  await expect(homePage(target).locator("[data-unavailable]")).toHaveCount(0);
});

test("Home as a whole unavailable says so with the product's code and draws no zone", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in", "&home=unavailable");
  await homeButton(target).click();
  const unavailable = homePage(target).locator("[data-home-unavailable]");
  await expect(unavailable).toContainText(
    label("desktop.home.availability_unavailable"),
  );
  await expect(unavailable.locator("code")).toHaveText(
    "synthetic.home.unavailable",
  );
  await expect(homePage(target).locator("[data-zone]")).toHaveCount(0);
});

test("a read that fails says so with its code, is not tried again by itself and can be asked again", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioHomeRefused = true;
  });
  await open(target, "signed-in");
  await homeButton(target).click();
  const failed = homePage(target).locator("[data-home-failed]");
  await expect(failed).toHaveAttribute("data-home-failed", "timed_out");
  await expect(failed).toHaveText(
    label("desktop.home.failed", { code: "timed_out" }),
  );
  // Never drawn as an empty Home.
  await expect(homePage(target).locator("[data-zone]")).toHaveCount(0);
  await expect(target.getByText(label("desktop.home.empty"))).toHaveCount(0);
  expect(await homeReads(target)()).toBe(1);
  // Left alone, it is not read again.
  await target.evaluate(
    () => new Promise((resolve) => window.setTimeout(resolve, 600)),
  );
  expect(await homeReads(target)()).toBe(1);
  // Asked again once the host answers, it shows Home.
  await target.evaluate(() => {
    window.__scenarioHomeRefused = false;
  });
  await homePage(target)
    .getByRole("button", { name: label("desktop.home.refresh") })
    .last()
    .click();
  await expect(zone(target, "actions")).toBeVisible();
  expect(await homeReads(target)()).toBe(2);
});

test("a declaration row opens the declarations and an agenda row the calendar, as links do", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await homeButton(target).click();
  await zone(target, "agenda")
    .getByRole("button", { name: /Synthetic due date/ })
    .click();
  await expect(target.locator(".calendar-page")).toBeVisible();
  await homeButton(target).click();
  await zone(target, "declarations")
    .getByRole("button", { name: /Synthetic return/ })
    .click();
  await expect(target.locator(".declarations-page")).toBeVisible();
  await expect(homePage(target)).toHaveCount(0);
});

test("an agent link to Home opens it with the keyboard on it and no notice", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await ask(target, "Respóndeme con enlaces");
  await settled(target);
  await agentTurns(target)
    .getByRole("link", { name: "el inicio", exact: true })
    .click();
  const page = homePage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(windowToast(target)).toHaveText("");
});
