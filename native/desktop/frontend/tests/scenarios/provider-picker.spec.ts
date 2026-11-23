import { expect, test, type Locator, type Page } from "@playwright/test";
import { catalogsUnderEngine } from "../../src/dev/fixtures/agentCatalog";
import { settingsLanesUnderEngine } from "../../src/dev/providerSettingsFixture";
import {
  agentColumn as column,
  ask,
  matrixCell,
  matrixLane,
  matrixRows,
  messageField,
  offeredModels,
  pickWay,
  settled,
} from "../support/agent";
import { bundledMark, connectionLabel } from "../support/connection";
import { SERVED_ENGINE } from "../support/servedLocalLanes";
import { label } from "../support/strings";

// The agent's model matrix: a heading for each lane, with its provider's own
// mark and the name cadrumo-agent's catalog gives it, and nothing that lets a
// person pick "how" a provider is reached. A provider the catalog serves two
// lanes for (Example Alpha and Example Beta) is two headings; the lane of the
// cell chosen is the one the next message runs on, and the models and efforts
// under each heading are that lane's own.

// The smallest side a control may have under a finger, less the rounding of a
// rem length to device pixels.
const FINGER = 44 - 1;

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** What the fixture catalog holds under the default engine, read straight
 * from it: every check below compares the column with this, and none restates
 * a provider. */
const lanes = catalogsUnderEngine(SERVED_ENGINE).served.providers ?? [];
const wayOf = (served: { provider_id: string; transport: string }) =>
  `${served.provider_id}/${served.transport}`;
const laneOf = (way: string) => {
  const served = lanes.find((held) => wayOf(held) === way);
  if (!served) throw new Error(`The fixture catalog has no lane ${way}.`);
  return served;
};

/** Why the fixture holds a lane back, in the words the column has for it. */
function heldBy(served: (typeof lanes)[number]): string | null {
  if (served.health.selectable) return null;
  if (served.health.configured === "unavailable")
    return label("desktop.agent.lane_not_configured");
  if (served.health.authentication === "unauthenticated")
    return label("desktop.agent.lane_signed_out");
  if (served.health.transport === "unavailable")
    return label("desktop.agent.lane_unreachable");
  return label("desktop.agent.unavailable");
}

const effortWords = (efforts: readonly string[]) =>
  efforts.map((effort) => label(`desktop.agent.effort_${effort}`));

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

const composerButton = (target: Page) =>
  column(target)
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first();

/** Opens the model settings from the composer. */
async function openSettings(target: Page) {
  await composerButton(target).click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  await expect(settings).toBeVisible();
  return settings;
}

/** The heading rows of every lane the open matrix shows. */
const laneHeadings = (settings: Locator) =>
  settings.locator("tr[data-slot=model-matrix-lane]");
const searchField = (settings: Locator) =>
  settings.getByRole("searchbox", {
    name: label("desktop.agent.model_matrix_search_label"),
  });
const filter = (settings: Locator, name: "on" | "off" | "ready" | "setup") =>
  settings.locator(`[data-filter=${name}]`);

/** The model row whose cell is the one chosen. */
const chosenRow = (settings: Locator) =>
  settings.locator(
    "tr[data-slot=model-matrix-row]:has([role=radio][aria-checked=true])",
  );

/** The columns of the cells the row of `model` on the lane `way` has, in
 * order: the provider's default, then each effort the model takes. */
const cellsOf = (settings: Locator, way: string, model: string) =>
  matrixRows(settings, way)
    .and(settings.locator(`[data-model="${model}"]`))
    .locator("[role=radio]")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-column")),
    );

/** The names of a row's effort cells, the provider's default left out. */
const effortCellNames = (settings: Locator, way: string, model: string) =>
  matrixRows(settings, way)
    .and(settings.locator(`[data-model="${model}"]`))
    .locator('[role=radio]:not([data-column="default"])')
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("aria-label")),
    );

/** The cell names a row of `name` has for `efforts`, in the words a screen
 * reader hears. */
const namedCells = (name: string, efforts: readonly string[]) =>
  effortWords(efforts).map((effort) =>
    label("desktop.agent.model_matrix_cell", { model: name, effort }),
  );

