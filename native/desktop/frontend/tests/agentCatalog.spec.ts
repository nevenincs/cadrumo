import { expect, test } from "@playwright/test";
import { DECLARED_LANES } from "../src/dev/fixtures/agentLanes.generated";
import { FIXTURE_CATALOG } from "../src/dev/fixtures/agentCatalog";
import {
  catalogChoices,
  offeredSelection,
  selectionRecord,
  startingSelection,
} from "../src/shell/agentCatalog";
import type { AgentProviderCatalog } from "../src/shell/agentSession";

// How the agent column deduces its choices from cadrumo-agent's provider
// catalog, and what it sends back for a run. The catalog is the scenario
// host's: its lanes are generated from cadrumo-agent, and its models are made
// up and named as fixtures. Words are left as their keys.

const words = (key: string) => key;
const choices = catalogChoices(words, FIXTURE_CATALOG);

test("a provider is one entry however many lanes reach it", () => {
  const identities = [
    ...new Set(DECLARED_LANES.map((lane) => lane.provider_id)),
  ];
  expect(choices.providers.map((provider) => provider.id)).toEqual(identities);
  expect(choices.incompatible).toBe(false);
  // The company behind an API is not a provider next to its product.
  const ids = choices.providers.map((provider) => provider.id);
  expect(ids).not.toContain("anthropic");
  expect(ids).not.toContain("openai");
  // Each entry carries the lanes the agent declares for it: the API before the
  // command-line app, and as many as there are.
  for (const provider of choices.providers) {
    const declared = DECLARED_LANES.filter(
      (lane) => lane.provider_id === provider.id,
    ).map((lane) => lane.transport);
    expect(provider.ways.map((way) => way.transport)).toEqual(
      [...declared].sort((a, b) => (a === b ? 0 : a === "api" ? -1 : 1)),
    );
  }
  const twoWays = choices.providers.filter(
    (provider) => provider.ways.length > 1,
  );
  expect(twoWays.map((provider) => provider.name)).toEqual(["Claude", "Codex"]);
});

test("a lane that says nothing of its provider or transport is not offered", () => {
  // What a service served before it named either: private lane ids, no
  // transport.
  const old = {
    providers: FIXTURE_CATALOG.providers?.map((lane) => {
      const served: Record<string, unknown> = { ...lane };
      delete served.transport;
      return served;
    }),
  } as unknown as AgentProviderCatalog;
  const offered = catalogChoices(words, old);
  expect(offered.providers).toEqual([]);
  expect(offered.incompatible).toBe(true);
  expect(offeredSelection(offered, null)).toBeNull();
});

test("the first lane that can run is where a conversation starts", () => {
  const start = offeredSelection(choices, null);
  expect(start).toMatchObject({
    providerId: "claude",
    wayId: "claude/api",
    modelId: "fixture-deep",
  });
  // Naming no effort leaves it to the provider.
  expect(start?.effort).toBeUndefined();
});

test("a model's default effort is the provider's to apply, so a selection holds none until one is chosen", () => {
  const codex = choices.providers.find((held) => held.id === "codex");
  const cli = codex?.ways.find((way) => way.transport === "cli");
  const model = choices.models["codex/cli"]?.find(
    (held) => held.id === "fixture-ultra",
  );
  expect(model?.defaultEffort).toBe("high");
  const start =
    codex && cli
      ? startingSelection(codex, cli, choices.models["codex/cli"] ?? [])
      : null;
  expect(start).toEqual({
    providerId: "codex",
    wayId: "codex/cli",
    modelId: "fixture-ultra",
  });
  if (!start) return;
  // No effort is sent, so the service applies the model's own.
  expect(selectionRecord(FIXTURE_CATALOG, start)).toEqual({
    provider: "codex",
    transport: "cli",
    model: "fixture-ultra",
  });
});

