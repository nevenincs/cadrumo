import { expect, test } from "@playwright/test";
import { fixtureOfferReads } from "../src/dev/agentFixtureModels";
import { fixtureTaskModels } from "../src/dev/fixtureTaskModels";
import {
  catalogsUnderEngine,
  FIXTURE_CATALOG,
} from "../src/dev/fixtures/agentCatalog";
import {
  FIXTURE_SETTINGS_LANES,
  providerSettingsFixture,
} from "../src/dev/providerSettingsFixture";
import {
  MATRIX_AVAILABILITIES,
  MATRIX_STATES,
  matrixMove,
  matrixView,
  STARTING_FILTERS,
  type MatrixLane,
  type MatrixMode,
  type MatrixRow,
  type MatrixView,
} from "../src/components/agent/modelMatrixView";
import { agentOffer, type AgentOffer } from "../src/shell/agentOffer";
import type { LocalModelListStatus } from "../src/shell/localModelsContract";
import { SERVED_ENGINE } from "./support/servedLocalLanes";

// What the model matrix shows of the agent's offer, worked out by the
// column's own projection from the made-up reads the specimens use: six
// providers, one ready by its API and signed out by its app, one with forty
// models, the lane on this computer with a model to download, one not
// configured, one turned off and one local engine that does not run. Every
// expected value is written out by hand. Words are left as their keys.

const words = (key: string) => key;

const offerOf = (scene?: Parameters<typeof fixtureOfferReads>[0]) => {
  const { catalog, lists, settings } = fixtureOfferReads(scene);
  return agentOffer(words, catalog, lists, settings);
};

const offer = offerOf();

const ids = (view: MatrixView) => view.lanes.map((lane) => lane.id);
const rowsOf = (view: MatrixView, lane: string) =>
  view.lanes.find((held) => held.id === lane)?.rows.map((row) => row.id);

test("a task's matrix lists every lane on, the one turned off counted apart", () => {
  const view = matrixView(words, offer, "task", "", STARTING_FILTERS);
  expect(ids(view)).toEqual([
    "kimi_api",
    "kimi_cli",
    "qwen_api",
    "qwen_cli",
    "deepseek_cli",
    "zai_api",
    "llamacpp_api",
  ]);
  expect(view.offHidden).toBe(1);
  expect(view.noneOn).toBe(false);
  expect(
    view.lanes.map((lane) => [lane.id, lane.standing, lane.step, lane.door]),
  ).toEqual([
    ["kimi_api", "ready", null, null],
    ["kimi_cli", "setup", "sign_in", null],
    ["qwen_api", "ready", null, null],
    ["qwen_cli", "ready", null, null],
    ["deepseek_cli", "setup", "set_up", null],
    // It runs, but lists a model this computer does not hold yet.
    ["zai_api", "ready", "download", null],
    ["llamacpp_api", "setup", null, "local_ai_setup"],
  ]);
  // A lane not set up says why; its models are counted, not listed as cells
  // that cannot be pressed.
  const signedOut = view.lanes.find((lane) => lane.id === "kimi_cli");
  expect(signedOut?.words).toBe("desktop.agent.lane_signed_out");
  const engine = view.lanes.find((lane) => lane.id === "llamacpp_api");
  expect(engine?.rows).toEqual([]);
  expect(engine?.models).toBe(2);
  // Three of the API lane, forty, two of the app lane, three on this
  // computer and the engine's two.
  expect(view.models).toBe(50);
});

test("a task runs a local lane's list in its order, a model not held not choosable", () => {
  const view = matrixView(words, offer, "task", "", STARTING_FILTERS);
  const local = view.lanes.find((lane) => lane.id === "zai_api");
  expect(
    local?.rows.map((row: MatrixRow) => [row.id, row.held, row.choosable]),
  ).toEqual([
    ["synthetic-vision:1", false, false],
    ["synthetic-text:1", true, true],
    // Added by name; the catalog does not list it.
    ["synthetic-added:1", true, true],
  ]);
  expect(local?.models).toBe(3);
});

