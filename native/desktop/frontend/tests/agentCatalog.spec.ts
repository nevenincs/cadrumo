import { expect, test } from "@playwright/test";
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
// host's, and its providers, lanes and models are all made up. Words are left as their keys.

const words = (key: string) => key;
const choices = catalogChoices(words, FIXTURE_CATALOG);

test("a provider is one entry however many lanes reach it", () => {
  const served = FIXTURE_CATALOG.providers ?? [];
  const identities = [...new Set(served.map((lane) => lane.provider_id))];
  expect(choices.providers.map((provider) => provider.id)).toEqual(identities);
  expect(choices.incompatible).toBe(false);
  // Each entry carries the lanes the agent declares for it: the API before the
  // command-line app, and as many as there are.
  for (const provider of choices.providers) {
    const declared = served
      .filter((lane) => lane.provider_id === provider.id)
      .map((lane) => lane.transport);
    expect(provider.ways.map((way) => way.transport)).toEqual(
      [...declared].sort((a, b) => (a === b ? 0 : a === "api" ? -1 : 1)),
    );
  }
  const twoWays = choices.providers.filter(
    (provider) => provider.ways.length > 1,
  );
  expect(twoWays.map((provider) => provider.name)).toEqual([
    "Example Alpha",
    "Example Beta",
  ]);
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
    providerId: "alpha",
    wayId: "alpha/api",
    modelId: "fixture-deep",
  });
  // Naming no effort leaves it to the provider.
  expect(start?.effort).toBeUndefined();
});

test("a model's default effort is the provider's to apply, so a selection holds none until one is chosen", () => {
  const beta = choices.providers.find((held) => held.id === "beta");
  const cli = beta?.ways.find((way) => way.transport === "cli");
  const model = choices.models["beta/cli"]?.find(
    (held) => held.id === "fixture-ultra",
  );
  expect(model?.defaultEffort).toBe("high");
  const start =
    beta && cli
      ? startingSelection(beta, cli, choices.models["beta/cli"] ?? [])
      : null;
  expect(start).toEqual({
    providerId: "beta",
    wayId: "beta/cli",
    modelId: "fixture-ultra",
  });
  if (!start) return;
  // No effort is sent, so the service applies the model's own.
  expect(selectionRecord(FIXTURE_CATALOG, start)).toEqual({
    provider: "beta",
    transport: "cli",
    model: "fixture-ultra",
  });
});

test("a run is named by provider, transport, model and effort, and nothing else", () => {
  const record = selectionRecord(FIXTURE_CATALOG, {
    providerId: "alpha",
    wayId: "alpha/api",
    modelId: "fixture-deep",
    effort: "max",
  });
  expect(record).toEqual({
    provider: "alpha",
    transport: "api",
    model: "fixture-deep",
    effort: "max",
  });
  const cli = selectionRecord(FIXTURE_CATALOG, {
    providerId: "beta",
    wayId: "beta/cli",
    modelId: "fixture-tiered",
  });
  expect(cli).toEqual({
    provider: "beta",
    transport: "cli",
    model: "fixture-tiered",
  });
  expect(Object.keys(cli ?? {})).toEqual(["provider", "transport", "model"]);
  // An effort the model does not take is not sent with it.
  expect(
    selectionRecord(FIXTURE_CATALOG, {
      providerId: "alpha",
      wayId: "alpha/api",
      modelId: "fixture-quick",
      effort: "max",
    })?.effort,
  ).toBeUndefined();
  // A model the way does not list is not a run.
  expect(
    selectionRecord(FIXTURE_CATALOG, {
      providerId: "alpha",
      wayId: "alpha/api",
      modelId: "fixture-beta-only",
    }),
  ).toBeNull();
});

test("the efforts of a way follow its model", () => {
  const efforts = (way: string, model: string) =>
    choices.models[way]
      ?.find((held) => held.id === model)
      ?.efforts.map((effort) => effort.id);
  expect(efforts("alpha/api", "fixture-deep")).toEqual([
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ]);
  expect(efforts("alpha/api", "fixture-quick")).toEqual(["low", "medium"]);
  expect(efforts("alpha/api", "fixture-plain")).toEqual([]);
  expect(efforts("beta/api", "fixture-coder")).toEqual([]);
  expect(efforts("beta/cli", "fixture-ultra")).toEqual(["high", "ultra"]);
  // A selection keeps its effort only while the model takes it.
  const kept = offeredSelection(choices, {
    providerId: "alpha",
    wayId: "alpha/api",
    modelId: "fixture-quick",
    effort: "max",
  });
  expect(kept?.effort).not.toBe("max");
});

