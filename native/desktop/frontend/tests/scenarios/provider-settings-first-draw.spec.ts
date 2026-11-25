import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The provider settings are drawn from their own status read. While the
// service starts the agent the host can answer that read busy, and the
// agent's other reads (its status and the ready it publishes, its catalog,
// its local models and engine, its skills, the keys for agents outside
// Cadrumo) can stay unanswered for many seconds more. A busy answer is said as
// the wait it is and read again on a cue, never by time: with the agent's
// status held no publication comes, so the cue is the person's (coming back
// to the window, or opening the settings again), and that answer is drawn.
// The bound is the one ruled for the window: drawn within 4 s of the ask.

test.beforeEach(() => {
  scenarioOnly("The scenario host holds the agent's other reads.");
});

const FIRST_DRAW_MS = 4_000;

const pane = (target: Page) => target.locator(".pane-agent");

const providers = (target: Page) =>
  pane(target).getByRole("region", { name: label("desktop.providers.title") });

const settingsDoor = (target: Page) =>
  pane(target).getByRole("button", { name: label("desktop.agent.settings") });

const statusReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "providerStatus",
      ).length,
  );

const drawnWithin = async (target: Page) => {
  const began = Date.now();
  await expect(
    providers(target).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible({ timeout: FIRST_DRAW_MS + 2_000 });
  return Date.now() - began;
};

const starting = (target: Page) =>
  pane(target)
    .getByRole("status")
    .filter({ hasText: label("desktop.providers.agent_starting") });

/** Opens the agent's settings and answers how long the provider settings
 * took to be drawn with their providers, in ms. */
async function openAndTime(target: Page): Promise<number> {
  const began = Date.now();
  await settingsDoor(target).click();
  await expect(
    providers(target).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible({ timeout: FIRST_DRAW_MS + 2_000 });
  return Date.now() - began;
}

test("provider settings answered busy are drawn within 4 s while every other agent read is held", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(settingsDoor(target)).toBeVisible();
  // The agent's column is shown again with every read but the provider
  // status held, so the agent publishes neither its status nor its ready.
  await target.evaluate(() => window.__scenarioAgentReadsHold?.hold());
  const agentRail = target.locator("[data-rail=agent]");
  await agentRail.click();
  await expect(settingsDoor(target)).toBeHidden();
  await agentRail.click();
  await expect(settingsDoor(target)).toBeVisible();

  // The first status read is answered busy, at once.
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead({ code: "busy" }),
  );
  await settingsDoor(target).click();
  // A wait, said as one, not a failure to retry, and not read again by time.
  await expect(starting(target)).toBeVisible();
  await expect(
    pane(target).getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);
  const asked = await statusReads(target);
  await target.waitForTimeout(1_000);
  expect(await statusReads(target)).toBe(asked);
  // The person coming back to the window reads it again, and it is drawn.
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  expect(await drawnWithin(target)).toBeLessThanOrEqual(FIRST_DRAW_MS);

  // Each later opening reads the status again; one answered busy keeps the
  // answer drawn before it on screen, within the same bound.
  await settingsDoor(target).click();
  await expect(providers(target)).toHaveCount(0);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead({ code: "busy" }),
  );
  expect(await openAndTime(target)).toBeLessThanOrEqual(FIRST_DRAW_MS);

  await target.evaluate(() => window.__scenarioAgentReadsHold?.release());
  await expect(providers(target)).toBeVisible();
});

test("provider settings answered at once are drawn within 4 s while every other agent read is held", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(settingsDoor(target)).toBeVisible();
  await target.evaluate(() => window.__scenarioAgentReadsHold?.hold());
  const agentRail = target.locator("[data-rail=agent]");
  await agentRail.click();
  await expect(settingsDoor(target)).toBeHidden();
  await agentRail.click();
  await expect(settingsDoor(target)).toBeVisible();

  expect(await openAndTime(target)).toBeLessThanOrEqual(FIRST_DRAW_MS);
  await settingsDoor(target).click();
  await expect(providers(target)).toHaveCount(0);
  expect(await openAndTime(target)).toBeLessThanOrEqual(FIRST_DRAW_MS);

  await target.evaluate(() => window.__scenarioAgentReadsHold?.release());
  await expect(providers(target)).toBeVisible();
});

test("provider settings are drawn from their status while the access keys and the catalog are both asked and held, and one opening reads the catalog once", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(settingsDoor(target)).toBeVisible();
  // The column is shown again with the access keys and the catalog held, so
  // its own catalog read is still unanswered when the settings open.
  await target.evaluate(() => {
    window.__scenarioAgentAccessHold?.hold();
    window.__scenarioAgentCatalogHold?.hold();
  });
  const agentRail = target.locator("[data-rail=agent]");
  await agentRail.click();
  await expect(settingsDoor(target)).toBeHidden();
  const since = await target.evaluate(
    () => (window.__scenarioHostCalls ?? []).length,
  );
  await agentRail.click();
  await expect(settingsDoor(target)).toBeVisible();
  const asked = async () =>
    target.evaluate(
      (from) => (window.__scenarioHostCalls ?? []).slice(from),
      since,
    );
  await expect
    .poll(async () => (await asked()).includes("agentProviderCatalogHeld"))
    .toBe(true);

  // The lanes are drawn from the status while nothing else has answered.
  expect(await openAndTime(target)).toBeLessThanOrEqual(FIRST_DRAW_MS);
  // The access keys and the catalog are both asked before either answers.
  await expect
    .poll(async () => (await asked()).includes("agentAccessList"))
    .toBe(true);
  const held = await asked();
  expect(held).not.toContain("agentProviderCatalogResolved");
  // The column's catalog read still out when the settings open is the one
  // answer the opening shares: the catalog is asked once.
  expect(held.filter((call) => call === "agentProviderCatalogHeld")).toEqual([
    "agentProviderCatalogHeld",
  ]);

  await target.evaluate(() => {
    window.__scenarioAgentAccessHold?.release();
    window.__scenarioAgentCatalogHold?.release();
  });
  await expect
    .poll(async () => (await asked()).includes("agentProviderCatalogResolved"))
    .toBe(true);
  await expect(providers(target)).toBeVisible();
  expect(
    (await asked()).filter((call) => call === "agentProviderCatalog"),
  ).toEqual(["agentProviderCatalog"]);
});
