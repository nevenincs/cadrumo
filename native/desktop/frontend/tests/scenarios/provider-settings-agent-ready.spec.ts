import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// While the service starts the agent, the host cannot reach the agent's
// administration and refuses the provider settings read: `read_failed`, with
// the reason `agent_admin_unavailable`, as a native build served it. The
// window reads the settings again when the service publishes the agent ready,
// from that publication alone: no timer while it starts, and no read for a
// publication that does not make it ready.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides when the agent turns ready.");
});

const pane = (target: Page) => target.locator(".pane-agent");

const settings = (target: Page) =>
  pane(target).getByRole("region", { name: label("desktop.providers.title") });

const settingsReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "providerStatus",
      ).length,
  );

test("settings refused while the agent starts are read again when it is ready", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=declared",
  );
  await expect(
    pane(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead({
      reason: "agent_admin_unavailable",
    }),
  );
  await pane(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const failed = pane(target).getByText(
    label("desktop.providers.load_failed"),
    {
      exact: true,
    },
  );
  await expect(failed).toBeVisible();
  expect(await settingsReads(target)).toBe(1);

  // Nothing is read again while the agent is still starting.
  await target.waitForTimeout(1000);
  await target.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({
      state: "starting",
      lane: "development",
    }),
  );
  await target.waitForTimeout(300);
  expect(await settingsReads(target)).toBe(1);

  // The agent is ready: the settings are read once and shown.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(settings(target)).toBeVisible();
  await expect(failed).toHaveCount(0);
  expect(await settingsReads(target)).toBe(2);

  // A repeated ready publication is not a new turn to ready.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await target.waitForTimeout(300);
  expect(await settingsReads(target)).toBe(2);
});
