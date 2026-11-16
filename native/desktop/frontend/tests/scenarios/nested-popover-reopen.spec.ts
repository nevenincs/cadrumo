import { expect, test } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// A popover inside another hands focus back a task after it has gone. A person
// who opens it again in that moment is working inside the popover around it,
// so that one stays open: the nested popover's content is portaled out of the
// enclosing one's, and the enclosing one counts it as its own.

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("reopening the provider list before its focus returns keeps the agent settings open", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await target
    .locator(".pane-agent")
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first()
    .click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  const providerBox = settings.getByRole("button", {
    name: label("desktop.agent.provider"),
  });
  await providerBox.click();
  const entry = target.locator('[role=option][data-way="qwen/api"]');
  await expect(entry).toBeVisible();
  // Choose an entry, and open the list again the moment the chosen one's list
  // has gone, before the task that hands focus back has run.
  await entry.evaluate(
    (chosen, trigger) =>
      new Promise<void>((done) => {
        const box = document.querySelector<HTMLButtonElement>(trigger);
        new MutationObserver((_, watch) => {
          if (chosen.isConnected) return;
          watch.disconnect();
          box?.click();
          done();
        }).observe(document.body, { childList: true, subtree: true });
        (chosen as HTMLElement).click();
      }),
    '[data-slot="provider-select"]',
  );
  await expect(
    target.locator('[role=option][data-way="qwen/cli"]'),
  ).toBeVisible();
  await target.locator('[role=option][data-way="qwen/cli"]').click();
  await expect(settings).toBeVisible();
  await expect(
    settings.getByRole("combobox", { name: label("desktop.agent.model") }),
  ).toHaveValue("fixture-ultra");
});
