import { expect, test } from "@playwright/test";
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

test("a person's retry after the bounded busy reads are spent starts a fresh budget of re-reads", async ({
  page: target,
}) => {
  await target.clock.install();
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=busy",
  );
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  const reads = () =>
    target.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "agentProviderCatalog",
        ).length,
    );
  // The fallback pauses grow with each read; jump past them in steps, since
  // each pause is scheduled only once the read before it has been shown.
  const pass = async () => {
    for (let step = 0; step < 12; step++) {
      await target.clock.fastForward("00:10");
      await target.waitForTimeout(50);
    }
  };
  await pass();
  const spent = await reads();
  expect(spent).toBeGreaterThan(1);
  // The service stays busy and publishes nothing: the budget is spent and
  // no further read follows by itself.
  await pass();
  expect(await reads()).toBe(spent);

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
  await providers
    .locator('li[data-provider="local"]')
    .getByRole("alert")
    .filter({ hasText: label("desktop.providers.load_failed") })
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect.poll(reads).toBeGreaterThan(spent);
  const asked = await reads();
  // The retry's own read is busy again, and the bounded re-reads resume.
  await pass();
  expect(await reads()).toBeGreaterThan(asked);
});
