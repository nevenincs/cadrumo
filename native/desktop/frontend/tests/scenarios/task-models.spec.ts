import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  laneModelsNote,
  laneModelsWords,
  matrixCell,
  matrixLane,
  matrixRows,
  scenarioOnly,
  worded,
} from "../support/agent";
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

const runsWith = (target: Page, kind: string) =>
  row(target, kind).locator("[data-slot=task-model-runs-with]");

const effortOf = (target: Page, kind: string) =>
  row(target, kind).locator("[data-slot=task-model-effort]");

type Kind = (typeof FIXTURE_CATALOG.task_kinds)[number];

/** A kind's name and description in the window's own words: the agent
 * serves them in English only, and the window says the kinds it knows in its
 * language. */
const taskName = (kind: Kind) =>
  label(`desktop.providers.task_kind_${kind.id}`);
const taskDescription = (kind: Kind) =>
  label(`desktop.providers.task_kind_${kind.id}_description`);

const changeButton = (target: Page, kind: Kind) =>
  row(target, kind.id).getByRole("button", {
    name: label("desktop.providers.task_model_change_label", {
      task: taskName(kind),
    }),
  });

/** Opens the one model matrix a kind's Change button shows, and answers it
 * once shown. */
async function openChange(target: Page, kind: Kind): Promise<Locator> {
  await changeButton(target, kind).click();
  const chooser = target.getByRole("dialog", {
    name: label("desktop.providers.task_model_model", {
      task: taskName(kind),
    }),
  });
  await expect(chooser).toBeVisible();
  return chooser;
}

const useReading = (chooser: Locator) =>
  chooser.getByRole("button", {
    name: label("desktop.providers.task_model_use_reading"),
  });

/** The words a task on the reading model runs with, whichever way the
 * reading model stands. */
const readingWords = new RegExp(
  [
    "desktop.providers.task_model_reading_chosen",
    "desktop.providers.task_model_reading_default",
    "desktop.providers.task_model_reading_none",
  ]
    .map((key) => worded(key).source)
    .join("|"),
);

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
    await expect(runsWith(target, kind.id)).toHaveText(readingWords);
    await expect(effortOf(target, kind.id)).toHaveText(
      label("desktop.agent.effort_provider_default"),
    );
    await expect(row(target, kind.id).getByRole("rowheader")).toContainText(
      taskName(kind),
    );
    await expect(row(target, kind.id)).toContainText(taskDescription(kind));
    // The served English words stand in for no kind the window knows.
    await expect(row(target, kind.id)).not.toContainText(kind.display_name);
  }
  expect(await storedTasks(target)).toEqual([]);

  const [first] = kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  const classification = row(target, first.id);
  const reading = (await runsWith(target, first.id).textContent()) ?? "";
  const chooser = await openChange(target, first);
  await expect(useReading(chooser)).toHaveAttribute("aria-pressed", "true");

  // A lane whose background requests take no effort offers none.
  const coder = matrixRows(chooser, "qwen/api").and(
    chooser.locator('[data-model="fixture-coder"]'),
  );
  await expect(coder.getByRole("radio")).toHaveCount(1);
  await matrixCell(chooser, "qwen/api", "fixture-coder").click();
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
  await expect(
    matrixCell(chooser, "qwen/api", "fixture-coder"),
  ).toHaveAttribute("aria-checked", "true");
  await expect(useReading(chooser)).toHaveAttribute("aria-pressed", "false");
  await expect(runsWith(target, first.id)).toContainText("Fixture Coder");
  await expect(effortOf(target, first.id)).toHaveText(
    label("desktop.agent.effort_provider_default"),
  );

  // A lane that takes one offers the levels the model states.
  const quick = matrixRows(chooser, "kimi/api").and(
    chooser.locator('[data-model="fixture-quick"]'),
  );
  expect(
    await quick
      .getByRole("radio")
      .evaluateAll((cells) =>
        cells.map((cell) => cell.getAttribute("data-column")),
      ),
  ).toEqual(["default", "low", "medium"]);
  await matrixCell(chooser, "kimi/api", "fixture-quick", "medium").click();
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
  await expect(
    matrixCell(chooser, "kimi/api", "fixture-quick", "medium"),
  ).toHaveAttribute("aria-checked", "true");
  await expect(
    matrixCell(chooser, "qwen/api", "fixture-coder"),
  ).toHaveAttribute("aria-checked", "false");
  await expect(runsWith(target, first.id)).toContainText("Fixture Quick");
  await expect(effortOf(target, first.id)).toHaveText(
    label("desktop.agent.effort_medium"),
  );
  // The other kind still uses the reading model.
  const [, second] = kinds;
  if (second) await expect(runsWith(target, second.id)).toHaveText(reading);

  // Back to the default: the setting is cleared and no effort is set.
  await useReading(chooser).click();
  await expect.poll(() => storedTasks(target)).toEqual([]);
  await expect(useReading(chooser)).toHaveAttribute("aria-pressed", "true");
  await expect(
    chooser.locator("[role=radio][data-matrix-cell][aria-checked=true]"),
  ).toHaveCount(0);
  await expect(runsWith(target, first.id)).toHaveText(reading);
  await expect(effortOf(target, first.id)).toHaveText(
    label("desktop.agent.effort_provider_default"),
  );
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
  const chooser = await openChange(target, first);
  const chat = matrixCell(chooser, "qwen/api", "fixture-chat");
  await chat.click();
  await expect(row(target, first.id).getByRole("alert")).toHaveText(
    label("desktop.providers.local_models_refused_revision_conflict"),
  );
  expect(await storedTasks(target)).toEqual([]);
  await expect(chat).toHaveAttribute("aria-checked", "false");
  await expect(useReading(chooser)).toHaveAttribute("aria-pressed", "true");
});