/** The model ids the catalog lists for the lane `way`, in its order. */
const catalogModels = (way: string) =>
  laneOf(way).catalog.models?.map((model) => model.entry_id) ?? [];

/** Waits out the transitions of a popover that is arriving: it grows as it
 * opens, so what is measured of it is only real once they have ended. */
const arrived = (popover: Locator) =>
  popover.evaluate(async (node) => {
    await Promise.all(
      node.getAnimations({ subtree: true }).map((motion) => motion.finished),
    );
  });

/** Every selection the column has handed to the agent with a message, in
 * order. Only the scenario host can say: it is read off the session the
 * column sends through. */
const sentSelections = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __sentSelections?: unknown[] })
        .__sentSelections ?? [],
  );

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the searchable matrix has one heading for each connection, with its provider's own mark", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);

  // Nothing offers a way to choose how a provider is reached: a person
  // chooses a cell of one matrix, and every choice is one of its cells.
  await expect(settings.getByRole("radiogroup")).toHaveCount(0);
  await expect(
    settings.locator("[role=radio]:not([data-matrix-cell])"),
  ).toHaveCount(0);
  await expect(settings.getByRole("switch")).toHaveCount(0);
  await expect(settings.getByRole("tablist")).toHaveCount(0);
  await expect(settings.getByRole("combobox")).toHaveCount(0);

  // The search names what it searches.
  const grid = settings.getByRole("grid", {
    name: label("desktop.agent.model_matrix_label"),
  });
  await expect(grid).toBeVisible();
  const gridId = await grid.getAttribute("id");
  expect(gridId).toBeTruthy();
  await expect(searchField(settings)).toHaveAttribute(
    "aria-controls",
    gridId ?? "",
  );
  const headings = laneHeadings(settings);
  await expect(headings).toHaveCount(lanes.length);
  const rows = await headings.evaluateAll((nodes) =>
    nodes.map((node) => ({
      way: node.getAttribute("data-way"),
      text: node.textContent ?? "",
      standing: node.getAttribute("data-standing"),
      words:
        node.querySelector("[data-slot=model-matrix-lane-words]")
          ?.textContent ?? null,
      marks: [...node.querySelectorAll("[data-slot=provider-mark]")].map(
        (mark) => ({
          provider: mark.getAttribute("data-provider"),
          kind: mark.getAttribute("data-mark"),
          tag: mark.tagName.toLowerCase(),
        }),
      ),
    })),
  );
  // Each lane the catalog serves is one heading.
  expect(rows.map((row) => row.way).sort()).toEqual(lanes.map(wayOf).sort());
  for (const served of lanes) {
    const row = rows.find((held) => held.way === wayOf(served));
    const why = heldBy(served);
    expect(row?.text, wayOf(served)).toContain(served.display_name);
    expect(row?.text, wayOf(served)).toContain(connectionLabel(served));
    if (why) expect(row?.words, wayOf(served)).toBe(why);
    expect(row?.standing, wayOf(served)).toBe(why === null ? "ready" : "setup");
    expect(row?.marks, wayOf(served)).toEqual([
      // A provider the agent ships no artwork for wears the generic mark.
      {
        provider: served.provider_id,
        kind: bundledMark(served.provider_id) ? "mono" : "generic",
        tag: "span",
      },
    ]);
  }
  // Example Alpha and Example Beta each have two distinguishable choices.
  for (const name of ["Example Alpha", "Example Beta"])
    expect(rows.filter((row) => row.text.includes(name))).toHaveLength(2);
  // Those the catalog holds back stay in the matrix, needing setup.
  const held = lanes.filter((served) => !served.health.selectable);
  await expect(
    settings.locator("tr[data-slot=model-matrix-lane][data-standing=setup]"),
  ).toHaveCount(held.length);

  // The lanes that are on are shown to start with; the filters set the ready
  // ones apart from those that need setting up.
  await expect(filter(settings, "on")).toHaveAttribute("aria-pressed", "true");
  await filter(settings, "ready").click();
  await expect(headings).toHaveCount(lanes.length - held.length);
  await expect(
    settings.locator(
      "tr[data-slot=model-matrix-lane]:not([data-standing=ready])",
    ),
  ).toHaveCount(0);
  // Both pressed is neither left out.
  await filter(settings, "setup").click();
  await expect(headings).toHaveCount(lanes.length);
  await filter(settings, "ready").click();
  await expect(headings).toHaveCount(held.length);
  await expect(
    settings.locator(
      "tr[data-slot=model-matrix-lane]:not([data-standing=setup])",
    ),
  ).toHaveCount(0);
});

