import { expect, test } from "@playwright/test";
import {
  agentColumn as column,
  openHistory,
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
