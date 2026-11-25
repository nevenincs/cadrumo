import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  laneModelsNote,
  laneModelsWords,
  matrixLane,
  matrixRows,
  openModelPicker,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// A keyless local lane whose engine the agent measured as not running: the
// agent column's notice and the picker say it in the served words, with the
// reason, and the notice offers the served door, which opens the provisioning
// panel on the local AI row. The lane row in the provider settings shows the
// local AI's setup row as the setup host serves it, already combined from the
// engine's server and its last start, and offers no engine door of its own. A
// running engine says nothing, and an answer that pairs its fields outside
// the contract states nothing. The
// service serves the keyless lane of the selected engine alone, so each
// engine's case starts the window on that engine. The scenario host stands in
// for the agent service.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const ENGINES = ["llamacpp", "ollama"] as const;
type Engine = (typeof ENGINES)[number];

const down = (engine: Engine, reason: string, door = "local_ai_setup") => ({
  engine,
  state: "not_running",
  reason,
  door,
});
const REASONS: Record<Engine, string> = {
  llamacpp: "not_reachable",
  ollama: "no_answer_in_time",
};
const bothDown = (door = "local_ai_setup") => ({
  llamacpp: down("llamacpp", REASONS.llamacpp, door),
  ollama: down("ollama", REASONS.ollama, door),
});

const nameOf = (engine: Engine) =>
  (FIXTURE_CATALOG.providers ?? []).find(
    (lane) => lane.provider_id === engine && lane.transport === "api",
  )!.display_name;

/** What the lane and the notice say of an engine that does not run. */
const stated = (reason: string) =>
  label("desktop.compose.noted", {
    text: label("desktop.agent.engine_not_running"),
    note: label(`desktop.agent.engine_reason_${reason}`),
  });
const noticed = (engine: Engine, reason: string) =>
  label("desktop.compose.labelled", {
    label: nameOf(engine),
    value: stated(reason),
  });

/** The local AI's setup row whose server failed the start a read demanded,
 * as the setup host serves it beside an engine that does not run. */
const START_FAILED = "start_failed";
const startFailed = () => label("desktop.setup.failure.program_not_running");