test("search filters connection types and reports no matches", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  const search = searchField(settings);
  const headings = laneHeadings(settings);

  await search.fill(label("desktop.providers.connection_api"));
  const reachedBy = (key: string) =>
    lanes.filter((served) => connectionLabel(served) === label(key));
  await expect(headings).toHaveCount(
    reachedBy("desktop.providers.connection_api").length,
  );
  for (const heading of await headings.all())
    await expect(heading).toContainText(
      label("desktop.providers.connection_api"),
    );

  await search.fill(label("desktop.providers.connection_app"));
  await expect(headings).toHaveCount(
    reachedBy("desktop.providers.connection_app").length,
  );
  await search.fill(label("desktop.providers.connection_local"));
  await expect(headings).toHaveCount(
    reachedBy("desktop.providers.connection_local").length,
  );
  await search.fill("no matching provider");
  await expect(headings).toHaveCount(0);
  await expect(
    settings.locator("[data-slot=model-matrix-empty]"),
  ).toContainText(label("desktop.agent.model_matrix_search_empty"));
});

test("a lane the catalogue serves as needing no key is worded as on this computer, and a keyed lane by how it is reached", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  const keyless = lanes.filter((served) => served.auth_kind === "none");
  const keyed = lanes.filter((served) => served.auth_kind !== "none");
  // The scenario catalogue serves both kinds, and the selected local
  // engine's lane alone.
  expect(keyless.map(wayOf)).toContain(`${SERVED_ENGINE}/api`);
  expect(keyless.map((served) => served.provider_id)).not.toContain(
    SERVED_ENGINE === "llamacpp" ? "ollama" : "llamacpp",
  );
  expect(keyed.length).toBeGreaterThan(0);
  for (const served of keyless) {
    const row = matrixLane(settings, wayOf(served));
    await expect(row).toContainText(
      label("desktop.providers.connection_local"),
    );
    await expect(row).not.toContainText(
      label("desktop.providers.connection_api"),
    );
  }
  for (const served of keyed) {
    const row = matrixLane(settings, wayOf(served));
    await expect(row).toContainText(connectionLabel(served));
    await expect(row).not.toContainText(
      label("desktop.providers.connection_local"),
    );
  }
  // An API-transport keyed lane says key; the same transport keyless does not.
  await expect(matrixLane(settings, "kimi/api")).toContainText(
    label("desktop.providers.connection_api"),
  );
  await expect(matrixLane(settings, "llamacpp/api")).not.toContainText(
    label("desktop.providers.connection_api"),
  );
  // The lane chosen is the one worded as on this computer.
  await pickWay(target, settings, "llamacpp/api");
  await expect(chosenRow(settings)).toHaveAttribute("data-way", "llamacpp/api");
  await expect(matrixLane(settings, "llamacpp/api")).toContainText(
    `${laneOf("llamacpp/api").display_name}, ${label("desktop.providers.connection_local")}`,
  );
});