test("a run is named by provider, transport, model and effort, and nothing else", () => {
  const record = selectionRecord(FIXTURE_CATALOG, {
    providerId: "claude",
    wayId: "claude/api",
    modelId: "fixture-deep",
    effort: "max",
  });
  expect(record).toEqual({
    provider: "claude",
    transport: "api",
    model: "fixture-deep",
    effort: "max",
  });
  const cli = selectionRecord(FIXTURE_CATALOG, {
    providerId: "codex",
    wayId: "codex/cli",
    modelId: "fixture-tiered",
  });
  expect(cli).toEqual({
    provider: "codex",
    transport: "cli",
    model: "fixture-tiered",
  });
  expect(Object.keys(cli ?? {})).toEqual(["provider", "transport", "model"]);
  // An effort the model does not take is not sent with it.
  expect(
    selectionRecord(FIXTURE_CATALOG, {
      providerId: "claude",
      wayId: "claude/api",
      modelId: "fixture-quick",
      effort: "max",
    })?.effort,
  ).toBeUndefined();
  // A model the way does not list is not a run.
  expect(
    selectionRecord(FIXTURE_CATALOG, {
      providerId: "claude",
      wayId: "claude/api",
      modelId: "fixture-codex-only",
    }),
  ).toBeNull();
});

test("the efforts of a way follow its model", () => {
  const efforts = (way: string, model: string) =>
    choices.models[way]
      ?.find((held) => held.id === model)
      ?.efforts.map((effort) => effort.id);
  expect(efforts("claude/api", "fixture-deep")).toEqual([
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ]);
  expect(efforts("claude/api", "fixture-quick")).toEqual(["low", "medium"]);
  expect(efforts("claude/api", "fixture-plain")).toEqual([]);
  expect(efforts("codex/api", "fixture-coder")).toEqual([]);
  expect(efforts("codex/cli", "fixture-ultra")).toEqual(["high", "ultra"]);
  // A selection keeps its effort only while the model takes it.
  const kept = offeredSelection(choices, {
    providerId: "claude",
    wayId: "claude/api",
    modelId: "fixture-quick",
    effort: "max",
  });
  expect(kept?.effort).not.toBe("max");
});

test("a provider that lists no models has its model written, with the efforts its row declares", () => {
  const deepseek = choices.providers.find((held) => held.id === "deepseek");
  const way = deepseek?.ways[0];
  expect(way?.modelWritten?.efforts.map((effort) => effort.id)).toEqual([
    "max",
  ]);
  expect(choices.models["deepseek/cli"]).toEqual([]);
  const select = (modelId: string, effort?: "low" | "max") => ({
    providerId: "deepseek",
    wayId: "deepseek/cli",
    modelId,
    ...(effort ? { effort } : {}),
  });
  expect(
    selectionRecord(FIXTURE_CATALOG, select("  a-model  ", "max")),
  ).toEqual({
    provider: "deepseek",
    transport: "cli",
    model: "a-model",
    effort: "max",
  });
  // An effort the row does not declare is not sent, and no model is no run.
  expect(
    selectionRecord(FIXTURE_CATALOG, select("a-model", "low"))?.effort,
  ).toBeUndefined();
  expect(selectionRecord(FIXTURE_CATALOG, select("   "))).toBeNull();
  expect(selectionRecord(FIXTURE_CATALOG, select("bad\u0007id"))).toBeNull();
});

test("a lane that is held back stays, saying why, and cannot be chosen", () => {
  const byId = (id: string) => choices.providers.find((held) => held.id === id);
  expect(byId("kimi")?.selectable).toBe(false);
  expect(byId("kimi")?.ways[0]?.unavailableReason).toBe(
    "desktop.agent.lane_not_configured",
  );
  const claude = byId("claude");
  expect(claude?.selectable).toBe(true);
  expect(claude?.ways.map((way) => way.selectable)).toEqual([true, false]);
  expect(claude?.ways[1]?.unavailableReason).toBe(
    "desktop.agent.lane_signed_out",
  );
  // A selection of a held way is not kept.
  expect(
    offeredSelection(choices, {
      providerId: "claude",
      wayId: "claude/cli",
      modelId: "x",
    })?.wayId,
  ).toBe("claude/api");
});

test("what a way has been proven to do is the way's, and no model's", () => {
  const claude = choices.providers.find((held) => held.id === "claude");
  expect(claude?.ways[0]?.capabilities).toEqual([
    "desktop.agent.can_use_tools",
    "desktop.agent.can_search_web",
    "desktop.agent.can_read_pdfs",
  ]);
  for (const models of Object.values(choices.models))
    for (const model of models)
      expect(model).not.toHaveProperty("capabilities");
});
