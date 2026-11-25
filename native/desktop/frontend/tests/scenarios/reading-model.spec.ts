import { expect, test, type Page } from "@playwright/test";
import {
  matrixCell,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";

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
    return list?.unreadable === false ? list.reading : undefined;
  });

test("the model picked in the agent column is the one documents are read with, on any lane", async ({
  page: target,
}) => {
  await open(target);
  // Nothing is stored for reading until the person picks.
  expect(await storedReading(target)).toBeNull();
  let picker = await openModelPicker(target);
  await pickWay(target, picker, "qwen/cli");
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  await expect
    .poll(() => storedReading(target))
    .toMatchObject({ lane: "qwen_cli" });
  picker = await openModelPicker(target);
  await pickWay(target, picker, "zai/api");
  const vision = matrixCell(picker, "zai/api", "synthetic-vision:1");
  // The lane starts on another model, so the store changes only by the pick.
  await expect(vision).toHaveAttribute("aria-checked", "false");
  await expect
    .poll(() => storedReading(target))
    .toMatchObject({ lane: "zai_api" });
  expect(await storedReading(target)).not.toEqual({
    lane: "zai_api",
    model: "synthetic-vision:1",
  });
  await vision.click();
  await expect(vision).toHaveAttribute("aria-checked", "true");
  await expect
    .poll(() => storedReading(target))
    .toEqual({ lane: "zai_api", model: "synthetic-vision:1" });
});

test("on a fresh profile the picker shows the installed model the service reads documents with, without a pick", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&models=all&reading_default=zai_api:synthetic-vision:1",
  );
  // Nothing is stored: the service serves its installed default.
  await expect
    .poll(() =>
      target.evaluate(async () => {
        const list = await window.__fixtureAgentSession?.localModels?.();
        return list?.unreadable === false
          ? { reading: list.reading, source: list.reading_source }
          : undefined;
      }),
    )
    .toEqual({
      reading: { lane: "zai_api", model: "synthetic-vision:1" },
      source: "default",
    });
  const picker = await openModelPicker(target);
  await expect(
    matrixCell(picker, "zai/api", "synthetic-vision:1"),
  ).toHaveAttribute("aria-checked", "true");
  // Showing it stores nothing: the default stays the service's answer.
  expect(
    await target.evaluate(async () => {
      const list = await window.__fixtureAgentSession?.localModels?.();
      return list?.unreadable === false ? list.reading_source : undefined;
    }),
  ).toBe("default");
});