test("search keeps duplicate provider connections distinct for keyboard choice", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  const search = searchField(settings);
  await search.fill("Example Beta");
  await expect(laneHeadings(settings)).toHaveCount(2);
  // Every word typed has to match: the name and how it is reached narrow it
  // to one.
  await search.fill(
    `Example Beta ${label("desktop.providers.connection_app")}`,
  );
  await expect(laneHeadings(settings)).toHaveCount(1);
  await expect(matrixLane(settings, "qwen/cli")).toHaveCount(1);
  await search.fill("Example Beta");
  await expect(laneHeadings(settings)).toHaveCount(2);

  const [first = "", second = ""] = await laneHeadings(settings).evaluateAll(
    (nodes) => nodes.map((node) => node.getAttribute("data-way") ?? ""),
  );
  expect([first, second].sort()).toEqual(["qwen/api", "qwen/cli"]);

  // The keyboard starts on the first cell shown, the first lane's, and a page
  // down goes to the next lane, the other connection of the same name.
  await settings.locator('[data-matrix-cell][tabindex="0"]').focus();
  await expect(
    matrixCell(settings, first, catalogModels(first)[0] ?? ""),
  ).toBeFocused();
  await target.keyboard.press("PageDown");
  const next = matrixCell(settings, second, catalogModels(second)[0] ?? "");
  await expect(next).toBeFocused();
  await target.keyboard.press("Enter");
  await expect(next).toHaveAttribute("aria-checked", "true");
  await expect(chosenRow(settings)).toHaveAttribute("data-way", second);
  await expect(composerButton(target)).toHaveAccessibleName(
    new RegExp(
      `^${escaped(label("desktop.agent.settings_label", { current: "Example Beta" }))}`,
    ),
  );
  expect(await offeredModels(settings, second)).toEqual(catalogModels(second));
});

test("choosing an entry chooses its lane, and a message goes with that lane's transport", async ({
  page: target,
}, info) => {
  test.skip(
    info.project.metadata.agentHost === "live",
    "What the column hands the agent is read off the scenario host's session.",
  );
  await target.addInitScript(() => {
    // The scenario host assigns its session to this property each time the
    // column uses it; the first send follows an observe, so every send is
    // seen by the wrapper.
    type Sending = {
      send?: (request: { selection: unknown }) => Promise<unknown>;
      recorded?: boolean;
    };
    const sent: unknown[] = [];
    Object.assign(window, { __sentSelections: sent });
    let held: Sending | undefined;
    Object.defineProperty(window, "__fixtureAgentSession", {
      configurable: true,
      get: () => held,
      set: (session: Sending | undefined) => {
        held = session;
        if (!session || session.recorded || !session.send) return;
        session.recorded = true;
        const send = session.send.bind(session);
        session.send = (request) => {
          sent.push(request.selection);
          return send(request);
        };
      },
    });
  });
  await open(target);

  const startsWith = (way: string) => {
    const served = laneOf(way);
    const start =
      served.catalog.recommended_entry_id ??
      served.catalog.models?.[0]?.entry_id;
    const model = served.catalog.models?.find(
      (held) => held.entry_id === start,
    );
    return {
      provider: served.provider_id,
      transport: served.transport,
      model: model?.model,
    };
  };

  // The program entry of Example Beta: its own models, and a message goes by the
  // transport the catalog gives that lane.
  let settings = await openSettings(target);
  await pickWay(target, settings, "qwen/cli");
  await expect(chosenRow(settings)).toHaveAttribute("data-way", "qwen/cli");
  expect(await offeredModels(settings, "qwen/cli")).toEqual(
    catalogModels("qwen/cli"),
  );
  await target.keyboard.press("Escape");
  await ask(target, "Primera");
  await expect.poll(() => sentSelections(target)).toHaveLength(1);
  expect((await sentSelections(target)).at(-1)).toEqual(startsWith("qwen/cli"));
  expect(startsWith("qwen/cli").transport).toBe("cli");
  await settled(target);

  // The other entry of the same name: another lane, with models of its own.
  settings = await openSettings(target);
  await pickWay(target, settings, "qwen/api");
  await expect(chosenRow(settings)).toHaveAttribute("data-way", "qwen/api");
  expect(await offeredModels(settings, "qwen/api")).toEqual(
    catalogModels("qwen/api"),
  );
  await target.keyboard.press("Escape");
  await ask(target, "Segunda");
  await expect.poll(() => sentSelections(target)).toHaveLength(2);
  expect((await sentSelections(target)).at(-1)).toEqual(startsWith("qwen/api"));
  expect(startsWith("qwen/api").transport).toBe("api");
  await settled(target);

  // The entry the column starts on goes by its own.
  settings = await openSettings(target);
  await pickWay(target, settings, "kimi/api");
  await target.keyboard.press("Escape");
  await ask(target, "Tercera");
  await expect.poll(() => sentSelections(target)).toHaveLength(3);
  expect((await sentSelections(target)).at(-1)).toEqual(startsWith("kimi/api"));
  expect(startsWith("kimi/api").transport).toBe("api");
});

