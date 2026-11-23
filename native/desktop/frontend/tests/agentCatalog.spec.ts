import { expect, test } from "@playwright/test";
import {
  FIXTURE_CATALOG,
  FIXTURE_DECLARED_CATALOG,
  fixtureModelPresence,
  withEngineHealth,
} from "../src/dev/fixtures/agentCatalog";
import {
  intendedProvider,
  laneSelection,
  modelDisplayName,
  offeredSelection,
  providerModelsToDownload,
  restoredSelection,
  selectionRecord,
  startingSelection,
} from "../src/shell/agentCatalog";
import type {
  ServedCatalogAnswer,
  ServedProviderLane,
} from "../src/shell/agentCatalogContract";
import { agentOffer, catalogStillReading } from "../src/shell/agentOffer";
import { connectionWords } from "../src/shell/providerConnection";

// How the agent column deduces its choices from cadrumo-agent's provider
// catalog, and what it sends back for a run. The catalog is the scenario
// host's, and its providers, lanes and models are all made up. Words are left as their keys.

const words = (key: string) => key;
const offerOf = (catalog: ServedCatalogAnswer) =>
  agentOffer(words, catalog, null, null);
const choices = offerOf(FIXTURE_CATALOG);
const localProvider = (offered: typeof choices) =>
  offered.providers.find((provider) => provider.id === "zai")!;

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

test("a catalog whose every lane states its engine outside the contract is not understood", () => {
  // A running engine that names a reason: the schema admits the fields, the
  // contract does not admit the pairing.
  const engines = withEngineHealth(
    {
      ...FIXTURE_CATALOG,
      providers: FIXTURE_CATALOG.providers?.filter(
        (lane) =>
          lane.provider_id === "llamacpp" || lane.provider_id === "ollama",
      ),
    },
    {
      llamacpp: {
        engine: "llamacpp",
        state: "running",
        reason: "not_reachable",
        door: null,
      },
      ollama: {
        engine: "ollama",
        state: "running",
        reason: null,
        door: "local_ai_setup",
      },
    },
  );
  const offered = offerOf(engines);
  expect(offered.providers).toEqual([]);
  expect(offered.incompatible).toBe(true);
  expect(offeredSelection(offered, null)).toBeNull();
});

test("the first lane that can run is where a conversation starts", () => {
  const start = offeredSelection(choices, null);
  expect(start).toMatchObject({
    providerId: "kimi",
    wayId: "kimi/api",
    modelId: "fixture-deep",
  });
  // Naming no effort leaves it to the provider.
  expect(start?.effort).toBeUndefined();
});

test("a model's default effort is the provider's to apply, so a selection holds none until one is chosen", () => {
  const beta = choices.providers.find((held) => held.id === "qwen");
  const cli = beta?.ways.find((way) => way.transport === "cli");
  const model = choices.models["qwen/cli"]?.find(
    (held) => held.id === "fixture-ultra",
  );
  expect(model?.defaultEffort).toBe("high");
  const start =
    beta && cli
      ? startingSelection(beta, cli, choices.models["qwen/cli"] ?? [])
      : null;
  expect(start).toEqual({
    providerId: "qwen",
    wayId: "qwen/cli",
    modelId: "fixture-ultra",
  });
  if (!start) return;
  // No effort is sent, so the service applies the model's own.
  expect(selectionRecord(choices, start)).toEqual({
    provider: "qwen",
    transport: "cli",
    model: "fixture-ultra",
  });
});

test("a run is named by provider, transport, model and effort, and nothing else", () => {
  const record = selectionRecord(choices, {
    providerId: "kimi",
    wayId: "kimi/api",
    modelId: "fixture-deep",
    effort: "max",
  });
  expect(record).toEqual({
    provider: "kimi",
    transport: "api",
    model: "fixture-deep",
    effort: "max",
  });
  const cli = selectionRecord(choices, {
    providerId: "qwen",
    wayId: "qwen/cli",
    modelId: "fixture-tiered",
  });
  expect(cli).toEqual({
    provider: "qwen",
    transport: "cli",
    model: "fixture-tiered",
  });
  expect(Object.keys(cli ?? {})).toEqual(["provider", "transport", "model"]);
  // An effort the model does not take is not sent with it.
  expect(
    selectionRecord(choices, {
      providerId: "kimi",
      wayId: "kimi/api",
      modelId: "fixture-quick",
      effort: "max",
    })?.effort,
  ).toBeUndefined();
  // A model the way does not list is not a run.
  expect(
    selectionRecord(choices, {
      providerId: "kimi",
      wayId: "kimi/api",
      modelId: "fixture-beta-only",
    }),
  ).toBeNull();
});

