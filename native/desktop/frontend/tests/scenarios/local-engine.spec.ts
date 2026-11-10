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

// The engines and placements offered are the ones the service serves, in its
// order; a token the window has no words for is offered as nothing.

const openServed = (target: Page, choices: string) =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&${choices}`,
  );
const offered = (group: ReturnType<typeof engineGroup>) =>
  group
    .locator("[data-choice]")
    .evaluateAll((nodes) =>
      nodes.map((node) => (node as HTMLElement).dataset.choice),
    );

test("every engine and placement the service offers is a choice, in its order", async ({
  page: target,
}) => {
  await openServed(
    target,
    "engine_choices=ollama,llamacpp&placement_choices=cpu_only,auto",
  );
  await openSettings(target);
  expect(await offered(engineGroup(target))).toEqual(["ollama", "llamacpp"]);
  expect(await offered(placementGroup(target))).toEqual(["cpu_only", "auto"]);
});

test("a single engine and a single placement are offered as that one choice", async ({
  page: target,
}) => {
  await openServed(target, "engine_choices=ollama&placement_choices=cpu_only");
  await openSettings(target);
  expect(await offered(engineGroup(target))).toEqual(["ollama"]);
  expect(await offered(placementGroup(target))).toEqual(["cpu_only"]);
  await expect(
    engineGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_engine_ollama"),
    }),
  ).toBeVisible();
  await expect(
    engineGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_engine_llamacpp"),
    }),
  ).toHaveCount(0);
  await expect(
    placementGroup(target).getByRole("radio", {
      name: label("desktop.providers.local_placement_auto"),
    }),
  ).toHaveCount(0);
});

test("a token the window has no words for is offered as nothing", async ({
  page: target,
}) => {
  await openServed(
    target,
    "engine_choices=llamacpp,vllm&placement_choices=auto,gpu",
  );
  await openSettings(target);
  expect(await offered(engineGroup(target))).toEqual(["llamacpp"]);
  expect(await offered(placementGroup(target))).toEqual(["auto"]);
  // No stand-in is offered for the token it does not know.
  await expect(engineGroup(target).getByRole("radio")).toHaveCount(1);
  await expect(placementGroup(target).getByRole("radio")).toHaveCount(1);
});

test("a choice among the served ones is sent as that token", async ({
  page: target,
}) => {
  await openServed(
    target,
    "engine_choices=llamacpp,ollama&placement_choices=auto,cpu_only",
  );
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
  await expect
    .poll(async () => await calls(target))
    .toContain(`agentLocalEngineChoose ollama auto ${read}`);
});
