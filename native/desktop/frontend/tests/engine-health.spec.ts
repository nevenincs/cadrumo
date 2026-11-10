import { expect, test } from "@playwright/test";
import {
  FIXTURE_CATALOG,
  withEngineHealth,
  type FixtureEngineHealth,
} from "../src/dev/fixtures/agentCatalog";
import { catalogChoices, laneEngines } from "../src/shell/agentCatalog";
import {
  parseEngineHealth,
  type AgentProviderLane,
} from "../src/shell/agentSession";
import {
  engineDoorWords,
  engineNotRunningWords,
} from "../src/shell/engineHealth";
import { catalogLanes } from "../src/shell/localModelLanes";

// What the catalog states of a local engine: only the API lane of an engine
// states one, a running engine names neither a reason nor a door, one that
// does not run names both, and anything else is a malformed answer whose lane
// is not offered. An engine that does not run is said before the transport
// that follows from it. Words are left as their keys, with the pieces a
// composed line is made of.

const words = (key: string, values?: Record<string, string | number>) =>
  values ? `${key}${JSON.stringify(values)}` : key;

const DOWN = {
  engine: "llamacpp",
  state: "not_running",
  reason: "not_reachable",
  door: "local_ai_setup",
};
const UP = { engine: "llamacpp", state: "running", reason: null, door: null };

const served = (health: FixtureEngineHealth) =>
  withEngineHealth(FIXTURE_CATALOG, health);
const laneOf = (provider: string, health: FixtureEngineHealth) =>
  served(health).providers?.find(
    (lane) => lane.provider_id === provider && lane.transport === "api",
  ) as AgentProviderLane;
const llamacpp = (stated: unknown) => laneOf("llamacpp", { llamacpp: stated });

test("a lane states its engine running, not running, or not at all", () => {
  expect(parseEngineHealth(llamacpp(UP))).toEqual(UP);
  expect(parseEngineHealth(llamacpp(DOWN))).toEqual(DOWN);
  expect(parseEngineHealth(llamacpp(null))).toBeNull();
  // A lane that is no engine's states none.
  const alpha = FIXTURE_CATALOG.providers?.find(
    (lane) => lane.provider_id === "alpha" && lane.transport === "api",
  ) as AgentProviderLane;
  expect(parseEngineHealth(alpha)).toBeNull();
  const unstated = { ...alpha, health: { ...alpha.health } };
  delete unstated.health.engine;
  expect(parseEngineHealth(unstated)).toBeNull();
});

test("each reason a not running engine can name is accepted, and a door the window does not know is kept", () => {
  for (const reason of [
    "no_answer_in_time",
    "not_reachable",
    "answer_unreadable",
  ]) {
    expect(parseEngineHealth(llamacpp({ ...DOWN, reason }))).toEqual({
      ...DOWN,
      reason,
    });
  }
  const unknownDoor = parseEngineHealth(llamacpp({ ...DOWN, door: "other" }));
  expect(unknownDoor).toEqual({ ...DOWN, door: "other" });
});

test("an answer outside the contract is malformed", () => {
  for (const stated of [
    { ...UP, reason: "not_reachable" },
    { ...UP, door: "local_ai_setup" },
    { ...UP, reason: undefined },
    { ...DOWN, reason: null },
    { ...DOWN, door: null },
    { ...DOWN, door: "" },
    { ...DOWN, reason: "unplugged" },
    { ...DOWN, state: "stopped" },
    { ...UP, state: "Running" },
    { ...UP, engine: "vllm" },
    { ...UP, engine: "ollama" },
    { ...DOWN, engine: 1 },
    "running",
    1,
    true,
    [DOWN],
  ]) {
    expect(parseEngineHealth(llamacpp(stated)), JSON.stringify(stated)).toBe(
      "malformed",
    );
  }
  // The command-line lane of a provider states no engine.
  const cli = {
    ...llamacpp(UP),
    transport: "cli" as const,
  };
  expect(parseEngineHealth(cli)).toBe("malformed");
});

test("an engine that does not run is said before the transport and its lane cannot be chosen", () => {
  const catalog = served({
    llamacpp: DOWN,
    ollama: { ...DOWN, engine: "ollama" },
  });
  const offered = catalogChoices(words, catalog);
  for (const provider of ["llamacpp", "ollama"]) {
    const way = offered.providers
      .find((held) => held.id === provider)
      ?.ways.find((held) => held.id === `${provider}/api`);
    expect(way?.selectable).toBe(false);
    // The lane's transport is unavailable too, and is not what is said.
    expect(way?.unavailableReason).toContain(
      "desktop.agent.engine_not_running",
    );
    expect(way?.unavailableReason).toContain(
      "desktop.agent.engine_reason_not_reachable",
    );
    expect(way?.unavailableReason).not.toContain(
      "desktop.agent.lane_unreachable",
    );
    expect(way?.engineNotRunning).toEqual({
      words: way?.unavailableReason,
      door: "local_ai_setup",
    });
  }
});

test("a running engine, or none stated, leaves the lane as it was and says nothing", () => {
  const offered = catalogChoices(words, served({ llamacpp: UP, ollama: null }));
  for (const provider of ["llamacpp", "ollama"]) {
    const way = offered.providers
      .find((held) => held.id === provider)
      ?.ways.find((held) => held.id === `${provider}/api`);
    expect(way?.selectable).toBe(true);
    expect(way?.unavailableReason).toBeUndefined();
    expect(way?.engineNotRunning).toBeUndefined();
  }
  expect(engineNotRunningWords(words, UP as never)).toBeNull();
});

test("the words name the reason by a whole key, and only a known door has any", () => {
  for (const reason of [
    "no_answer_in_time",
    "not_reachable",
    "answer_unreadable",
  ] as const) {
    expect(
      engineNotRunningWords(words, { ...DOWN, reason } as never),
    ).toContain(`desktop.agent.engine_reason_${reason}`);
  }
  expect(engineNotRunningWords(words, DOWN as never)).toContain(
    "desktop.agent.engine_not_running",
  );
  expect(engineDoorWords(words, "local_ai_setup")).toBe(
    "desktop.agent.engine_door_local_ai_setup",
  );
  expect(engineDoorWords(words, "other")).toBeNull();
  expect(engineDoorWords(words, "constructor")).toBeNull();
});

test("a lane with a malformed engine answer is not offered, here or in the model lists", () => {
  const catalog = served({ llamacpp: { ...DOWN, reason: "unplugged" } });
  const offered = catalogChoices(words, catalog);
  expect(offered.providers.some((held) => held.id === "llamacpp")).toBe(false);
  expect(offered.providers.some((held) => held.id === "ollama")).toBe(true);
  expect(
    catalogLanes(catalog).some((held) => held.provider === "llamacpp"),
  ).toBe(false);
  expect(laneEngines(catalog)).not.toHaveProperty("llamacpp_api");
});

test("the engines stated are keyed by lane", () => {
  expect(laneEngines(served({ llamacpp: DOWN, ollama: null }))).toEqual({
    llamacpp_api: DOWN,
  });
  expect(laneEngines(FIXTURE_CATALOG)).toEqual({
    llamacpp_api: UP,
    ollama_api: { ...UP, engine: "ollama" },
  });
});
