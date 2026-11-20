import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// What each kind of background task runs with, set in the agent's settings:
// every kind the catalogue serves starts on the model documents are read
// with, a model on a lane can be set instead, with an effort where the lane
// takes one for that model, and each change is stored and said.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");

const section = (target: Page) =>
  target
    .locator(".pane-agent details")
    .filter({ hasText: label("desktop.providers.task_models_title") });

const row = (target: Page, kind: string) =>
  section(target).locator(`[data-task-kind="${kind}"]`);

/** The settings the made-up service stores per kind. */
const storedTasks = (target: Page) =>
  target.evaluate(async () => {
    const list = await window.__fixtureAgentSession?.localModels?.();
    return list?.unreadable === false ? list.tasks : undefined;
  });

const kinds = FIXTURE_CATALOG.task_kinds;

test("each served task kind uses the reading model until a model and effort are set, and clearing it returns there", async ({
  page: target,
}) => {
  await open(target);
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(section(target)).toBeVisible();
  // One row per kind the catalogue serves, in its order, each on the default.
  await expect(section(target).locator("[data-task-kind]")).toHaveCount(
    kinds.length,
  );
  for (const kind of kinds) {
    const model = row(target, kind.id).getByLabel(
      label("desktop.providers.task_model_model", { task: kind.display_name }),
    );
    await expect(model).toHaveValue("");
    await expect(model.locator("option:checked")).toHaveText(
      label("desktop.providers.task_model_reading"),
    );
    await expect(row(target, kind.id)).toContainText(kind.description);
  }
  expect(await storedTasks(target)).toEqual([]);

  const [first] = kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  const classification = row(target, first.id);
  const model = classification.getByLabel(
    label("desktop.providers.task_model_model", { task: first.display_name }),
  );
  const effort = classification.getByLabel(
    label("desktop.providers.task_model_effort", { task: first.display_name }),
  );
  // A lane whose background requests take no effort offers none.
  await model.selectOption("qwen_api\nfixture-coder");
  await expect
    .poll(() => storedTasks(target))
    .toEqual([
      {
        task_kind: first.id,
        lane: "qwen_api",
        model: "fixture-coder",
        effort: null,
      },
    ]);
  await expect(classification.getByRole("status")).toHaveText(
    label("desktop.providers.task_model_saved"),
  );
  await expect(effort).toHaveCount(0);

  // A lane that takes one offers the levels the model states.
  await model.selectOption("kimi_api\nfixture-quick");
  await expect(effort).toBeVisible();
  await expect(effort.locator("option")).toHaveText([
    label("desktop.agent.effort_default"),
    label("desktop.agent.effort_low"),
    label("desktop.agent.effort_medium"),
  ]);
  await effort.selectOption("medium");
  await expect
    .poll(() => storedTasks(target))
    .toEqual([
      {
        task_kind: first.id,
        lane: "kimi_api",
        model: "fixture-quick",
        effort: "medium",
      },
    ]);
  // The other kind still uses the reading model.
  const [, second] = kinds;
  if (second)
    await expect(
      row(target, second.id).getByLabel(
        label("desktop.providers.task_model_model", {
          task: second.display_name,
        }),
      ),
    ).toHaveValue("");

  // Back to the default: the setting is cleared and no effort is offered.
  await model.selectOption("");
  await expect.poll(() => storedTasks(target)).toEqual([]);
  await expect(effort).toHaveCount(0);
  await expect(classification.getByRole("status")).toHaveText(
    label("desktop.providers.task_model_saved"),
  );
});

test("a refused change says so and leaves the stored setting", async ({
  page: target,
}) => {
  await open(target);
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const [first] = kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  // Another change moves the revision the settings read.
  await target.evaluate(async () => {
    const session = window.__fixtureAgentSession;
    const list = await session?.localModels?.();
    if (list)
      await session?.addLocalModel?.(
        "zai_api",
        "synthetic-named:test",
        list.revision,
      );
  });
  await row(target, first.id)
    .getByLabel(
      label("desktop.providers.task_model_model", { task: first.display_name }),
    )
    .selectOption("qwen_api\nfixture-chat");
  await expect(row(target, first.id).getByRole("alert")).toHaveText(
    label("desktop.providers.local_models_refused_revision_conflict"),
  );
  expect(await storedTasks(target)).toEqual([]);
});