test("the efforts of a way follow its model", () => {
  const efforts = (way: string, model: string) =>
    choices.models[way]
      ?.find((held) => held.id === model)
      ?.efforts.map((effort) => effort.id);
  expect(efforts("kimi/api", "fixture-deep")).toEqual([
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
  ]);
  expect(efforts("kimi/api", "fixture-quick")).toEqual(["low", "medium"]);
  expect(efforts("kimi/api", "fixture-plain")).toEqual([]);
  expect(efforts("qwen/api", "fixture-coder")).toEqual([]);
  expect(efforts("qwen/cli", "fixture-ultra")).toEqual(["high", "ultra"]);
  // A selection keeps its effort only while the model takes it.
  const kept = offeredSelection(choices, {
    providerId: "kimi",
    wayId: "kimi/api",
    modelId: "fixture-quick",
    effort: "max",
  });
  expect(kept?.effort).not.toBe("max");
});

test("a provider that lists no models has its model written, with the efforts its row declares", () => {
  const gateway = choices.providers.find((held) => held.id === "zhipu");
  const way = gateway?.ways[0];
  expect(way?.modelWritten?.efforts.map((effort) => effort.id)).toEqual([
    "max",
  ]);
  expect(choices.models["zhipu/cli"]).toEqual([]);
  const select = (modelId: string, effort?: "low" | "max") => ({
    providerId: "zhipu",
    wayId: "zhipu/cli",
    modelId,
    ...(effort ? { effort } : {}),
  });
  expect(selectionRecord(choices, select("  a-model  ", "max"))).toEqual({
    provider: "zhipu",
    transport: "cli",
    model: "a-model",
    effort: "max",
  });
  // An effort the row does not declare is not sent, and no model is no run.
  expect(
    selectionRecord(choices, select("a-model", "low"))?.effort,
  ).toBeUndefined();
  expect(selectionRecord(choices, select("   "))).toBeNull();
  expect(selectionRecord(choices, select("bad\u0007id"))).toBeNull();
});

test("a lane that is held back stays, saying why, and cannot be chosen", () => {
  const byId = (id: string) => choices.providers.find((held) => held.id === id);
  expect(byId("deepseek")?.selectable).toBe(false);
  expect(byId("deepseek")?.ways[0]?.unavailableReason).toBe(
    "desktop.agent.lane_not_configured",
  );
  const alpha = byId("kimi");
  expect(alpha?.selectable).toBe(true);
  expect(alpha?.ways.map((way) => way.selectable)).toEqual([true, false]);
  expect(alpha?.ways[1]?.unavailableReason).toBe(
    "desktop.agent.lane_signed_out",
  );
  // A selection of a held way is not kept.
  expect(
    offeredSelection(choices, {
      providerId: "kimi",
      wayId: "kimi/cli",
      modelId: "x",
    })?.wayId,
  ).toBe("kimi/api");
});

test("what a way has been proven to do is the way's, and no model's", () => {
  const alpha = choices.providers.find((held) => held.id === "kimi");
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
    (lane) => lane.provider_id === "qwen" && lane.transport === "cli",
  );
  const api = catalog.providers?.find(
    (lane) => lane.provider_id === "qwen" && lane.transport === "api",
  );
  expect(cli).toBeDefined();
  expect(api).toBeDefined();
  if (!cli || !api) return;

  // A stale/incorrect selectable bit cannot turn an unauthenticated installed
  // CLI into a runnable choice.
  cli.health = { ...cli.health, authentication: "unauthenticated" };
  const signedOut = offerOf(catalog).providers.find(
    (provider) => provider.id === "qwen",
  );
  expect(
    signedOut?.ways.find((way) => way.transport === "cli")?.selectable,
  ).toBe(false);

  // API auth may be not applicable only when the agent also says the lane has
  // configured credentials and all other health checks passed.
  api.health = { ...api.health, authentication: "not_applicable" };
  const apiWay = offerOf(catalog)
    .providers.find((provider) => provider.id === "qwen")
    ?.ways.find((way) => way.transport === "api");
  expect(apiWay?.selectable).toBe(true);

  api.health = { ...api.health, configured: "unknown" };
  const unconfigured = offerOf(catalog)
    .providers.find((provider) => provider.id === "qwen")
    ?.ways.find((way) => way.transport === "api");
  expect(unconfigured?.selectable).toBe(false);
});

