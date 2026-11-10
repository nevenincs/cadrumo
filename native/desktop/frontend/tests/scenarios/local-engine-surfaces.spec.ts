import { expect, test, type Locator, type Page } from "@playwright/test";
import { agentColumn as column, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// A computer whose local AI program is set up and which holds no model. Two
// surfaces speak of the local AI, and each says which fact it states. The
// setup panel's local AI element states the program that runs the models,
// named as that, from the component setup. The provider settings state the
// lane's engine from what the agent serves of it: not running with its
// reason, running, or, where the agent measured none, only what the lane's
// settings say. Neither calls the lane unchecked while the agent serves its
// engine, and neither takes the other's word.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const DOWN = {
  engine: "llamacpp",
  state: "not_running",
  reason: "not_reachable",
  door: "local_ai_setup",
};
const UP = { engine: "llamacpp", state: "running", reason: null, door: null };

/** The lane's settings have verified nothing, as on a computer that holds no
 * model; the engine's health is what the agent serves of it. */
async function open(target: Page, health: unknown) {
  await target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&models=none&catalog=engines-only&engine_health=${encodeURIComponent(
      JSON.stringify({ llamacpp: health }),
    )}`,
  );
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.leaveLaneUnconfirmed("llamacpp_api", {
      readiness: "not_verified",
    });
  });
}

const setupPanel = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });
const localAiElement = (target: Page) =>
  setupPanel(target).locator('[data-setup-element="local_ai"]');

/** Opens the setup panel from the window's settings. */
async function openSetupPanel(target: Page) {
  await target.locator("[data-rail=settings]").click();
  await target
    .locator(".settings [data-settings-provisioning]")
    .getByRole("button", { name: label("desktop.setup.open"), exact: true })
    .click();
  await expect(setupPanel(target)).toBeVisible();
}

async function closeSetupPanel(target: Page) {
  await setupPanel(target)
    .getByLabel(label("desktop.setup.close"), { exact: true })
    .click();
  await expect(setupPanel(target)).toBeHidden();
}

const providerSettings = (target: Page) =>
  column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });

/** The lane row of the engine, in the agent's provider settings. */
async function laneRow(target: Page) {
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(providerSettings(target)).toBeVisible();
  await providerSettings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
  return providerSettings(target).locator('li[data-lane="llamacpp_api"]');
}

const status = (row: Locator) => row.locator("[data-slot=provider-status]");

const programFact = (sentence: string) =>
  label("desktop.compose.labelled", {
    label: label("desktop.setup.part_program"),
    value: sentence,
  });

test("the setup panel says its status is the program's, and the provider settings say the engine does not run", async ({
  page: target,
}) => {
  await open(target, DOWN);
  await openSetupPanel(target);
  // Closed, the element's status is the program's, named as that rather than
  // left to read as the whole local AI.
  const element = localAiElement(target);
  await expect(element.locator("[data-setup-sentence]")).toHaveText(
    programFact(label("desktop.setup.state.ready")),
  );
  // Open, the program row names its part and says the same state.
  await element
    .getByRole("button", { name: label("desktop.setup.item.local_ai") })
    .click();
  const program = element.locator('[data-setup-row="local_ai"]');
  await expect(
    program.getByRole("heading", { name: label("desktop.setup.part_program") }),
  ).toBeVisible();
  await expect(program.locator("[data-setup-sentence]")).toHaveText(
    label("desktop.setup.state.ready"),
  );
  await closeSetupPanel(target);

  // The same computer's lane states what the agent serves of its engine, with
  // its reason, and is not called unchecked.
  const row = await laneRow(target);
  await expect(status(row)).toHaveAttribute(
    "data-status",
    "engine_not_running",
  );
  await expect(row).toContainText(
    label("desktop.compose.noted", {
      text: label("desktop.agent.engine_not_running"),
      note: label("desktop.agent.engine_reason_not_reachable"),
    }),
  );
  await expect(row).not.toContainText(
    label("desktop.providers.status_not_checked"),
  );
});

test("a lane whose engine the agent serves as running is not called unchecked while its settings verified nothing", async ({
  page: target,
}) => {
  await open(target, UP);
  await openSetupPanel(target);
  await expect(
    localAiElement(target).locator("[data-setup-sentence]"),
  ).toHaveText(programFact(label("desktop.setup.state.ready")));
  await closeSetupPanel(target);

  const row = await laneRow(target);
  await expect(status(row)).toHaveAttribute("data-status", "ready");
  await expect(status(row)).toHaveText(label("desktop.providers.status_ready"));
  await expect(row).not.toContainText(
    label("desktop.providers.status_not_checked"),
  );
  await expect(row).not.toContainText(
    label("desktop.agent.engine_not_running"),
  );
});

test("a lane whose engine the agent did not measure says it was not checked", async ({
  page: target,
}) => {
  await open(target, null);
  const row = await laneRow(target);
  await expect(status(row)).toHaveAttribute("data-status", "not_checked");
  await expect(status(row)).toHaveText(
    label("desktop.providers.status_not_checked"),
  );
  await expect(row).not.toContainText(
    label("desktop.agent.engine_not_running"),
  );
});