const openSettings = async (target: Page) => {
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(section(target)).toBeVisible();
};

test("a record of the lists that cannot be read says why and offers the reset, after which a model can be set", async ({
  page: target,
}) => {
  await target.addInitScript(() => {
    // The record stays unreadable until the person resets it.
    window.__fixtureLocalModelsRead = async () => {
      if (
        (window.__scenarioHostCalls ?? []).some((call) =>
          call.startsWith("agentLocalModelsReset"),
        )
      )
        return;
      return {
        unreadable: true,
        models: [],
        reading: null,
        reading_source: "none",
        tasks: [],
        local_lanes: [],
        revision: "0".repeat(64),
      };
    };
  });
  await open(target);
  await openSettings(target);
  const said = section(target).locator("[data-slot=task-models-unreadable]");
  await expect(said.getByRole("alert")).toHaveText(
    label("desktop.providers.local_models_unreadable"),
  );
  const [first] = kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  const change = changeButton(target, first);
  await expect(change).toBeDisabled();
  await said
    .getByRole("button", {
      name: label("desktop.providers.local_models_reset"),
    })
    .click();
  await expect(said).toHaveCount(0);
  await expect(change).toBeEnabled();
});

test("model lists that answer where setup stands are said as that state, with asking again where that helps", async ({
  page: target,
}) => {
  await target.addInitScript(() => {
    window.__taskListsRefused = true;
    window.__fixtureLocalModelsRead = async () => {
      if (!window.__taskListsRefused) return;
      throw Object.assign(new Error("agent_local_models_catalog_unavailable"), {
        code: "agent_local_models_catalog_unavailable",
      });
    };
  });
  await open(target);
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const said = section(target).locator("[data-slot=task-models-lists]");
  await expect(said).toHaveAttribute("role", "status");
  await expect(said).toContainText(label("desktop.agent.catalog_unavailable"));
  await target.evaluate(() => {
    window.__taskListsRefused = false;
  });
  await said
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect(said).toHaveCount(0);
  await expect(section(target).locator("[data-task-kind]")).toHaveCount(
    kinds.length,
  );
});

test("a lane a task cannot run on yet says why with the picker's step, and a model not on this computer cannot be set", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&models=none&catalog=hosted-signed-out",
  );
  await openSettings(target);
  const [first] = kinds;
  if (!first) throw new Error("The made-up catalogue serves no task kind.");
  let chooser = await openChange(target, first);
  // The local lane holds none of its models yet: downloading one is the step.
  const local = matrixLane(chooser, "zai/api");
  await expect(local.locator("[data-slot=model-matrix-lane-words]")).toHaveText(
    label("desktop.agent.lane_no_installed_model"),
  );
  // A signed-out lane is signed in to in its provider's settings.
  const signedOut = matrixLane(chooser, "kimi/cli");
  await expect(
    signedOut.locator("[data-slot=model-matrix-lane-words]"),
  ).toHaveText(label("desktop.agent.lane_signed_out"));

  // Neither lane offers a model to set: each counts its models under its
  // heading, with no row or cell to press.
  for (const way of ["zai/api", "kimi/cli"]) {
    await expect(matrixRows(chooser, way)).toHaveCount(0);
    await expect(matrixLane(chooser, way).locator("[role=radio]")).toHaveCount(
      0,
    );
  }
  await expect(laneModelsNote(chooser, "zai/api")).toHaveText(laneModelsWords);

  const providerExpander = (provider: string) =>
    target
      .locator(".pane-agent")
      .locator(`li[data-provider="${provider}"]`)
      .first()
      .locator("[data-slot=lane-expander]");
  await expect(providerExpander("kimi")).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await signedOut
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  await expect(chooser).toBeHidden();
  await expect(providerExpander("kimi")).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  chooser = await openChange(target, first);
  await matrixLane(chooser, "zai/api")
    .getByRole("button", { name: label("desktop.agent.download_models") })
    .click();
  await expect(chooser).toBeHidden();
  await expect(providerExpander("zai")).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(
    target
      .locator(".pane-agent")
      .locator('li[data-provider="zai"] [data-slot=local-models]')
      .first(),
  ).toBeInViewport();
});

declare global {
  interface Window {
    /** Whether the made-up list read refuses, while set. */
    __taskListsRefused?: boolean;
  }
}
