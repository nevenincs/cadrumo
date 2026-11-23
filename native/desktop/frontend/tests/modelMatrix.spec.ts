import { expect, test } from "@playwright/test";
import { fixtureOfferReads } from "../src/dev/agentFixtureModels";
import {
  matrixMove,
  matrixView,
  STARTING_FILTERS,
  type MatrixLane,
  type MatrixRow,
  type MatrixView,
} from "../src/components/agent/modelMatrixView";
import { agentOffer } from "../src/shell/agentOffer";

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
  // A lane not set up says why; its models are still listed, none choosable.
  const signedOut = view.lanes.find((lane) => lane.id === "kimi_cli");
  expect(signedOut?.words).toBe("desktop.agent.lane_signed_out");
  const engine = view.lanes.find((lane) => lane.id === "llamacpp_api");
  expect(engine?.rows.map((row) => [row.id, row.choosable])).toEqual([
    ["synthetic-llamacpp-vision:1", false],
    ["synthetic-llamacpp:1", false],
  ]);
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
    ["example-added:7b", true, true],
  ]);
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
  const none = matrixView(words, offer, "task", "nothing", STARTING_FILTERS);
  expect(none.lanes).toEqual([]);
  expect(none.rows).toBe(0);
  expect(none.offHidden).toBe(0);
});

test("the filters keep lanes on or off, ready or needing setup", () => {
  const off = matrixView(words, offer, "task", "", {
    on: false,
    off: true,
    ready: false,
    setup: false,
  });
  expect(ids(off)).toEqual(["antigravity_cli"]);
  expect(off.lanes[0]?.standing).toBe("off");
  expect(off.lanes[0]?.step).toBe("set_up");
  expect(off.offHidden).toBe(0);
  const ready = matrixView(words, offer, "task", "", {
    ...STARTING_FILTERS,
    ready: true,
  });
  expect(ids(ready)).toEqual(["kimi_api", "qwen_api", "qwen_cli", "zai_api"]);
  const setup = matrixView(words, offer, "task", "", {
    ...STARTING_FILTERS,
    setup: true,
  });
  expect(ids(setup)).toEqual(["kimi_cli", "deepseek_cli", "llamacpp_api"]);
  // Both of a pair pressed, or neither, keeps both.
  const both = matrixView(words, offer, "task", "", {
    on: true,
    off: true,
    ready: false,
    setup: false,
  });
  expect(both.lanes).toHaveLength(8);
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

// The keyboard, over a matrix written out by hand: a lane of two rows, one
// taking two efforts and one none, then a lane of one row.
const row = (key: string, efforts: MatrixRow["efforts"]): MatrixRow => ({
  key,
  id: key,
  name: key,
  description: null,
  held: true,
  efforts,
  defaultEffort: null,
  written: false,
  choosable: true,
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
});
const GRID = {
  columns: ["default", "low", "high"] as MatrixView["columns"],
  lanes: [
    lane("one", [row("a", ["low", "high"]), row("b", [])]),
    lane("two", [row("c", ["low"])]),
  ],
};

test("the keyboard moves along a row's cells, between rows and between lanes", () => {
  const at = (rowKey: string, column: MatrixView["columns"][number]) => ({
    row: rowKey,
    column,
  });
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
