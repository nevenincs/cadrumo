import { expect, test, type Page } from "@playwright/test";
import { openModelPicker, pickWay, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// Documents are read with the one model the person picks in the agent
// column's model picker, on any lane, local or not.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

// Every model of the local lane is held, so a model other than the one the
// lane starts with can be picked.
const open = (target: Page) =>
  target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&models=all",
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
  const model = picker.getByLabel(label("desktop.agent.model"));
  // The lane starts on another model, so the store changes only by the pick.
  await expect(model).not.toHaveValue("synthetic-vision:1");
  await expect
    .poll(() => storedReading(target))
    .toMatchObject({ lane: "local_api" });
  expect(await storedReading(target)).not.toEqual({
    lane: "local_api",
    model: "synthetic-vision:1",
  });
  await model.selectOption("synthetic-vision:1");
  await expect
    .poll(() => storedReading(target))
    .toEqual({ lane: "local_api", model: "synthetic-vision:1" });
});

test("on a fresh profile the picker shows the installed model the service reads documents with, without a pick", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&models=all&reading_default=local_api:synthetic-vision:1",
  );
  // Nothing is stored: the service serves its installed default.
  await expect
    .poll(() =>
      target.evaluate(async () => {
        const list = await window.__fixtureAgentSession?.localModels?.();
        return list?.state === "readable"
          ? { reading: list.reading, source: list.reading_source }
          : undefined;
      }),
    )
    .toEqual({
      reading: { lane: "local_api", model: "synthetic-vision:1" },
      source: "default",
    });
  const picker = await openModelPicker(target);
  await expect(picker.getByLabel(label("desktop.agent.model"))).toHaveValue(
    "synthetic-vision:1",
  );
  // Showing it stores nothing: the default stays the service's answer.
  expect(
    await target.evaluate(async () => {
      const list = await window.__fixtureAgentSession?.localModels?.();
      return list?.state === "readable" ? list.reading_source : undefined;
    }),
  ).toBe("default");
});
