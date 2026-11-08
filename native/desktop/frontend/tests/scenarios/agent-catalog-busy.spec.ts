import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  offeredModels,
  openHistory,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// A service still starting the agent can be too busy to answer its catalog.
// The column says the agent is still starting, and reads the catalog again
// when the service publishes the agent's status, so the person gets the
// choices without doing anything.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides when the service is busy.");
});

test("an unsupported platform reports its capability without catalog or model reads", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=unsupported",
  );
  await expect(column(page).getByRole("status")).toContainText(
    label("desktop.agent.platform_unsupported"),
  );
  await expect(
    column(page).getByRole("button", {
      name: label("desktop.agent.retry"),
      exact: true,
    }),
  ).toHaveCount(0);
  await page.waitForTimeout(1200);
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter(
      (call) => call === "agentProviderCatalog" || call === "agentLocalModels",
    ),
  ).toEqual([]);
});

test("history waits for the agent and refreshes after service recovery", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect
    .poll(() =>
      page.evaluate(() =>
        (window.__scenarioHostCalls ?? []).includes(
          "agentProviderCatalogResolved",
        ),
      ),
    )
    .toBe(true);
  await page.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({ state: "starting" }),
  );
  await expect(
    column(page).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await openHistory(page);
  const reads = () =>
    page.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "agentConversations",
        ).length,
    );
  expect(await reads()).toBe(0);
  await page.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(reads).toBe(1);
  await expect(
    column(page).getByText(label("desktop.agent.service_signed_out")),
  ).toHaveCount(0);
  await page.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({
      state: "refused",
      code: "agent_service_failed",
    }),
  );
  await expect(
    column(page)
      .locator(".agent-body")
      .getByText(label("desktop.agent.unavailable"), { exact: true }),
  ).toBeVisible();
  expect(await reads()).toBe(1);
  await page.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(reads).toBe(2);
});

test("a catalog the busy service cannot answer yet is read again once the agent's status is published", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy",
  );
  const starting = column(target).getByText(
    label("desktop.agent.service_starting"),
  );
  await expect(starting).toBeVisible();
  // Nothing can be chosen while the catalog is unread.
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveAccessibleName(new RegExp(label("desktop.agent.unavailable")));

  // The signal: the service publishes the agent's status.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(starting).toHaveCount(0);
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call === "agentProviderCatalogResolved").length,
  ).toBeGreaterThanOrEqual(1);
});

test("the stored model lists are not asked for while the agent starts, and are read and applied once it runs", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&catalog=declared",
  );
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  const localModelReads = () =>
    target.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "agentLocalModels",
        ).length,
    );
  // The catalog is asked for while starting, with its own retry; the lists
  // have none, and the host refuses them until the service has a connection.
  await expect
    .poll(() =>
      target.evaluate(() =>
        (window.__scenarioHostCalls ?? []).includes("agentProviderCatalog"),
      ),
    )
    .toBe(true);
  await target.waitForTimeout(600);
  expect(await localModelReads()).toBe(0);
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(localModelReads).toBeGreaterThanOrEqual(1);
  // The lists read at ready are applied: the local lane serves a model nobody
  // put on its list, and the picker leaves it out. Lists left unread would
  // offer it.
  const picker = await openModelPicker(target);
  await pickWay(target, picker, "local/api");
  expect(await offeredModels(picker)).toEqual([
    "synthetic-text:1",
    "synthetic-vision:1",
  ]);
});

/** How many times the window has asked for the catalog. */
const catalogReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentProviderCatalog",
      ).length,
  );

/** Two minutes on the page's clock, in steps: each pause is scheduled only
 * once the read before it has been shown. */
const pass = async (target: Page) => {
  for (let step = 0; step < 12; step++) {
    await target.clock.fastForward("00:10");
    await target.waitForTimeout(50);
  }
};

test("a catalog the service is still busy with just after the agent is ready loads without a reload", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy-past-ready",
  );
  const starting = column(target).getByText(
    label("desktop.agent.service_starting"),
  );
  await expect(starting).toBeVisible();
  // A long start: the service answers every read busy while the agent starts.
  await pass(target);
  const beforeReady = await catalogReads(target);
  expect(beforeReady).toBeGreaterThan(1);

  // The agent is ready, and the service stays busy for a moment longer.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect.poll(() => catalogReads(target)).toBe(beforeReady + 1);
  // The ready signal asks once: its busy answer is followed after a pause,
  // not by a second read in the same busy moment.
  await target.waitForTimeout(300);
  expect(await catalogReads(target)).toBe(beforeReady + 1);
  await expect(starting).toBeVisible();

  // After the pause the service answers, and the choices appear with
  // nothing asked of the person.
  await target.clock.fastForward("00:03");
  await expect(starting).toHaveCount(0);
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.choose_model"),
      exact: false,
    }),
  ).toHaveCount(0);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).toContain("agentProviderCatalogResolved");
});

test("a service that stays busy is asked again until it answers, and a person's retry asks at once", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy",
  );
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await pass(target);
  const first = await catalogReads(target);
  expect(first).toBeGreaterThan(1);
  // The service stays busy and publishes nothing: the reads go on, each
  // after a pause, with no last one.
  await pass(target);
  const followed = await catalogReads(target);
  expect(followed).toBeGreaterThan(first);
  // No pause outlasts a ten-second step, so most steps ask again.
  expect(followed - first).toBeGreaterThanOrEqual(6);

  // The person asks again where the failed read is shown: the local
  // provider's models in the agent settings.
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const providers = column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });
  await providers
    .locator('li[data-provider="local"] > details')
    .evaluate((node) => ((node as HTMLDetailsElement).open = true));
  const asked = await catalogReads(target);
  await providers
    .locator('li[data-provider="local"]')
    .getByRole("alert")
    .filter({ hasText: label("desktop.providers.load_failed") })
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  // The retry asks at once, without waiting for the next pause to end.
  await expect.poll(() => catalogReads(target)).toBeGreaterThan(asked);
});
