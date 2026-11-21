import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// A fresh profile on a package that carries the local AI's program, as the
// bundled llama.cpp does, with no model downloaded yet. The host serves the
// local AI as absent with its program set up and a model awaited, and the
// bundled engine as the package default nobody chose. The setup panel says
// the program is ready and that a model download remains, closed and open
// alike, and the engine choice shows the bundled engine selected. Once an
// earlier download stored a model, the host serves the local AI as ready, and
// the panel asks for no download.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the desktop host.");
});

const open = (target: Page) =>
  target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=model_needed",
  );

const panel = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });
const localAi = (target: Page) =>
  panel(target).locator('[data-setup-element="local_ai"]');

/** The program's sentence as the panel words it, with its label. */
const programSentence = (sentence: string) =>
  label("desktop.compose.labelled", {
    label: label("desktop.setup.part_program"),
    value: sentence,
  });

test("the closed local AI says its program is ready and a model download remains", async ({
  page: target,
}) => {
  await open(target);
  const element = localAi(target);
  await expect(element).toBeVisible();
  await expect(element.locator("[data-setup-sentence]")).toHaveText(
    programSentence(label("desktop.setup.awaits_model")),
  );
  await expect(element).not.toContainText(label("desktop.setup.state.absent"));
  // Nothing here sets the program up: the model list offers the download.
  await expect(
    element.getByRole("button", { name: label("desktop.setup.action.set_up") }),
  ).toHaveCount(0);
});

test("the open local AI says the same and shows the bundled engine selected", async ({
  page: target,
}) => {
  await open(target);
  const element = localAi(target);
  await element
    .getByRole("button", {
      name: label("desktop.setup.item.local_ai"),
      exact: true,
    })
    .click();
  await expect(
    element
      .locator('[data-setup-row="local_ai"]')
      .getByText(label("desktop.setup.awaits_model")),
  ).toBeVisible();
  const engines = element.locator("[data-slot=local-engine-choice]");
  const bundled = engines.getByRole("radio", {
    name: label("desktop.providers.local_engine_llamacpp"),
  });
  await expect(bundled).toBeChecked();
  await expect(bundled).toHaveAttribute("aria-checked", "true");
  await expect(
    engines.getByRole("radio", {
      name: label("desktop.providers.local_engine_ollama"),
    }),
  ).toHaveAttribute("aria-checked", "false");
  // The served setting is the package default, not a choice the person made.
  const served = await target.evaluate(async () => {
    const held = await window.__fixtureAgentSession?.localEngine?.();
    return held ? { chosen: held.chosen, engine: held.engine } : null;
  });
  expect(served).toEqual({ chosen: false, engine: "llamacpp" });
});

test("with a model already stored the local AI reads ready and asks for no download", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=model_stored",
  );
  // Everything is set up, so the panel stays closed until asked for.
  await expect(panel(target)).toHaveCount(0);
  const item = label("desktop.setup.palette_item", {
    name: label("desktop.setup.item.local_ai"),
  });
  await target.keyboard.press("Control+KeyK");
  await target
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(item);
  await target.getByRole("listbox").getByRole("option", { name: item }).click();
  const element = localAi(target);
  const toggle = element.getByRole("button", {
    name: label("desktop.setup.item.local_ai"),
    exact: true,
  });
  await expect(toggle).toBeVisible();
  if ((await toggle.getAttribute("aria-expanded")) === "true")
    await toggle.click();
  await expect(element.locator("[data-setup-sentence]")).toHaveText(
    programSentence(label("desktop.setup.ready_dormant")),
  );
  await expect(element).not.toContainText(label("desktop.setup.awaits_model"));
  await expect(element).not.toContainText(label("desktop.setup.state.absent"));
});