test("Escape straight after a choice closes the settings", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  await pickWay(target, settings, "qwen/api");
  // The choice is made, and the settings stay open for the next.
  await expect(chosenRow(settings)).toHaveAttribute("data-way", "qwen/api");
  await expect(settings).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await expect(composerButton(target)).toBeFocused();
});

test("the arrow keys move inside the matrix, and Escape from it closes the settings", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  // The keyboard starts on the cell chosen, and an arrow moves along its row
  // without choosing.
  const chosen = matrixCell(settings, "kimi/api", "fixture-deep");
  await settings.locator('[data-matrix-cell][tabindex="0"]').focus();
  await expect(chosen).toBeFocused();
  await target.keyboard.press("ArrowRight");
  const moved = matrixCell(settings, "kimi/api", "fixture-deep", "low");
  await expect(moved).toBeFocused();
  await expect(moved).toHaveAttribute("aria-checked", "false");
  await expect(chosen).toHaveAttribute("aria-checked", "true");
  await expect(settings).toBeVisible();

  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await expect(composerButton(target)).toBeFocused();
});

test("a rapid double Escape from the matrix closes the settings and goes no further", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  await settings.locator('[data-matrix-cell][tabindex="0"]').focus();

  await target.keyboard.press("Escape");
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await expect(composerButton(target)).toBeFocused();
});

test("the message box taking focus after a choice closes the settings", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  await pickWay(target, settings, "qwen/api");
  await expect(chosenRow(settings)).toHaveAttribute("data-way", "qwen/api");
  // Focus moves out of the settings without a press on them.
  await messageField(target).focus();
  await expect(settings).toHaveCount(0);
  await expect(messageField(target)).toBeFocused();
});

test("a held lane cannot be chosen, and says why", async ({ page: target }) => {
  await open(target);
  const settings = await openSettings(target);
  for (const served of lanes) {
    const why = heldBy(served);
    if (why === null) continue;
    const held = matrixLane(settings, wayOf(served));
    await expect(held).toHaveAttribute("data-standing", "setup");
    await expect(
      held.locator("[data-slot=model-matrix-lane-words]"),
    ).toHaveText(why);
  }
  // A model this computer lacks is listed, and cannot be chosen either.
  const lacking = matrixRows(settings, "llamacpp/api").and(
    settings.locator("[data-held=false]"),
  );
  await expect(lacking).toHaveCount(1);
  await expect(lacking).toHaveAttribute("aria-disabled", "true");
  const lackingCell = lacking.locator('[role=radio][data-column="default"]');
  await expect(lackingCell).toHaveAttribute("aria-disabled", "true");
  // Pressed all the same: a disabled cell is still in the grid to be pressed.
  await lackingCell.click({ force: true });
  // The lane in use stays as it was.
  await expect(lackingCell).toHaveAttribute("aria-checked", "false");
  await expect(
    matrixCell(settings, "kimi/api", "fixture-deep"),
  ).toHaveAttribute("aria-checked", "true");
  await expect(composerButton(target)).toHaveAccessibleName(
    new RegExp(
      `^${escaped(label("desktop.agent.settings_label", { current: "Example Alpha" }))}`,
    ),
  );
});

