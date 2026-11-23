import { expect, test } from "@playwright/test";
import { matrixCell, openModelPicker, scenarioOnly } from "../support/agent";

// A choice in the agent settings is made in one press, and the settings stay
// open for the next: a person who chooses again straight away, before the
// first choice has settled, is still working inside them, so they stay open
// and the last choice is the one held.

test("choosing again straight after a choice keeps the agent settings open", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const settings = await openModelPicker(target);
  const first = matrixCell(settings, "qwen/api", "fixture-coder");
  await expect(first).toBeVisible();
  // Choose a cell, and another of another lane in the same task, before the
  // first choice has been rendered.
  await first.evaluate((chosen, next) => {
    (chosen as HTMLElement).click();
    document.querySelector<HTMLElement>(next)?.click();
  }, 'tr[data-slot=model-matrix-row][data-way="qwen/cli"][data-model="fixture-ultra"] [role=radio][data-column="default"]');
  await expect(settings).toBeVisible();
  await expect(
    matrixCell(settings, "qwen/cli", "fixture-ultra"),
  ).toHaveAttribute("aria-checked", "true");
  await expect(first).toHaveAttribute("aria-checked", "false");
});