async function open(
  target: Page,
  health?: object,
  {
    engine = "llamacpp",
    setup = "ready",
    catalog = "engines-only",
  }: { engine?: Engine; setup?: string; catalog?: string } = {},
) {
  await target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=${setup}&catalog=${catalog}&engine=${engine}${
      health
        ? `&engine_health=${encodeURIComponent(JSON.stringify(health))}`
        : ""
    }`,
  );
  // A local AI that is not ready opens the setup panel at the start; the
  // column is reached once it is closed.
  if (setup !== "ready") {
    await expect(setupPanel(target)).toBeVisible();
    await setupPanel(target)
      .getByLabel(label("desktop.setup.close"), { exact: true })
      .click();
    await expect(setupPanel(target)).toBeHidden();
  }
}

const settings = (target: Page) =>
  column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });

async function openSettings(target: Page) {
  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeVisible();
  await settings(target)
    .locator("[data-slot=lane-expander][aria-expanded=false]")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => (node as HTMLElement).click()),
    );
}

const laneRow = (target: Page, engine: Engine) =>
  settings(target).locator(`li[data-lane="${engine}_api"]`);
const notice = (target: Page, engine: Engine) =>
  column(target).locator(`[data-engine-notice="${engine}/api"]`);
const doors = (scope: ReturnType<typeof column>) =>
  scope.locator("[data-engine-door]");
const doorButton = (scope: ReturnType<typeof column>) =>
  scope.getByRole("button", {
    name: label("desktop.agent.engine_door_local_ai_setup"),
    exact: true,
  });
const setupPanel = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });

/** The picker holds the engine's lane back, says `words` for it rather
 * than that its transport is unreachable, and offers none of its models:
 * they are counted under its heading, not listed as rows to choose. */
async function expectHeldInPicker(picker: Locator, way: string, words: string) {
  const lane = matrixLane(picker, way);
  await expect(lane).toHaveAttribute("data-standing", "setup");
  await expect(lane).toContainText(words);
  await expect(lane).not.toContainText(label("desktop.agent.lane_unreachable"));
  await expect(laneModelsNote(picker, way)).toHaveText(laneModelsWords);
  await expect(matrixRows(picker, way)).toHaveCount(0);
  await expect(lane.locator("[role=radio]")).toHaveCount(0);
}

/** The door led to the provisioning panel, opened on the local AI row. */
async function expectLocalAiSetup(target: Page) {
  await expect(setupPanel(target)).toBeVisible();
  await expect(
    setupPanel(target).locator('[data-setup-element="local_ai"]'),
  ).toBeVisible();
  await expect(
    setupPanel(target).locator('[data-setup-row="local_ai"]'),
  ).toBeVisible();
}

for (const engine of ENGINES) {
  test(`${engine}: an engine that does not run is said in the column with the door to the local AI setup, and its lane row shows the served setup row`, async ({
    page: target,
  }) => {
    await open(target, bothDown(), { engine, setup: START_FAILED });
    // No lane can run, so the column says why, for the engine's lane.
    await expect(notice(target, engine)).toContainText(
      noticed(engine, REASONS[engine]),
    );
    await expect(doors(notice(target, engine))).toHaveCount(1);
    await expect(
      column(target).getByText(label("desktop.agent.no_provider")),
    ).toHaveCount(0);

    // The lane row says the setup row in the setup's words and is not set up
    // while that row is not ready; the engine's door is the column's.
    await openSettings(target);
    const row = laneRow(target, engine);
    await expect(row).toContainText(startFailed());
    await expect(
      row.locator("[data-slot=provider-status][data-status=setup_needed]"),
    ).toHaveCount(1);
    await expect(row).not.toContainText(
      label("desktop.agent.engine_not_running"),
    );
    await expect(doors(row)).toHaveCount(0);
  });

  test(`${engine}: the door in the column opens the local AI setup row`, async ({
    page: target,
  }) => {
    await open(target, bothDown(), { engine });
    await doorButton(notice(target, engine)).click();
    await expectLocalAiSetup(target);
  });
}

test("an engine that does not run holds its lane back before its transport, and the picker says it", async ({
  page: target,
}) => {
  await open(target, bothDown());
  const picker = await openModelPicker(target);
  await expectHeldInPicker(picker, "llamacpp/api", stated(REASONS.llamacpp));
});

test("an engine that does not run leaves the other lanes usable and the column quiet", async ({
  page: target,
}) => {
  await open(
    target,
    { llamacpp: down("llamacpp", "answer_unreadable") },
    { setup: START_FAILED, catalog: "served" },
  );
  // Other lanes can run, so the column has nothing to say about the engine
  // that does not.
  await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
  await expect(
    column(target).getByText(label("desktop.agent.engine_not_running")),
  ).toHaveCount(0);
  // The picker holds the engine's lane back and says why.
  const picker = await openModelPicker(target);
  await expectHeldInPicker(picker, "llamacpp/api", stated("answer_unreadable"));
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  // Its lane row shows the served setup row, with no engine door.
  await openSettings(target);
  await expect(laneRow(target, "llamacpp")).toContainText(startFailed());
  await expect(doors(laneRow(target, "llamacpp"))).toHaveCount(0);
});

for (const engine of ENGINES)
  test(`${engine}: a running engine says nothing on its row or in the column`, async ({
    page: target,
  }) => {
    await open(target, undefined, { engine });
    await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
    await expect(
      column(target).getByText(label("desktop.agent.engine_not_running")),
    ).toHaveCount(0);
    await openSettings(target);
    await expect(laneRow(target, engine)).toBeVisible();
    await expect(laneRow(target, engine)).not.toContainText(
      label("desktop.agent.engine_not_running"),
    );
    await expect(doors(laneRow(target, engine))).toHaveCount(0);
  });

for (const engine of ENGINES)
  test(`${engine}: an answer outside the contract states nothing`, async ({
    page: target,
  }) => {
    // An engine that does not run and names no door, and a running engine
    // that names a reason: the schema admits each field, not the pairing.
    await open(
      target,
      {
        llamacpp: { ...down("llamacpp", REASONS.llamacpp), door: null },
        ollama: {
          engine: "ollama",
          state: "running",
          reason: "not_reachable",
          door: null,
        },
      },
      { engine },
    );
    await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
    await openSettings(target);
    await expect(laneRow(target, engine)).toBeVisible();
    await expect(laneRow(target, engine)).not.toContainText(
      label("desktop.agent.engine_not_running"),
    );
    await expect(doors(laneRow(target, engine))).toHaveCount(0);
  });

// A way that takes no key is a server on this computer: it is named as that
// and offers no key to add, on either engine's lane.
for (const engine of ENGINES) {
  test(`${engine}: the keyless lane is not called a key connection and offers no key`, async ({
    page: target,
  }) => {
    await open(target, undefined, { engine });
    await openSettings(target);
    const row = laneRow(target, engine);
    // The row is named for its provider and the way it connects.
    await expect(row.getByRole("heading", { level: 4 })).toHaveText(
      new RegExp(` · ${label("desktop.providers.connection_local")}$`),
    );
    await expect(row).not.toContainText(
      label("desktop.providers.connection_api"),
    );
    await expect(
      row.getByRole("button", { name: label("desktop.providers.add_key") }),
    ).toHaveCount(0);
    await expect(row.locator("input[type=password]")).toHaveCount(0);
  });
}
