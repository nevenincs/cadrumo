import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// While the agent service cannot answer for the provider settings, the
// section draws the connections the agent declares, each standing on where
// the service is, and says why once above them. The wait ends on what the
// service publishes: the settings once it is admitted, or the reason it
// stopped with the way on, never a spinner left turning.

const pane = (target: Page) => target.locator(".pane-agent");

const providers = (target: Page) =>
  pane(target).getByRole("region", { name: label("desktop.providers.title") });

const statuses = (target: Page) =>
  providers(target).locator("[data-slot=provider-status]");

const hostCalls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

async function openSettings(target: Page) {
  await pane(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
}

test("a starting agent draws each declared connection as starting, then the settings once it is ready", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=declared",
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.holdSettingsBusy(),
  );
  await openSettings(target);
  await expect(
    providers(target)
      .getByRole("status")
      .filter({ hasText: label("desktop.providers.agent_starting") }),
  ).toBeVisible();
  // Every row the agent declares is drawn, each saying it waits on the agent.
  const count = await statuses(target).count();
  expect(count).toBeGreaterThan(0);
  await expect(
    providers(target).locator(
      "[data-slot=provider-status][data-status=starting]",
    ),
  ).toHaveCount(count);
  await expect(statuses(target).first()).toHaveText(
    label("desktop.providers.status_starting"),
  );
  // Nothing is offered to change while the service holds the settings.
  await expect(providers(target).getByRole("button")).toHaveCount(0);
  await expect(providers(target).locator("[aria-busy=true]")).toHaveCount(0);

  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.releaseSettingsBusy();
    window.__scenarioAgentPublishStatus?.();
  });
  await expect(
    providers(target).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible();
  await expect(providers(target).locator("[data-status=starting]")).toHaveCount(
    0,
  );
  await expect(
    providers(target).getByText(label("desktop.providers.agent_starting")),
  ).toHaveCount(0);
});

test("an admitted service that has not yet taken up the session answers not signed in: still starting, never a load failure", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=declared",
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSettingsRead({
      code: "not_signed_in",
    }),
  );
  await openSettings(target);
  await expect(
    providers(target)
      .getByRole("status")
      .filter({ hasText: label("desktop.providers.agent_starting") }),
  ).toBeVisible();
  await expect(
    providers(target).locator("[data-status=starting]").first(),
  ).toBeVisible();
  await expect(
    pane(target).getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);
  await expect(providers(target).getByRole("alert")).toHaveCount(0);
  // It waits on the service's next status, not on a timer.
  const reads = async () =>
    (await hostCalls(target)).filter((call) => call === "providerStatus")
      .length;
  const asked = await reads();
  await target.waitForTimeout(1_000);
  expect(await reads()).toBe(asked);
  await expect(
    pane(target).getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);

  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(
    providers(target).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible();
  await expect(providers(target).locator("[data-status=starting]")).toHaveCount(
    0,
  );
});

test("a start that fails ends the wait with its cause and a Retry that starts the agent again", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=declared",
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.holdSettingsBusy(),
  );
  await openSettings(target);
  await expect(
    providers(target).locator("[data-status=starting]").first(),
  ).toBeVisible();

  // The service gives up on the start: it publishes why, and the host's read
  // then fails because nothing is starting any more.
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.releaseSettingsBusy();
    window.__scenarioProviderSignIn!.holdSettingsUnavailable();
    window.__scenarioAgentPublishStatus?.({
      state: "refused",
      code: "agent_timeout",
    });
  });
  const alert = providers(target).getByRole("alert");
  await expect(alert).toContainText(label("desktop.agent.service_timeout"));
  // No row is left saying it waits: a stopped service serves no catalogue.
  await expect(statuses(target)).toHaveCount(0);
  // It is not the section's own read failing, and nothing still spins.
  await expect(
    pane(target).getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);
  await expect(providers(target).locator("[aria-busy=true]")).toHaveCount(0);

  const before = (await hostCalls(target)).filter(
    (call) => call === "agentRetry",
  ).length;
  await alert
    .getByRole("button", { name: label("desktop.agent.retry") })
    .click();
  await expect
    .poll(
      async () =>
        (await hostCalls(target)).filter((call) => call === "agentRetry")
          .length,
    )
    .toBe(before + 1);

  // The new start goes through: the settings are drawn.
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.releaseSettingsBusy();
    window.__scenarioAgentPublishStatus?.({ state: "starting" });
    window.__scenarioAgentPublishStatus?.();
  });
  await expect(
    providers(target).locator("[data-slot=lane-expander]").first(),
  ).toBeVisible();
  await expect(providers(target).getByRole("alert")).toHaveCount(0);
});

test("with no agent to start the section says so at once, offers no start, and never waits", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=unsupported",
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.holdSettingsUnavailable(),
  );
  await openSettings(target);
  const alert = providers(target).getByRole("alert");
  await expect(alert).toHaveText(label("desktop.agent.platform_unsupported"));
  // No start can move it on, so none is offered.
  await expect(alert.getByRole("button")).toHaveCount(0);
  await expect(
    providers(target).getByText(label("desktop.providers.agent_starting")),
  ).toHaveCount(0);
  await expect(providers(target).locator("[data-status=starting]")).toHaveCount(
    0,
  );
  await expect(providers(target).locator("[aria-busy=true]")).toHaveCount(0);
  await expect(
    pane(target).getByText(label("desktop.providers.load_failed")),
  ).toHaveCount(0);
});

test("the waiting rows fit a 420 px window without spilling sideways", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 420, height: 900 });
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=declared",
  );
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.holdSettingsBusy(),
  );
  await target.locator("[data-rail=agent]").click();
  await openSettings(target);
  await expect(
    providers(target).locator("[data-status=starting]").first(),
  ).toBeVisible();
  const spill = await providers(target).evaluate((section) => {
    const edge = section.getBoundingClientRect().right;
    return [...section.querySelectorAll("li, li *")].filter(
      (node) => node.getBoundingClientRect().right > edge + 0.5,
    ).length;
  });
  expect(spill).toBe(0);
  expect(
    await target.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