test("a provider that lists no models has its model written, with the efforts its row declares", () => {
  const gateway = choices.providers.find((held) => held.id === "gateway");
  const way = gateway?.ways[0];
  expect(way?.modelWritten?.efforts.map((effort) => effort.id)).toEqual([
    "max",
  ]);
  expect(choices.models["gateway/cli"]).toEqual([]);
  const select = (modelId: string, effort?: "low" | "max") => ({
    providerId: "gateway",
    wayId: "gateway/cli",
    modelId,
    ...(effort ? { effort } : {}),
  });
  expect(
    selectionRecord(FIXTURE_CATALOG, select("  a-model  ", "max")),
  ).toEqual({
    provider: "gateway",
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
  expect(byId("delta")?.selectable).toBe(false);
  expect(byId("delta")?.ways[0]?.unavailableReason).toBe(
    "desktop.agent.lane_not_configured",
  );
  const alpha = byId("alpha");
  expect(alpha?.selectable).toBe(true);
  expect(alpha?.ways.map((way) => way.selectable)).toEqual([true, false]);
  expect(alpha?.ways[1]?.unavailableReason).toBe(
    "desktop.agent.lane_signed_out",
  );
  // A selection of a held way is not kept.
  expect(
    offeredSelection(choices, {
      providerId: "alpha",
      wayId: "alpha/cli",
      modelId: "x",
    })?.wayId,
  ).toBe("alpha/api");
});

test("what a way has been proven to do is the way's, and no model's", () => {
  const alpha = choices.providers.find((held) => held.id === "alpha");
  // Tool use is the agent's machinery, not a capability to choose by.
  expect(alpha?.ways[0]?.capabilities).toEqual([
    "desktop.agent.can_search_web",
    "desktop.agent.can_read_pdfs",
  ]);
  for (const models of Object.values(choices.models))
    for (const model of models)
      expect(model).not.toHaveProperty("capabilities");
});

test("provider selection requires live authentication and configuration axes", () => {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const cli = catalog.providers?.find(
    (lane) => lane.provider_id === "beta" && lane.transport === "cli",
  );
  const api = catalog.providers?.find(
    (lane) => lane.provider_id === "beta" && lane.transport === "api",
  );
  expect(cli).toBeDefined();
  expect(api).toBeDefined();
  if (!cli || !api) return;

  // A stale/incorrect selectable bit cannot turn an unauthenticated installed
  // CLI into a runnable choice.
  cli.health = { ...cli.health, authentication: "unauthenticated" };
  const signedOut = catalogChoices(words, catalog).providers.find(
    (provider) => provider.id === "beta",
  );
  expect(
    signedOut?.ways.find((way) => way.transport === "cli")?.selectable,
  ).toBe(false);

  // API auth may be not applicable only when the agent also says the lane has
  // configured credentials and all other health checks passed.
  api.health = { ...api.health, authentication: "not_applicable" };
  const apiWay = catalogChoices(words, catalog)
    .providers.find((provider) => provider.id === "beta")
    ?.ways.find((way) => way.transport === "api");
  expect(apiWay?.selectable).toBe(true);

  api.health = { ...api.health, configured: "unknown" };
  const unconfigured = catalogChoices(words, catalog)
    .providers.find((provider) => provider.id === "beta")
    ?.ways.find((way) => way.transport === "api");
  expect(unconfigured?.selectable).toBe(false);
});

test("person-facing capabilities are localized; machinery and unknown proofs are skipped", () => {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const alpha = catalog.providers?.find(
    (lane) => lane.provider_id === "alpha" && lane.transport === "api",
  );
  expect(alpha).toBeDefined();
  if (!alpha) return;

  alpha.capability_proofs = [
    ...(alpha.capability_proofs ?? []),
    { capability: "subagents", state: "proven" },
    { capability: "subagent_cancel", state: "proven" },
    { capability: "future_capability", state: "proven" },
  ];

  const provider = catalogChoices(words, catalog).providers.find(
    (held) => held.id === "alpha",
  );
  const capabilities = provider?.ways[0]?.capabilities ?? [];
  expect(capabilities).toEqual([
    "desktop.agent.can_search_web",
    "desktop.agent.can_read_pdfs",
  ]);
  expect(() => new Intl.ListFormat("en").format(capabilities)).not.toThrow();
});

test("generation-scoped proofs are not presented as lane-wide capabilities", () => {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const alpha = catalog.providers?.find(
    (lane) => lane.provider_id === "alpha" && lane.transport === "api",
  );
  expect(alpha).toBeDefined();
  if (!alpha) return;

  alpha.catalog.models![0]!.multi_agent_generation = "v1";
  alpha.capability_proofs = [
    ...(alpha.capability_proofs ?? []),
    { capability: "subagents", generation: "v1", state: "proven" },
    { capability: "subagent_cancel", generation: "v1", state: "proven" },
  ];

  const provider = catalogChoices(words, catalog).providers.find(
    (held) => held.id === "alpha",
  );
  expect(provider?.ways[0]?.capabilities).toEqual([
    "desktop.agent.can_search_web",
    "desktop.agent.can_read_pdfs",
  ]);
});
