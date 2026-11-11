import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  openModelPicker,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// A keyless local lane whose engine the agent measured as not running: the
// lane row in the provider settings and the agent column's notice say it in
// the served words, with the reason, and offer the served door, which opens
// the provisioning panel on the local AI row. A running engine says nothing;
// a door the window does not know opens nothing and has no stand-in; an
// answer outside the contract states nothing. The scenario host stands in for
// the agent service.

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

const open = (target: Page, health?: object) =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&catalog=engines-only${
      health
        ? `&engine_health=${encodeURIComponent(JSON.stringify(health))}`
        : ""
    }`,
  );

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
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
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
  test(`${engine}: an engine that does not run is said on its lane row and in the column, with the door to the local AI setup`, async ({
    page: target,
  }) => {
    await open(target, bothDown());
    // No lane can run, so the column says why, once for each engine lane.
    await expect(notice(target, engine)).toContainText(
      noticed(engine, REASONS[engine]),
    );
    await expect(doors(notice(target, engine))).toHaveCount(1);
    await expect(
      column(target).getByText(label("desktop.agent.no_provider")),
    ).toHaveCount(0);

    await openSettings(target);
    const row = laneRow(target, engine);
    await expect(row).toContainText(stated(REASONS[engine]));
    await expect(
      row.locator(
        "[data-slot=provider-status][data-status=engine_not_running]",
      ),
    ).toHaveCount(1);
    await expect(doors(row)).toHaveCount(1);

    // The row door opens the setup panel on the local AI row.
    await doorButton(row).click();
    await expectLocalAiSetup(target);
    await setupPanel(target)
      .getByLabel(label("desktop.setup.close"), { exact: true })
      .click();
    await expect(setupPanel(target)).toBeHidden();
  });

  test(`${engine}: the door in the column opens the local AI setup row`, async ({
    page: target,
  }) => {
    await open(target, bothDown());
    await doorButton(notice(target, engine)).click();
    await expectLocalAiSetup(target);
  });
}

test("an engine that does not run holds its lane back before its transport, and the picker says it", async ({
  page: target,
}) => {
  await open(target, bothDown());
  const picker = await openModelPicker(target);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const lane = target.locator('[role=option][data-way="llamacpp/api"]');
  await expect(lane).toHaveAttribute("data-disabled", "true");
  await expect(lane).toContainText(stated(REASONS.llamacpp));
  await expect(lane).not.toContainText(label("desktop.agent.lane_unreachable"));
});

test("one engine that does not run leaves the other lane usable and the column quiet", async ({
  page: target,
}) => {
  await open(target, { llamacpp: down("llamacpp", "answer_unreadable") });
  // The ollama lane can run, so the column has nothing to say about the
  // engine that does not.
  await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
  await expect(
    column(target).getByText(label("desktop.agent.engine_not_running")),
  ).toHaveCount(0);
  await openSettings(target);
  await expect(laneRow(target, "llamacpp")).toContainText(
    stated("answer_unreadable"),
  );
  await expect(doors(laneRow(target, "llamacpp"))).toHaveCount(1);
  // The other engine states it runs: its row says nothing of the engine.
  await expect(laneRow(target, "ollama")).not.toContainText(
    label("desktop.agent.engine_not_running"),
  );
  await expect(doors(laneRow(target, "ollama"))).toHaveCount(0);
});

test("a running engine says nothing on its row or in the column", async ({
  page: target,
}) => {
  await open(target);
  await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
  await expect(
    column(target).getByText(label("desktop.agent.engine_not_running")),
  ).toHaveCount(0);
  await openSettings(target);
  for (const engine of ENGINES) {
    await expect(laneRow(target, engine)).not.toContainText(
      label("desktop.agent.engine_not_running"),
    );
    await expect(doors(laneRow(target, engine))).toHaveCount(0);
  }
});

test("a door the window does not know renders no door and no stand-in", async ({
  page: target,
}) => {
  await open(target, bothDown("elsewhere"));
  for (const engine of ENGINES)
    await expect(notice(target, engine)).toContainText(
      noticed(engine, REASONS[engine]),
    );
  await expect(notice(target, "llamacpp").getByRole("button")).toHaveCount(0);
  await openSettings(target);
  await expect(laneRow(target, "llamacpp")).toContainText(
    stated(REASONS.llamacpp),
  );
  await expect(doors(column(target))).toHaveCount(0);
  await expect(
    laneRow(target, "llamacpp").getByRole("button", {
      name: label("desktop.setup.open"),
    }),
  ).toHaveCount(0);
});

test("an answer outside the contract states nothing", async ({
  page: target,
}) => {
  // A reason the contract does not name, and a running engine that names one.
  await open(target, {
    llamacpp: down("llamacpp", "unplugged"),
    ollama: {
      engine: "ollama",
      state: "running",
      reason: "not_reachable",
      door: null,
    },
  });
  await expect(column(target).locator("[data-engine-notice]")).toHaveCount(0);
  await openSettings(target);
  for (const engine of ENGINES) {
    await expect(laneRow(target, engine)).not.toContainText(
      label("desktop.agent.engine_not_running"),
    );
    await expect(doors(laneRow(target, engine))).toHaveCount(0);
  }
});

// A way that takes no key is a server on this computer: it is named as that
// and offers no key to add, on either engine's lane.
for (const engine of ENGINES) {
  test(`${engine}: the keyless lane is not called a key connection and offers no key`, async ({
    page: target,
  }) => {
    await open(target);
    await openSettings(target);
    const row = laneRow(target, engine);
    await expect(
      // Exact: the lane's model list is headed "Models on this computer".
      row.getByRole("heading", {
        name: label("desktop.providers.connection_local"),
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      settings(target).locator(`[data-lane-summary="${engine}_api"]`),
    ).toContainText(label("desktop.providers.connection_local"));
    await expect(row).not.toContainText(
      label("desktop.providers.connection_api"),
    );
    await expect(
      row.getByRole("button", { name: label("desktop.providers.add_key") }),
    ).toHaveCount(0);
    await expect(row.locator("input[type=password]")).toHaveCount(0);
  });
}
