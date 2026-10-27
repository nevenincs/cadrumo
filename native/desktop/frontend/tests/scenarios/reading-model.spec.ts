import { expect, test, type Page } from "@playwright/test";
import { openModelPicker, pickWay, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// Documents are read with the one model the person picks in the agent
// column's model picker, on any lane, local or not.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const open = (target: Page) =>
  target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready",
  );

/** The model the made-up service stores for reading documents. */
const storedReading = (target: Page) =>
  target.evaluate(async () => {
    const list = await window.__fixtureAgentSession?.localModels?.();
    return list?.state === "readable" ? list.reading : undefined;
  });

test("the model picked in the agent column is the one documents are read with, on any lane", async ({
  page: target,
}) => {
  await open(target);
  // Nothing is stored for reading until the person picks.
  expect(await storedReading(target)).toBeNull();
  let picker = await openModelPicker(target);
  await pickWay(target, picker, "beta/cli");
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  await expect
    .poll(() => storedReading(target))
    .toMatchObject({ lane: "beta_cli" });
  picker = await openModelPicker(target);
  await pickWay(target, picker, "local/api");
  await picker
    .getByLabel(label("desktop.agent.model"))
    .selectOption("synthetic-vision:1");
  await expect
    .poll(() => storedReading(target))
    .toEqual({ lane: "local_api", model: "synthetic-vision:1" });
});