test("the effort columns are the ones some shown row takes, lowest first", () => {
  const every = matrixView(words, offer, "task", "", STARTING_FILTERS);
  expect(every.columns).toEqual([
    "default",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
    "ultra",
  ]);
  // The app lane takes no effort for a background request, so its
  // "ultra" model adds no column to a task's matrix.
  const fixture = matrixView(words, offer, "task", "fixture", STARTING_FILTERS);
  expect(ids(fixture)).toEqual(["kimi_api", "qwen_cli"]);
  expect(rowsOf(fixture, "qwen_cli")).toEqual([
    "fixture-tiered",
    "fixture-ultra",
  ]);
  expect(fixture.columns).toEqual([
    "default",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ]);
  // A conversation takes the app lane's efforts.
  const talk = matrixView(
    words,
    offer,
    "conversation",
    "fixture ultra",
    STARTING_FILTERS,
  );
  expect(ids(talk)).toEqual(["qwen_cli"]);
  expect(talk.columns).toEqual(["default", "high", "ultra"]);
});

test("every typed word has to match the lane's words or the model's", () => {
  const view = matrixView(
    words,
    offer,
    "task",
    "  ALPHA deep ",
    STARTING_FILTERS,
  );
  expect(ids(view)).toEqual(["kimi_api"]);
  expect(rowsOf(view, "kimi_api")).toEqual(["fixture-deep"]);
  expect(view.models).toBe(1);
  // An effort's words find the models that take it.
  const ultra = matrixView(
    words,
    offer,
    "task",
    "effort_ultra",
    STARTING_FILTERS,
  );
  expect(ids(ultra)).toEqual(["qwen_api"]);
  expect(rowsOf(ultra, "qwen_api")).toEqual([
    "example-many-06",
    "example-many-12",
    "example-many-18",
    "example-many-24",
    "example-many-30",
    "example-many-36",
  ]);
  // A lane with no models stays where its own words match.
  expect(
    ids(matrixView(words, offer, "task", "delta", STARTING_FILTERS)),
  ).toEqual(["deepseek_cli"]);
  // A lane not set up counts only the models the search keeps: the engine's
  // vision model alone holds "vision".
  const engine = matrixView(
    words,
    offer,
    "task",
    "llamacpp vision",
    STARTING_FILTERS,
  );
  expect(ids(engine)).toEqual(["llamacpp_api"]);
  expect(engine.lanes[0]?.rows).toEqual([]);
  expect(engine.models).toBe(1);
  const none = matrixView(words, offer, "task", "nothing", STARTING_FILTERS);
  expect(none.lanes).toEqual([]);
  expect(none.models).toBe(0);
  expect(none.offHidden).toBe(0);
});

test("the filters keep lanes on or off, and ready or needing setup", () => {
  const off = matrixView(words, offer, "task", "", {
    state: "off",
    availability: "all",
  });
  expect(ids(off)).toEqual(["antigravity_cli"]);
  expect(off.lanes[0]?.standing).toBe("off");
  expect(off.lanes[0]?.step).toBe("set_up");
  expect(off.offHidden).toBe(0);
  const ready = matrixView(words, offer, "task", "", {
    state: "on",
    availability: "ready",
  });
  expect(ids(ready)).toEqual(["kimi_api", "qwen_api", "qwen_cli", "zai_api"]);
  const setup = matrixView(words, offer, "task", "", {
    state: "on",
    availability: "setup",
  });
  expect(ids(setup)).toEqual(["kimi_cli", "deepseek_cli", "llamacpp_api"]);
  // A lane turned off needs setting up too, so it is kept beside them.
  const anySetup = matrixView(words, offer, "task", "", {
    state: "all",
    availability: "setup",
  });
  expect(ids(anySetup)).toEqual([
    "kimi_cli",
    "deepseek_cli",
    "llamacpp_api",
    "antigravity_cli",
  ]);
  // A lane off is never ready: the two axes together keep nothing, and the
  // one turned off is counted as kept out.
  const offReady = matrixView(words, offer, "task", "", {
    state: "off",
    availability: "ready",
  });
  expect(offReady.lanes).toEqual([]);
  expect(offReady.offHidden).toBe(1);
  const every = matrixView(words, offer, "task", "", {
    state: "all",
    availability: "all",
  });
  expect(every.lanes).toHaveLength(8);
  expect(every.offHidden).toBe(0);
});

