import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The agent's settings show each section as soon as its own read answers: a
// slow read of the keys for agents outside Cadrumo does not hold back the
// provider settings, and says on its own that it is still being read.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");

const providers = (target: Page) =>
  target
    .locator(".pane-agent")
    .getByRole("region", { name: label("desktop.providers.title") });

const accessSection = (target: Page) =>
  target
    .locator(".pane-agent details")
    .filter({ hasText: label("desktop.automation_access.title") });

test("the provider settings are drawn while the agent access read is still pending", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(() => window.__scenarioAgentAccessHold?.hold());
  await page
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(providers(page)).toBeVisible();
  // The access section is there, saying only that it is being read.
  await expect(
    accessSection(page)
      .getByRole("status")
      .and(page.locator("[aria-busy=true]")),
  ).toBeVisible();
  // A search while it is pending cannot say nothing matched: that section has
  // not answered yet.
  await page
    .locator(".pane-agent")
    .getByRole("searchbox", { name: label("desktop.settings.agent_search") })
    .fill("zz-no-such-setting");
  await expect(
    page.getByText(label("desktop.settings.agent_search_empty")),
  ).toHaveCount(0);
  await page.evaluate(() => window.__scenarioAgentAccessHold?.release());
  await expect(
    page.getByText(label("desktop.settings.agent_search_empty")),
  ).toBeVisible();
  await page
    .locator(".pane-agent")
    .getByRole("searchbox", { name: label("desktop.settings.agent_search") })
    .fill("");
  await expect(accessSection(page).locator("[aria-busy=true]")).toHaveCount(0);
  await expect(providers(page)).toBeVisible();
});

test("provider settings answered busy while the agent starts say so, and appear once it is ready", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead({ code: "busy" }),
  );
  await page
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  // Not a failure to retry: the agent is starting, and the settings come.
  await expect(
    page
      .locator(".pane-agent")
      .getByRole("status")
      .filter({ hasText: label("desktop.providers.agent_starting") }),
  ).toBeVisible();
  await expect(
    page
      .locator(".pane-agent")
      .getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);
  await page.evaluate(() =>
    window.__scenarioAgentPublishStatus?.({ state: "starting" }),
  );
  await page.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(
    providers(page).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible();
});
