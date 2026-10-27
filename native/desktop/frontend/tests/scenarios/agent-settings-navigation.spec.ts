import { expect, test } from "@playwright/test";
import { agentColumn as column, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

test("opening local models after closing the agent settings focuses the local provider", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready",
  );
  const providers = column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings"), exact: true })
    .click();
  await expect(providers).toBeVisible();

  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings"), exact: true })
    .click();
  await expect(providers).toHaveCount(0);
  await target.locator("[data-rail=settings]").click();
  await target
    .locator(".settings")
    .getByRole("button", {
      name: label("desktop.setup.item.local_ai"),
      exact: true,
    })
    .click();
  const local = column(target).locator('li[data-provider="local"] > details');
  await expect(local).toHaveAttribute("open", "");
  await expect(local.locator(":scope > summary")).toBeFocused();
  await expect(local.locator('[data-slot="local-models"]')).toBeVisible();
});