test("the efforts offered follow the model of the lane chosen", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  const takes = (way: string, model: string) =>
    laneOf(way).catalog.models?.find((held) => held.entry_id === model)
      ?.efforts ?? [];

  // Example Beta by its program: the lane's recommended model takes its
  // efforts, each a cell beside the provider's default.
  await pickWay(target, settings, "qwen/cli");
  await expect(
    matrixCell(settings, "qwen/cli", "fixture-ultra"),
  ).toHaveAttribute("aria-checked", "true");
  expect(await cellsOf(settings, "qwen/cli", "fixture-ultra")).toEqual([
    "default",
    ...takes("qwen/cli", "fixture-ultra"),
  ]);
  expect(await effortCellNames(settings, "qwen/cli", "fixture-ultra")).toEqual(
    namedCells("Fixture Ultra", takes("qwen/cli", "fixture-ultra")),
  );
  expect(await cellsOf(settings, "qwen/cli", "fixture-tiered")).toEqual([
    "default",
    ...takes("qwen/cli", "fixture-tiered"),
  ]);
  // The same name by its other connection: its models take none.
  for (const model of catalogModels("qwen/api"))
    expect(await cellsOf(settings, "qwen/api", model)).toEqual(["default"]);
  // Example Alpha's models take their own, and one of them none.
  expect(await cellsOf(settings, "kimi/api", "fixture-deep")).toEqual([
    "default",
    ...takes("kimi/api", "fixture-deep"),
  ]);
  expect(await effortCellNames(settings, "kimi/api", "fixture-deep")).toEqual(
    namedCells("Fixture Deep", takes("kimi/api", "fixture-deep")),
  );
  expect(await cellsOf(settings, "kimi/api", "fixture-quick")).toEqual([
    "default",
    ...takes("kimi/api", "fixture-quick"),
  ]);
  expect(await cellsOf(settings, "kimi/api", "fixture-plain")).toEqual([
    "default",
  ]);
});

/** Everything in `scope` a screen reader or a pointer could meet that says
 * how it is reached: its text, and its names and titles. */
const wording = (scope: Locator) =>
  scope.evaluate((node) => {
    const names = [...node.querySelectorAll("[aria-label],[title]")].flatMap(
      (named) => [
        named.getAttribute("aria-label"),
        named.getAttribute("title"),
      ],
    );
    return [(node as HTMLElement).innerText, ...names].filter(Boolean);
  });

test("no “CLI” appears in the agent column, the model matrix or the settings", async ({
  page: target,
}) => {
  await open(target);
  const settings = await openSettings(target);
  // The lane that runs a program: the very one the old wording was for.
  await pickWay(target, settings, "qwen/cli");
  const said = [
    ...(await wording(settings)),
    ...(await column(target).evaluate((node) => [
      (node as HTMLElement).innerText,
    ])),
  ];
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);

  await column(target)
    .getByRole("button", { name: label("desktop.agent.settings"), exact: true })
    .click();
  const providers = column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });
  await expect(providers).toBeVisible();
  await expect(providers.locator("[data-lane]")).toHaveCount(
    settingsLanesUnderEngine(SERVED_ENGINE).length,
  );
  said.push(...(await wording(providers)));

  // What was read is the whole of what a person is shown there.
  const everything = said.join(" ");
  for (const shown of [
    "Example Relay",
    label("desktop.providers.title"),
    label("desktop.providers.status_setup_needed"),
    label("desktop.agent.lane_not_configured"),
    label("desktop.agent.model_matrix_label"),
    label("desktop.agent.effort_ultra"),
  ])
    expect(everything).toContain(shown);
  for (const text of said) {
    expect(text).not.toMatch(/\bCLI\b/i);
    expect(text).not.toMatch(/command[- ]line/i);
    // Nor any of the agent's own machinery or the build it runs in.
    expect(text).not.toMatch(
      /\b(lanes?|catalog|transport|oauth|development|subagents?|runtime)\b/i,
    );
  }
});