test("with every provider off nothing is on, and each is counted", () => {
  const view = matrixView(
    words,
    offerOf({ allOff: true }),
    "task",
    "",
    STARTING_FILTERS,
  );
  expect(view.noneOn).toBe(true);
  expect(view.lanes).toEqual([]);
  expect(view.offHidden).toBe(8);
  expect(view.models).toBe(0);
});

test("while the agent starts each declared lane is listed as not checked, with nothing to choose", () => {
  const view = matrixView(
    words,
    offerOf({ declared: true }),
    "task",
    "",
    STARTING_FILTERS,
  );
  expect(ids(view)).toEqual([
    "kimi_api",
    "kimi_cli",
    "qwen_api",
    "qwen_cli",
    "deepseek_cli",
    "zai_api",
    "llamacpp_api",
  ]);
  for (const lane of view.lanes) {
    expect(lane.words).toBe("desktop.agent.lane_not_observed");
    expect(lane.rows).toEqual([]);
  }
  expect(view.columns).toEqual(["default"]);
  expect(view.models).toBe(0);
});

test("a conversation fixed to a lane says another continues in a new one", () => {
  const view = matrixView(
    words,
    offer,
    "conversation",
    "",
    STARTING_FILTERS,
    "kimi/api",
  );
  const say = (id: string) =>
    view.lanes.find((lane) => lane.id === id)?.words ?? null;
  expect(say("kimi_api")).toBeNull();
  expect(say("qwen_cli")).toBe("desktop.agent.continue_in_new_conversation");
  // A lane that cannot run says why instead.
  expect(say("kimi_cli")).toBe("desktop.agent.lane_signed_out");
  expect(rowsOf(view, "kimi_api")).toEqual([
    "fixture-deep",
    "fixture-quick",
    "fixture-plain",
  ]);
});

// Every combination of the two filters, over the reads the desktop scenario
// host serves by default (the fixture catalog under the bundled engine, the
// settings as its provider fixture starts them, and lists with nothing
// added), and over the specimen's reads, which turn one lane off. Each
// table maps "state/availability" to the lanes shown and their models.

type Table = Record<string, [string[], number]>;

const tableOf = (offered: AgentOffer, mode: MatrixMode): Table =>
  Object.fromEntries(
    MATRIX_STATES.flatMap((state) =>
      MATRIX_AVAILABILITIES.map(
        (availability): [string, [string[], number]] => {
          const view = matrixView(words, offered, mode, "", {
            state,
            availability,
          });
          return [`${state}/${availability}`, [ids(view), view.models]];
        },
      ),
    ),
  );

async function scenarioOffer(): Promise<AgentOffer> {
  const { settings } = providerSettingsFixture({
    say: () => undefined,
    wait: () => Promise.resolve(),
    readable: () => true,
    selectedEngine: () => SERVED_ENGINE,
  });
  // The lists as the host's model fixture starts them: nothing added, no
  // reading model, no task set, and every keyless lane its own.
  const lists: LocalModelListStatus = {
    unreadable: false,
    models: [],
    reading: null,
    reading_source: "none",
    tasks: fixtureTaskModels(FIXTURE_CATALOG).entries(),
    local_lanes: FIXTURE_SETTINGS_LANES.filter(
      (seed) => seed.auth_kind === "none",
    ).map((seed) => seed.id),
    revision: "0".repeat(64),
  };
  return agentOffer(
    words,
    catalogsUnderEngine(SERVED_ENGINE).served,
    lists,
    await settings.status(),
  );
}