test("person-facing capabilities are localized; machinery proofs are skipped", () => {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const alpha = catalog.providers?.find(
    (lane) => lane.provider_id === "kimi" && lane.transport === "api",
  );
  expect(alpha).toBeDefined();
  if (!alpha) return;

  alpha.capability_proofs = [
    ...(alpha.capability_proofs ?? []),
    { capability: "subagents", state: "proven" },
    { capability: "subagent_cancel", state: "proven" },
    { capability: "subagent_limits", state: "proven" },
  ];

  const provider = offerOf(catalog).providers.find(
    (held) => held.id === "kimi",
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
    (lane) => lane.provider_id === "kimi" && lane.transport === "api",
  );
  expect(alpha).toBeDefined();
  if (!alpha) return;

  alpha.catalog.models![0]!.multi_agent_generation = "v1";
  alpha.capability_proofs = [
    ...(alpha.capability_proofs ?? []),
    { capability: "subagents", generation: "v1", state: "proven" },
    { capability: "subagent_cancel", generation: "v1", state: "proven" },
  ];

  const provider = offerOf(catalog).providers.find(
    (held) => held.id === "kimi",
  );
  expect(provider?.ways[0]?.capabilities).toEqual([
    "desktop.agent.can_search_web",
    "desktop.agent.can_read_pdfs",
  ]);
});

// Whether this computer holds a model is the served catalog's `installed`,
// never the column's guess. The made-up local lane serves one recommended
// model as not downloaded.
const LOCAL = "zai/api";
const servedLocal = () =>
  (FIXTURE_CATALOG.providers ?? []).find(
    (lane) => `${lane.provider_id}/${lane.transport}` === LOCAL,
  );
const absent = () =>
  (servedLocal()?.catalog.models ?? []).filter(
    (entry) => entry.installed === false,
  );

test("a model the catalog says this computer lacks is listed, marked and never chosen", () => {
  expect(absent().length).toBeGreaterThan(0);
  const missing = absent()[0]!;
  const listed = choices.models[LOCAL] ?? [];
  const shown = listed.find((model) => model.id === missing.entry_id);
  expect(shown?.installed).toBe(false);
  // Every model the catalog does not mark stays choosable as it was.
  for (const model of listed)
    if (model.id !== missing.entry_id) expect(model.installed).toBeUndefined();
  const local = choices.providers
    .flatMap((provider) => provider.ways)
    .find((way) => way.id === LOCAL);
  expect(local?.selectable).toBe(true);
  expect(local?.modelsToDownload).toBe(true);
  expect(providerModelsToDownload(localProvider(choices))).toBe(true);
  // Only a lane on this computer has a model to download: no hosted provider
  // does.
  const hosted = choices.providers.filter((provider) =>
    provider.ways.every((way) => way.authKind !== "none"),
  );
  expect(hosted.length).toBeGreaterThan(0);
  for (const provider of hosted)
    expect(providerModelsToDownload(provider)).toBe(false);
  const chosen = {
    providerId: "zai",
    wayId: LOCAL,
    modelId: missing.entry_id,
  };
  // A run never names it, and a kept choice of it is not restored.
  expect(selectionRecord(choices, chosen)).toBeNull();
  const restored = restoredSelection(choices, [chosen]);
  expect(restored?.modelId).not.toBe(missing.entry_id);
  expect(offeredSelection(choices, chosen)?.modelId).not.toBe(missing.entry_id);
});