/** The relative luminance of a computed `rgb(...)` colour. */
function luminance(colour: string): number {
  const [red = 0, green = 0, blue = 0] = (colour.match(/[\d.]+/g) ?? [])
    .slice(0, 3)
    .map((part) => {
      const channel = Number(part) / 255;
      return channel <= 0.03928
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4;
    });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

for (const mode of ["light", "dark", "forced colours"] as const) {
  test(`a mark follows the text colour of the matrix (${mode})`, async ({
    page: target,
  }) => {
    await target.emulateMedia({
      colorScheme: mode === "dark" ? "dark" : "light",
      forcedColors: mode === "forced colours" ? "active" : "none",
    });
    await open(target);
    const settings = await openSettings(target);
    await expect(laneHeadings(settings)).toHaveCount(lanes.length);
    const marks = await laneHeadings(settings).evaluateAll((nodes) =>
      nodes.map((node) => {
        const mark = node.querySelector("[data-slot=provider-mark]");
        return {
          provider: mark?.getAttribute("data-provider") ?? "",
          text: mark ? getComputedStyle(mark).color : "",
          pieces: [...(mark?.querySelectorAll("path") ?? [])].map((piece) => ({
            fill: getComputedStyle(piece).fill,
            stroke: getComputedStyle(piece).stroke,
          })),
        };
      }),
    );
    expect(marks).toHaveLength(lanes.length);
    // Mask marks have no SVG paths; generic outlines inherit the text colour.
    for (const mark of marks) {
      for (const piece of mark.pieces) {
        expect(piece.fill, mark.provider).toBe("none");
        expect(piece.stroke, mark.provider).toBe(mark.text);
      }
    }
    // The text colour is the theme's: dark ink on the light matrix, light on
    // the dark one, so a mark drawn in it can be seen on either.
    const plain = marks.find((mark) => mark.provider === "qwen");
    if (mode === "light")
      expect(luminance(plain?.text ?? ""), mode).toBeLessThan(0.3);
    if (mode === "dark")
      expect(luminance(plain?.text ?? ""), mode).toBeGreaterThan(0.5);
  });
}

for (const width of [390, 520]) {
  test.describe(`a window ${width} wide`, () => {
    test.use({
      viewport: { width, height: 844 },
      hasTouch: true,
      isMobile: true,
    });

    const overflowing = (target: Page) =>
      target.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );

    /** Opens the agent, which a window this narrow shows on its own. */
    async function showAgent(target: Page) {
      await open(target);
      await target.locator("[data-rail=agent]").tap();
      await expect(composerButton(target)).toBeVisible();
    }

    test("the settings and the matrix fit, the matrix scrolls inside itself, and each cell is finger sized", async ({
      page: target,
    }) => {
      await showAgent(target);
      await composerButton(target).tap();
      const settings = target.getByRole("dialog", {
        name: label("desktop.agent.settings_title"),
      });
      await expect(settings).toBeVisible();
      // Measured once the popover has finished arriving: it grows as it opens.
      await expect
        .poll(async () => {
          const box = await settings.boundingBox();
          return box ? box.x >= 0 && box.x + box.width <= width : false;
        })
        .toBe(true);
      await arrived(settings);
      expect(await overflowing(target)).toBe(false);
      expect(
        await settings.evaluate((node) => node.scrollWidth > node.clientWidth),
      ).toBe(false);
      // Every field and filter of it is a fingertip.
      for (const field of [
        searchField(settings),
        ...(await settings.locator("[data-filter]").all()),
      ]) {
        const box = await field.boundingBox();
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(FINGER);
        expect((box?.x ?? -1) + (box?.width ?? 0)).toBeLessThanOrEqual(width);
      }

      const grid = settings.getByRole("grid", {
        name: label("desktop.agent.model_matrix_label"),
      });
      await expect(laneHeadings(settings)).toHaveCount(lanes.length);
      // What scrolls the matrix is the box around its grid.
      const scroller = grid.locator("xpath=..");
      const edge = (await scroller.boundingBox())!;
      expect(edge.x).toBeGreaterThanOrEqual(0);
      expect(edge.x + edge.width).toBeLessThanOrEqual(width);
      expect(edge.y).toBeGreaterThanOrEqual(0);
      expect(edge.y + edge.height).toBeLessThanOrEqual(844);
      expect(await overflowing(target)).toBe(false);
      // A window this narrow lays each model out on lines of its own, its
      // efforts wrapping under its name: nothing of the matrix scrolls or
      // is cut sideways, the page nor the box around the grid.
      expect(
        await scroller.evaluate((node) => node.scrollWidth > node.clientWidth),
      ).toBe(false);
      const cut = await grid.evaluate((table) => {
        const box = table.getBoundingClientRect();
        // The column headings are left to a screen reader here, so only
        // what is drawn is measured.
        return [...table.querySelectorAll("tbody [role=radio], tbody th")]
          .filter((node) => {
            const at = node.getBoundingClientRect();
            return at.right > box.right + 1 || at.left < box.left - 1;
          })
          .map((node) => node.textContent ?? "");
      });
      expect(cut).toEqual([]);
      // Each choice names its effort where no column heading stands over it.
      await expect(
        matrixCell(settings, "kimi/api", "fixture-deep", "low"),
      ).toHaveText(label("desktop.agent.effort_low"));

      // The cells are a fingertip each.
      const cells = await grid.locator("[role=radio]").evaluateAll((nodes) =>
        nodes.map((node) => {
          const box = node.getBoundingClientRect();
          return {
            cell: `${node.closest("tr")?.getAttribute("data-way")} ${node.closest("tr")?.getAttribute("data-model")} ${node.getAttribute("data-column")}`,
            height: box.height,
            width: box.width,
          };
        }),
      );
      expect(cells.length).toBeGreaterThan(0);
      for (const cell of cells) {
        expect(cell.height, cell.cell).toBeGreaterThanOrEqual(FINGER);
        expect(cell.width, cell.cell).toBeGreaterThanOrEqual(FINGER);
      }

      // More rows than fit: the matrix scrolls inside itself, down to its
      // last row, without the window moving.
      expect(
        await scroller.evaluate(
          (node) => node.scrollHeight > node.clientHeight,
        ),
      ).toBe(true);
      await scroller.evaluate((node) => {
        node.scrollTop = node.scrollHeight;
      });
      await expect
        .poll(() =>
          scroller.evaluate((node) => {
            const inside = node.getBoundingClientRect();
            const row = node
              .querySelector("tbody tr:last-child")
              ?.getBoundingClientRect();
            return row
              ? row.top >= inside.top - 1 && row.bottom <= inside.bottom + 1
              : false;
          }),
        )
        .toBe(true);
      expect(await overflowing(target)).toBe(false);

      // A tap on a cell that can be chosen chooses it.
      const cell = matrixCell(settings, "qwen/cli", "fixture-ultra");
      await cell.scrollIntoViewIfNeeded();
      await cell.tap();
      await expect(cell).toHaveAttribute("aria-checked", "true");
      await expect(chosenRow(settings)).toHaveAttribute("data-way", "qwen/cli");
      expect(await overflowing(target)).toBe(false);
    });

    test("the settings of the providers fit, each card under a finger", async ({
      page: target,
    }) => {
      await showAgent(target);
      await column(target)
        .getByRole("button", {
          name: label("desktop.agent.settings"),
          exact: true,
        })
        .tap();
      const providers = column(target).getByRole("region", {
        name: label("desktop.providers.title"),
      });
      await expect(providers).toBeVisible();
      await expect(providers.locator("[data-lane]")).not.toHaveCount(0);
      const edge = (await providers.boundingBox())!;
      expect(edge.x).toBeGreaterThanOrEqual(0);
      expect(edge.x + edge.width).toBeLessThanOrEqual(width);
      expect(await overflowing(target)).toBe(false);
      // Nothing of any card reaches past the region, and a card's name is
      // whole: it wraps rather than being cut.
      const spill = await providers.evaluate((region) => {
        const box = region.getBoundingClientRect();
        return [...region.querySelectorAll("*")]
          .filter((node) => {
            const at = node.getBoundingClientRect();
            return at.right > box.right + 1 || at.left < box.left - 1;
          })
          .map((node) => node.tagName.toLowerCase());
      });
      expect(spill).toEqual([]);
      const names = await providers
        .getByRole("heading", { level: 4 })
        .evaluateAll((nodes) =>
          nodes.map((node) => node.scrollWidth > node.clientWidth),
        );
      expect(names).not.toContain(true);
      // Every control of a card is a fingertip.
      const small = await providers.getByRole("button").evaluateAll((nodes) =>
        nodes
          .map((node) => node.getBoundingClientRect())
          .filter((box) => box.height < 44 || box.width < 44)
          .map((box) => `${box.width}x${box.height}`),
      );
      expect(small).toEqual([]);
    });
  });
}
