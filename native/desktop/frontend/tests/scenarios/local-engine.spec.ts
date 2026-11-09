import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The local engine and placement choice in the agent's settings: Ollama is
// the default and shows its lane alone; choosing llama.cpp stores the choice
// at the revision read and shows its lane instead. The scenario host stands
// in for the agent service.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const open = (target: Page) =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready`,
  );

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

async function openSettings(target: Page) {
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeVisible();
  await settings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
  return settings(target);
}

const engineGroup = (target: Page) =>
  settings(target).locator("[data-slot=local-engine-choice]");
const placementGroup = (target: Page) =>
  settings(target).locator("[data-slot=local-placement-choice]");
const modelRows = (target: Page, provider: string) =>
  settings(target).locator(
    `li[data-provider="${provider}"] [data-slot=local-models] li[data-model]`,
  );
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

test("the bundled llama.cpp is the default and shows its lane alone", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await expect(
    engineGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_engine_llamacpp"),
    }),
  ).toBeChecked();
  await expect(
    placementGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_placement_auto"),
    }),
  ).toBeChecked();
  await expect(modelRows(target, "llamacpp")).toHaveCount(1);
  await expect(modelRows(target, "ollama")).toHaveCount(0);
  await expect(
    settings(target).getByText(
      label("desktop.providers.local_engine_restarts"),
    ),
  ).toBeVisible();
});

test("choosing Ollama stores it at the revision read and shows its lane", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const read = await target.evaluate(async () => {
    const held = await window.__fixtureAgentSession?.localEngine?.();
    return held?.revision;
  });
  await engineGroup(target)
    .getByRole("radio", {
      name: label("desktop.providers.local_engine_ollama"),
    })
    .click();
  await expect(modelRows(target, "ollama")).toHaveCount(1);
  await expect(modelRows(target, "llamacpp")).toHaveCount(0);
  expect(await calls(target)).toContain(
    `agentLocalEngineChoose ollama auto ${read}`,
  );
  await expect(
    engineGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_engine_ollama"),
    }),
  ).toBeChecked();
});

test("the placement switches to the processor alone", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await placementGroup(target)
    .getByRole("radio", {
      name: label("desktop.providers.local_placement_cpu_only"),
    })
    .click();
  await expect(
    placementGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_placement_cpu_only"),
    }),
  ).toBeChecked();
  expect(
    (await calls(target)).some((call) =>
      call.startsWith("agentLocalEngineChoose llamacpp cpu_only "),
    ),
  ).toBe(true);
});

test("a change made first refuses the choice with its word", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  // The record moves under the window: its next change carries a stale
  // revision.
  await target.evaluate(async () => {
    const session = window.__fixtureAgentSession;
    const held = await session?.localModels?.();
    if (held) await session?.resetLocalModels?.(held.revision);
  });
  await engineGroup(target)
    .getByRole("radio", {
      name: label("desktop.providers.local_engine_ollama"),
    })
    .click();
  await expect(
    settings(target)
      .getByRole("alert")
      .filter({
        hasText: label(
          "desktop.providers.local_models_refused_revision_conflict",
        ),
      }),
  ).toBeVisible();
});