test("whether a lane has a model to download is the service's model_download, not a model the window finds missing", () => {
  const served = (lanes: (lane: ServedProviderLane) => ServedProviderLane) =>
    offerOf({
      ...FIXTURE_CATALOG,
      providers: (FIXTURE_CATALOG.providers ?? []).map(lanes),
    });
  const localWay = (catalog: ReturnType<typeof offerOf>) =>
    catalog.providers
      .flatMap((provider) => provider.ways)
      .find((way) => way.id === LOCAL);
  expect(servedLocal()?.model_download).toBe("required");
  // A lane the service says downloads nothing has no model to download, even
  // where one of its models is marked as not held.
  const none = served((lane) =>
    `${lane.provider_id}/${lane.transport}` === LOCAL
      ? { ...lane, model_download: "none" }
      : lane,
  );
  expect(localWay(none)?.modelsToDownload).toBeUndefined();
  expect(providerModelsToDownload(localProvider(none))).toBe(false);
  // A lane that downloads its models, all of them held, has none to download.
  const held = served((lane) => ({
    ...lane,
    catalog: {
      ...lane.catalog,
      models: lane.catalog.models?.map((entry) => ({
        ...entry,
        installed: true,
      })),
    },
  }));
  expect(localWay(held)?.modelsToDownload).toBeUndefined();
  // Every hosted lane is served as downloading none.
  for (const lane of FIXTURE_CATALOG.providers ?? [])
    if (
      `${lane.provider_id}/${lane.transport}` !== LOCAL &&
      !lane.health.engine
    )
      expect(lane.model_download).toBe("none");
});

test("a way starts with a model this computer holds, even where the catalog recommends one it lacks", () => {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const local = catalog.providers?.find(
    (lane) => `${lane.provider_id}/${lane.transport}` === LOCAL,
  );
  const missing = absent()[0]!;
  local!.catalog.recommended_entry_id = missing.entry_id;
  const offered = offerOf(catalog);
  const provider = offered.providers.find((held) => held.id === "zai")!;
  const way = provider.ways.find((held) => held.id === LOCAL)!;
  const start = startingSelection(provider, way, offered.models[LOCAL] ?? []);
  expect(start).not.toBeNull();
  expect(start?.modelId).not.toBe(missing.entry_id);
  expect(
    (offered.models[LOCAL] ?? []).find((model) => model.id === start?.modelId)
      ?.installed,
  ).toBeUndefined();
});

test("with no model of the local lane on this computer, the lane cannot be chosen and says why", () => {
  const presence = fixtureModelPresence();
  for (const entry of servedLocal()?.catalog.models ?? [])
    presence.mark(entry.model, false);
  const served = presence.report(FIXTURE_CATALOG);
  const offered = offerOf(served);
  const local = offered.providers
    .flatMap((provider) => provider.ways)
    .find((way) => way.id === LOCAL);
  expect(local?.selectable).toBe(false);
  expect(local?.unavailableReason).toBe(
    "desktop.agent.lane_no_installed_model",
  );
  expect(local?.modelsToDownload).toBe(true);
  expect(providerModelsToDownload(localProvider(offered))).toBe(true);
  for (const model of offered.models[LOCAL] ?? [])
    expect(model.installed).toBe(false);
  // No kept choice of the lane survives, and a run never names its models.
  const kept = {
    providerId: "zai",
    wayId: LOCAL,
    modelId: servedLocal()!.catalog.models![0]!.entry_id,
  };
  expect(restoredSelection(offered, [kept])?.wayId).not.toBe(LOCAL);
  expect(selectionRecord(offered, kept)).toBeNull();
  // A lane held for another reason keeps that reason.
  expect(
    offered.providers
      .flatMap((provider) => provider.ways)
      .find((way) => way.id === "kimi/cli")?.unavailableReason,
  ).toBe("desktop.agent.lane_signed_out");
});

// What a lane is authenticated with is the catalogue's to state, on every lane
// and from a closed set; the lane's name and transport say nothing of it.

const laneNamed = (provider: string, transport: string) =>
  FIXTURE_CATALOG.providers?.find(
    (lane) => lane.provider_id === provider && lane.transport === transport,
  ) as ServedProviderLane;

test("a way carries what its lane is served to authenticate with, not what its transport or name suggests", () => {
  const ways = choices.providers.flatMap((provider) => provider.ways);
  for (const way of ways) {
    const [provider, transport] = way.id.split("/");
    expect(way.authKind).toBe(
      laneNamed(provider ?? "", transport ?? "").auth_kind,
    );
  }
  const kinds = new Map(ways.map((way) => [way.id, way.authKind]));
  expect(kinds.get("llamacpp/api")).toBe("none");
  expect(kinds.get("ollama/api")).toBe("none");
  expect(kinds.get("kimi/api")).toBe("api_key");
  expect(kinds.get("qwen/cli")).toBe("provider_sign_in_only");
});