test("every filter combination over the scenario reads", async () => {
  const scenario = await scenarioOffer();
  // No lane starts turned off, so "on" shows what "all" does and "off"
  // nothing. A task runs on the lanes that list models, not on the three
  // whose models are written: the API lane's three, two of each other ready
  // lane, and the local lane's and the engine's two recommended; the three
  // lanes not set up have none.
  const taskReady = [
    "kimi_api",
    "qwen_api",
    "qwen_cli",
    "zai_api",
    "llamacpp_api",
  ];
  const taskSetup = ["antigravity_cli", "kimi_cli", "deepseek_cli"];
  const taskAll = [
    "antigravity_cli",
    "kimi_api",
    "kimi_cli",
    "qwen_api",
    "qwen_cli",
    "deepseek_cli",
    "zai_api",
    "llamacpp_api",
  ];
  expect(tableOf(scenario, "task")).toEqual({
    "all/all": [taskAll, 11],
    "all/ready": [taskReady, 11],
    "all/setup": [taskSetup, 0],
    "on/all": [taskAll, 11],
    "on/ready": [taskReady, 11],
    "on/setup": [taskSetup, 0],
    "off/all": [[], 0],
    "off/ready": [[], 0],
    "off/setup": [[], 0],
  });
  // A conversation adds the three lanes whose model is written, one row
  // each: the keyed gateway ready, the two without a key needing setup and
  // still counting theirs.
  const talkReady = [
    "kimi_api",
    "qwen_api",
    "qwen_cli",
    "zhipu_cli",
    "zai_api",
    "llamacpp_api",
  ];
  const talkSetup = [
    "antigravity_cli",
    "kimi_cli",
    "deepseek_cli",
    "minimax_cli",
    "moonshot_cli",
  ];
  const talkAll = [
    "antigravity_cli",
    "kimi_api",
    "kimi_cli",
    "qwen_api",
    "qwen_cli",
    "zhipu_cli",
    "deepseek_cli",
    "minimax_cli",
    "moonshot_cli",
    "zai_api",
    "llamacpp_api",
  ];
  expect(tableOf(scenario, "conversation")).toEqual({
    "all/all": [talkAll, 14],
    "all/ready": [talkReady, 12],
    "all/setup": [talkSetup, 2],
    "on/all": [talkAll, 14],
    "on/ready": [talkReady, 12],
    "on/setup": [talkSetup, 2],
    "off/all": [[], 0],
    "off/ready": [[], 0],
    "off/setup": [[], 0],
  });
});

test("every filter combination over the specimen reads, one lane turned off", () => {
  // The lane turned off counts no models and is kept by "off" and by
  // "setup", never by "ready". A task counts the API lane's three, the
  // forty, the app lane's two, three on this computer (one added by name)
  // and the stopped engine's two.
  const ready = ["kimi_api", "qwen_api", "qwen_cli", "zai_api"];
  const setupOn = ["kimi_cli", "deepseek_cli", "llamacpp_api"];
  const on = [
    "kimi_api",
    "kimi_cli",
    "qwen_api",
    "qwen_cli",
    "deepseek_cli",
    "zai_api",
    "llamacpp_api",
  ];
  expect(tableOf(offer, "task")).toEqual({
    "all/all": [[...on, "antigravity_cli"], 50],
    "all/ready": [ready, 48],
    "all/setup": [[...setupOn, "antigravity_cli"], 2],
    "on/all": [on, 50],
    "on/ready": [ready, 48],
    "on/setup": [setupOn, 2],
    "off/all": [["antigravity_cli"], 0],
    "off/ready": [[], 0],
    "off/setup": [["antigravity_cli"], 0],
  });
  // A conversation offers the lane on this computer only the two of its
  // list the catalog names, not the one added by name.
  expect(tableOf(offer, "conversation")).toEqual({
    "all/all": [[...on, "antigravity_cli"], 49],
    "all/ready": [ready, 47],
    "all/setup": [[...setupOn, "antigravity_cli"], 2],
    "on/all": [on, 49],
    "on/ready": [ready, 47],
    "on/setup": [setupOn, 2],
    "off/all": [["antigravity_cli"], 0],
    "off/ready": [[], 0],
    "off/setup": [["antigravity_cli"], 0],
  });
});

