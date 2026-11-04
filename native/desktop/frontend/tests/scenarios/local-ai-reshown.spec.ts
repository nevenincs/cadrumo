import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The host keeps one listener for the agent's status, so a second surface
// that watches it takes the notices from the agent column. The column still
// learns that the agent runs, and its settings show the local AI with the
// provider.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

test("the agent settings show the local AI after the agent became ready while the setup panel watched its status", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&catalog=declared",
  );
  await expect(
    target
      .locator(".pane-agent")
      .getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  await target.locator("[data-rail=settings]").click();
  await target
    .locator(".settings [data-settings-provisioning]")
    .getByRole("button", { name: label("desktop.setup.open"), exact: true })
    .click();
  const panel = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  await expect(panel).toBeVisible();
  // The panel reads the status while its local AI is open; the agent then
  // becomes ready.
  await panel
    .locator('[data-setup-element="local_ai"]')
    .getByRole("button", { name: label("desktop.setup.item.local_ai") })
    .click();
  // Its program row is the sign that the panel's local AI is open and
  // watching the status.
  await expect(panel.locator('[data-setup-row="local_ai"]')).toBeVisible();
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await panel.getByLabel(label("desktop.setup.close"), { exact: true }).click();
  await expect(panel).toBeHidden();

  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeVisible();
  const provider = settings(target).locator('li[data-provider="local"]');
  await provider
    .locator("> details")
    .evaluate((node) => ((node as HTMLDetailsElement).open = true));
  await expect(provider.getByTestId("local-ai")).toBeVisible({
    timeout: 5000,
  });
});
