import { expect, test, type Page } from "@playwright/test";
import { servedCatalogFor } from "../../src/dev/fixtures/agentCatalog";
import { FIXTURE_ENGINES } from "../../src/dev/fixtures/localEngineRecord";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";
import type { AgentLocalEngineToken } from "../../src/ipc/contract";
import { agentColumn as column, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The service serves one lane set for the engine its record selects, and the
// window shows what it is served: the agent's picker, the provider settings
// and the local AI's setup list the same lanes, the selected engine's keyless
// lane among them and the other engine's in none. What each surface should
// show is read from the lists the scenario host serves for the engine, so the
// check holds whatever the window would filter.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const KEYLESS = new Set(
  FIXTURE_SETTINGS_LANES.filter((seed) => seed.auth_kind === "none").map(
    (seed) => seed.id,
  ),
);

/** Every lane of the made-up catalogue, whichever engine is selected. */
const CATALOGUED = new Set(
  FIXTURE_ENGINES.flatMap((engine) =>
    (servedCatalogFor(engine).providers ?? []).map(
      (lane) => `${lane.provider_id}_${lane.transport}`,
    ),
  ),
);

/** What the host serves for `engine`, by catalogue lane id, in order. */
function served(engine: AgentLocalEngineToken) {
  const lanes = servedCatalogFor(engine).providers ?? [];
  const ids = lanes.map((lane) => `${lane.provider_id}_${lane.transport}`);
  const keyless = lanes.filter((lane) =>
    KEYLESS.has(`${lane.provider_id}_${lane.transport}`),
  );
  return {
    ids,
    keyless: keyless.map((lane) => `${lane.provider_id}_${lane.transport}`),
    // The models a keyless lane's list starts with: those it recommends.
    listed: [
      ...new Set(
        keyless.flatMap((lane) =>
          Object.values(lane.catalog.recommended ?? {}),
        ),
      ),
    ].sort(),
  };
}

const other = (engine: AgentLocalEngineToken) =>
  FIXTURE_ENGINES.find((held) => held !== engine)!;

const open = (target: Page, engine: string, setup = "ready") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=${setup}&engine=${engine}`,
  );

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The lanes the agent's picker offers, as catalogue lane ids. */
async function pickerLanes(target: Page): Promise<string[]> {
  await column(target)
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first()
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  await dialog
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const options = target.getByRole("listbox").locator("[role=option]");
  await expect(options.first()).toBeVisible();
  const ways = await options.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-way") ?? ""),
  );
  return ways.map((way) => way.replace("/", "_"));
}

/** The lanes the provider settings list, as catalogue lane ids. */
async function settingsLanes(target: Page): Promise<string[]> {
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const settings = target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });
  const lanes = settings.locator("[data-lane]");
  await expect(lanes.first()).toBeAttached();
  return lanes.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-lane") ?? ""),
  );
}

/** The models the local AI's setup lists, across its lanes, and how many
 * lane lists it shows. */
async function setupLists(target: Page) {
  const panel = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  await panel
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(panel).toBeHidden();
  await target.keyboard.press("Control+KeyK");
  const name = label("desktop.setup.palette_item", { name: "Local AI" });
  await target
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(name);
  await target.getByRole("listbox").getByRole("option", { name }).click();
  const lists = panel
    .locator('[data-setup-element="local_ai"]')
    .locator('[data-slot="local-models"]');
  await expect(lists.first()).toBeVisible();
  const models = await lists
    .locator("li[data-model]")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-model") ?? ""),
    );
  return { count: await lists.count(), models: [...new Set(models)].sort() };
}

for (const engine of FIXTURE_ENGINES) {
  test(`with ${engine} selected the picker and the settings list the lanes served for it`, async ({
    page: target,
  }) => {
    const expected = served(engine);
    expect(expected.ids).toContain(`${engine}_api`);
    expect(expected.ids).not.toContain(`${other(engine)}_api`);

    await open(target, engine);
    const picker = await pickerLanes(target);
    await open(target, engine);
    const settings = await settingsLanes(target);

    // The picker groups the lanes that can run first, so order is not
    // compared; the set is.
    const lanes = [...expected.ids].sort();
    expect([...picker].sort()).toEqual(lanes);
    // The settings also show made-up artwork lanes no catalogue serves;
    // of the catalogue's lanes they list the served ones alone.
    expect(settings.filter((id) => CATALOGUED.has(id)).sort()).toEqual(lanes);
    expect(settings).not.toContain(`${other(engine)}_api`);
  });

  test(`with ${engine} selected the local AI's setup lists the keyless lanes served for it`, async ({
    page: target,
  }) => {
    const expected = served(engine);
    expect(expected.keyless).toContain(`${engine}_api`);

    await open(target, engine, "hardware");
    const setup = await setupLists(target);

    expect(setup.count).toBe(expected.keyless.length);
    expect(setup.models).toEqual(expected.listed);
  });
}

test("choosing the other engine changes every list the host serves", async ({
  page: target,
}) => {
  await open(target, "llamacpp");
  await target.waitForFunction(() => Boolean(window.__fixtureAgentSession));
  const lists = await target.evaluate(async () => {
    const session = window.__fixtureAgentSession;
    if (!session) throw new Error("The scenario host made no agent session.");
    const read = async () => {
      const catalog = await session.providerCatalog();
      const local = await session.localModels!();
      return {
        catalog: (
          ("providers" in catalog ? catalog.providers : undefined) ?? []
        ).map((lane) => `${lane.provider_id}_${lane.transport}`),
        local: local.local_lanes,
        revision: local.revision,
      };
    };
    const before = await read();
    await session.chooseLocalEngine!("ollama", "auto", before.revision);
    return { before, after: await read() };
  });

  for (const read of [lists.before.catalog, lists.before.local]) {
    expect(read).toContain("llamacpp_api");
    expect(read).not.toContain("ollama_api");
  }
  for (const read of [lists.after.catalog, lists.after.local]) {
    expect(read).toContain("ollama_api");
    expect(read).not.toContain("llamacpp_api");
  }
  expect(lists.after.catalog).toEqual(served("ollama").ids);
  expect(lists.after.local).toEqual(served("ollama").keyless);
});