// The keyboard, over a matrix written out by hand: a lane of two rows, one
// taking two efforts and one none, then a lane of one row.
const row = (
  key: string,
  efforts: MatrixRow["efforts"],
  choosable = true,
): MatrixRow => ({
  key,
  id: key,
  name: key,
  description: null,
  held: choosable,
  efforts,
  defaultEffort: null,
  written: false,
  choosable,
  recommended: false,
});
const lane = (id: string, rows: MatrixRow[]): MatrixLane => ({
  id,
  wayId: null,
  provider: id,
  providerName: id,
  name: id,
  connection: "",
  standing: "ready",
  words: null,
  step: null,
  door: null,
  rows,
  models: rows.length,
});
const COLUMNS: MatrixView["columns"] = ["default", "low", "high"];
const GRID = {
  columns: COLUMNS,
  lanes: [
    lane("one", [row("a", ["low", "high"]), row("b", [])]),
    lane("two", [row("c", ["low"])]),
  ],
};

const at = (rowKey: string, column: MatrixView["columns"][number]) => ({
  row: rowKey,
  column,
});

test("the keyboard moves along a row's cells, between rows and between lanes", () => {
  expect(matrixMove(GRID, at("a", "default"), "ArrowRight")).toEqual(
    at("a", "low"),
  );
  expect(matrixMove(GRID, at("a", "high"), "ArrowRight")).toEqual(
    at("a", "high"),
  );
  expect(matrixMove(GRID, at("a", "low"), "ArrowLeft")).toEqual(
    at("a", "default"),
  );
  expect(matrixMove(GRID, at("a", "low"), "End")).toEqual(at("a", "high"));
  expect(matrixMove(GRID, at("a", "high"), "Home")).toEqual(at("a", "default"));
  // Down to a row without that effort lands on its nearest cell before it.
  expect(matrixMove(GRID, at("a", "high"), "ArrowDown")).toEqual(
    at("b", "default"),
  );
  expect(matrixMove(GRID, at("b", "default"), "ArrowDown")).toEqual(
    at("c", "default"),
  );
  expect(matrixMove(GRID, at("a", "low"), "ArrowUp")).toEqual(at("a", "low"));
  expect(matrixMove(GRID, at("c", "low"), "ArrowDown")).toEqual(at("c", "low"));
  // A page is a lane: down to the next lane's first row, up to this lane's
  // first row, or the lane before's from there.
  expect(matrixMove(GRID, at("a", "low"), "PageDown")).toEqual(at("c", "low"));
  expect(matrixMove(GRID, at("c", "low"), "PageDown")).toEqual(at("c", "low"));
  expect(matrixMove(GRID, at("b", "default"), "PageUp")).toEqual(
    at("a", "default"),
  );
  expect(matrixMove(GRID, at("c", "low"), "PageUp")).toEqual(at("a", "low"));
  expect(matrixMove(GRID, at("a", "low"), "PageUp")).toEqual(at("a", "low"));
});

test("the keyboard passes over a row that cannot be chosen, which has no cells", () => {
  // A model this computer does not hold yet sits between two that can be
  // chosen, and a lane of only such a model sits between the two lanes.
  const held = {
    columns: COLUMNS,
    lanes: [
      lane("one", [row("a", ["low"]), row("x", ["low"], false)]),
      lane("waiting", [row("y", ["low", "high"], false)]),
      lane("two", [row("c", ["low"])]),
    ],
  };
  expect(matrixMove(held, at("a", "low"), "ArrowDown")).toEqual(at("c", "low"));
  expect(matrixMove(held, at("c", "low"), "ArrowUp")).toEqual(at("a", "low"));
  expect(matrixMove(held, at("a", "low"), "PageDown")).toEqual(at("c", "low"));
  expect(matrixMove(held, at("c", "low"), "PageUp")).toEqual(at("a", "low"));
  // The keyboard never stands on it, so a move from it stays put.
  expect(matrixMove(held, at("x", "low"), "ArrowDown")).toEqual(at("x", "low"));
});