test("a keyless lane is worded as on this computer and a keyed one by how it is reached, whatever its transport", () => {
  const way = (transport: "api" | "cli", authKind: string) =>
    ({ transport, authKind }) as Parameters<typeof connectionWords>[1];
  expect(connectionWords(words, way("api", "none"))).toBe(
    "desktop.providers.connection_local",
  );
  expect(connectionWords(words, way("cli", "none"))).toBe(
    "desktop.providers.connection_local",
  );
  expect(connectionWords(words, way("api", "api_key"))).toBe(
    "desktop.providers.connection_api",
  );
  expect(connectionWords(words, way("api", "api_key_with_base_url"))).toBe(
    "desktop.providers.connection_api",
  );
  expect(connectionWords(words, way("cli", "provider_sign_in_only"))).toBe(
    "desktop.providers.connection_app",
  );
});

test("a declared lane carries what the declared catalogue states it authenticates with", () => {
  const declared = offerOf(FIXTURE_DECLARED_CATALOG);
  const ways = declared.providers.flatMap((provider) => provider.ways);
  expect(ways.find((way) => way.id === "llamacpp/api")?.authKind).toBe("none");
  expect(ways.find((way) => way.id === "kimi/api")?.authKind).toBe("api_key");
  expect(declared.incompatible).toBe(false);
});

test("the provider the person is on is the one kept, even where none of its ways can run, else the first served", () => {
  const presence = fixtureModelPresence();
  for (const entry of servedLocal()?.catalog.models ?? [])
    presence.mark(entry.model, false);
  const offered = offerOf(presence.report(FIXTURE_CATALOG));
  const kept = (providerId: string, wayId: string) => ({
    providerId,
    wayId,
    modelId: "",
  });
  // A kept choice of a way held back still names its provider.
  expect(intendedProvider(offered, [kept("kimi", "kimi/cli")])?.id).toBe(
    "kimi",
  );
  expect(intendedProvider(offered, [kept("zai", LOCAL)])?.id).toBe("zai");
  // The first that names a provider the catalog serves.
  expect(
    intendedProvider(offered, [
      null,
      kept("retired", "retired/api"),
      kept("zai", LOCAL),
      kept("kimi", "kimi/cli"),
    ])?.id,
  ).toBe("zai");
  // Nothing kept: where a start begins, the first provider served.
  expect(intendedProvider(offered, [null, undefined])?.id).toBe(
    offered.providers[0]?.id,
  );
  expect(
    intendedProvider({ ...offered, providers: [] }, [null]),
  ).toBeUndefined();
});

/** The fixture catalog with `lane` stated as `change` says. */
function withLane(
  provider: string,
  transport: string,
  change: (lane: ServedProviderLane) => void,
) {
  const catalog = structuredClone(FIXTURE_CATALOG);
  const lane = catalog.providers?.find(
    (held) => held.provider_id === provider && held.transport === transport,
  );
  if (!lane) throw new Error(`The fixture catalog has no ${provider} lane.`);
  change(lane);
  return catalog;
}

test("a lane held back says the step the person can take, from the catalog's own reason", () => {
  const way = (offered: typeof choices, id: string) =>
    offered.providers.flatMap((held) => held.ways).find((one) => one.id === id);
  // Signed out: sign in. Not configured or unreachable: nothing to do here.
  expect(way(choices, "kimi/cli")?.heldStep).toBe("sign_in");
  expect(way(choices, "deepseek/cli")?.heldStep).toBeUndefined();
  expect(way(choices, "antigravity/cli")?.heldStep).toBeUndefined();
  // A lane whose models were not read: ask again.
  const unread = offerOf(
    withLane("qwen", "api", (lane) => {
      lane.health.selectable = false;
      lane.health.catalog = "unknown";
    }),
  );
  expect(way(unread, "qwen/api")?.selectable).toBe(false);
  expect(way(unread, "qwen/api")?.unavailableReason).toBe(
    "desktop.agent.lane_no_catalog",
  );
  expect(way(unread, "qwen/api")?.heldStep).toBe("retry");
  // A lane that can be chosen has none.
  expect(way(choices, "kimi/api")?.heldStep).toBeUndefined();
  // A declared lane is not yet observed: ask again.
  const declared = offerOf(FIXTURE_DECLARED_CATALOG);
  expect(
    declared.providers.flatMap((held) => held.ways).map((one) => one.heldStep),
  ).not.toContain(undefined);
});

