import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The agent service serves, for each provider lane, whether a conversation on
// it leaves this computer: the agent's own declaration, `reads_off_host`. The
// lane says so in the person's language, from that served value alone; the
// window never reads it from the lane's transport or provider.

test.beforeEach(() => {
  scenarioOnly("The scenario host serves each lane's declaration.");
});

const settings = (target: Page, language: string) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title", {}, language),
  });

async function openSettings(target: Page, language: string) {
  await target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=${language}`,
  );
  await target
    .locator(".pane-agent")
    .getByRole("button", {
      name: label("desktop.agent.settings", {}, language),
    })
    .click();
  await expect(settings(target, language)).toBeVisible();
  await settings(target, language)
    .locator("[data-slot=lane-expander][aria-expanded=false]")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => (node as HTMLElement).click()),
    );
}

for (const language of ["en", "es", "ca", "hu"] as const) {
  test(`each lane says whether its conversation leaves this computer in ${language}`, async ({
    page: target,
  }) => {
    await openSettings(target, language);
    const lanes = settings(target, language);
    // The hosted lanes the made-up agent declares off this computer.
    for (const id of ["zhipu_cli", "kimi_api", "antigravity_cli"]) {
      const lane = lanes.locator(`li[data-lane="${id}"]`);
      await expect(lane).toHaveAttribute("data-reads-off-host", "true");
      await expect(lane).toContainText(
        label("desktop.providers.reads_off_host", {}, language),
      );
      await expect(lane).not.toContainText(
        label("desktop.providers.reads_on_host", {}, language),
      );
    }
    // The local engine's lane, declared on this computer.
    const local = lanes.locator('li[data-lane="llamacpp_api"]');
    await expect(local).toHaveAttribute("data-reads-off-host", "false");
    await expect(local).toContainText(
      label("desktop.providers.reads_on_host", {}, language),
    );
    await expect(local).not.toContainText(
      label("desktop.providers.reads_off_host", {}, language),
    );
  });
}