test("a catalog is still being read while a lane waits on the service's reading, and not while a settled cause holds it", () => {
  expect(catalogStillReading(FIXTURE_CATALOG)).toBe(false);
  // The packaged model list in place of the account's.
  expect(
    catalogStillReading(
      withLane("kimi", "api", (lane) => {
        lane.catalog.model_list_source = "packaged";
        lane.catalog.state.status = "stale";
      }),
    ),
  ).toBe(true);
  // Models not yet read.
  expect(
    catalogStillReading(
      withLane("qwen", "api", (lane) => {
        lane.health.selectable = false;
        lane.health.catalog = "unknown";
        lane.catalog.state.status = "unknown";
      }),
    ),
  ).toBe(true);
  // A sign-in not yet read, on a lane that is otherwise configured.
  expect(
    catalogStillReading(
      withLane("qwen", "api", (lane) => {
        lane.health.selectable = false;
        lane.health.authentication = "unknown";
      }),
    ),
  ).toBe(true);
  // The account's own list, not observed again in time, and a launcher not
  // yet measured.
  expect(
    catalogStillReading(
      withLane("qwen", "api", (lane) => {
        lane.health.selectable = false;
        lane.health.catalog = "stale";
        lane.catalog.state.status = "stale";
        lane.health.admission = "unknown";
      }),
    ),
  ).toBe(true);
  // The same, on a lane that is not configured, signed out, unreachable or
  // not admitted: the service has settled why it cannot be chosen.
  for (const settled of [
    { configured: "unavailable" },
    { authentication: "unauthenticated" },
    { transport: "unavailable" },
    { admission: "not_admitted" },
  ] as const)
    expect(
      catalogStillReading(
        withLane("qwen", "api", (lane) => {
          lane.health.selectable = false;
          lane.health.authentication = "unknown";
          Object.assign(lane.health, settled);
        }),
      ),
    ).toBe(false);
  // A lane that can be chosen is not being read, whatever an axis says.
  expect(
    catalogStillReading(
      withLane("qwen", "api", (lane) => {
        lane.health.authentication = "unknown";
      }),
    ),
  ).toBe(false);
});

test("a choice the catalog stops offering for a while is offered again, whole, when the lane returns", () => {
  const chosen = {
    providerId: "qwen",
    wayId: "qwen/api",
    modelId: "fixture-chat",
  };
  expect(restoredSelection(choices, [chosen])).toEqual(chosen);
  const away = offerOf(
    withLane("qwen", "api", (lane) => {
      lane.health.selectable = false;
      lane.health.catalog = "unknown";
    }),
  );
  // While it is held back the start is another lane: nothing is sent on it.
  expect(restoredSelection(away, [chosen])?.wayId).not.toBe("qwen/api");
  // A conversation fixed to the lane is refused altogether.
  expect(laneSelection(away, [chosen], "qwen/api")).toBeNull();
  // The choice, held by the column, is the same once the lane returns.
  expect(restoredSelection(choices, [chosen])).toEqual(chosen);
  expect(laneSelection(choices, [chosen], "qwen/api")).toEqual(chosen);
});

test("a model is named as the picker names it in its lane, and by its id only where the catalog lists none", () => {
  const lane = FIXTURE_CATALOG.providers?.find(
    (held) => `${held.provider_id}/${held.transport}` === "kimi/api",
  );
  const listed = lane?.catalog.models?.find(
    (held) => held.model === "fixture-deep",
  );
  expect(listed?.display_name).toBeTruthy();
  expect(modelDisplayName(choices, "kimi/api", "fixture-deep")).toBe(
    listed?.display_name,
  );
  // The same id on a lane that does not list it, a lane the catalog does not
  // serve, and no lane at all each give the id back.
  expect(modelDisplayName(choices, "qwen/api", "fixture-deep")).toBe(
    "fixture-deep",
  );
  expect(modelDisplayName(choices, "none/api", "fixture-deep")).toBe(
    "fixture-deep",
  );
  expect(modelDisplayName(choices, null, "fixture-deep")).toBe("fixture-deep");
  expect(
    modelDisplayName(offerOf(FIXTURE_DECLARED_CATALOG), "kimi/api", "x"),
  ).toBe("x");
});
