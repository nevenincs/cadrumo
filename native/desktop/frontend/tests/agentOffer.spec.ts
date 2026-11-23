import { expect, test } from "@playwright/test";
import { fixtureInstant } from "../src/dev/fixtureDates";
import { FIXTURE_DECLARED_CATALOG } from "../src/dev/fixtures/agentCatalog";
import {
  ranSelection,
  readingSelection,
  selectionRecord,
} from "../src/shell/agentCatalog";
import type {
  ProviderHealthResponse,
  ServedCatalogModel,
  ServedProviderCatalog,
  ServedProviderLane,
} from "../src/shell/agentCatalogContract";
import {
  agentOffer,
  groupedByProvider,
  laneIdOf,
  offerMatches,
  taskModelsOf,
  wayIdOf,
} from "../src/shell/agentOffer";
import type { LocalModelListStatus } from "../src/shell/localModelsContract";
import type { ProviderSettingsRecord } from "../src/shell/providerSettingsContract";

// The one projection every agent surface reads, over a made-up catalogue of
// several providers: a provider served as its app before its API, a lane not
// configured, one the settings turned off, a keyless local lane with a list,
// a gateway whose models the person writes, one that takes no background
// text, a hosted lane with many models, and one stating its engine outside
// the contract. Every expected value is written out by hand. Words are left
// as their keys.

const words = (key: string) => key;

const CHECKED = fixtureInstant(1, 1, "00:00:00Z");

const OK: ProviderHealthResponse = {
  configured: "available",
  transport: "available",
  authentication: "authenticated",
  catalog: "available",
  admission: "admitted",
  selectable: true,
  checked_at: CHECKED,
};

const model = (
  entry: string,
  id: string,
  name: string,
  more: Partial<ServedCatalogModel> = {},
): ServedCatalogModel => ({
  entry_id: entry,
  model: id,
  display_name: name,
  vision: null,
  size_bytes: null,
  context_length: null,
  licence: null,
  llamacpp_default_context: null,
  ...more,
});

const lane = (
  provider: ServedProviderLane["provider_id"],
  transport: ServedProviderLane["transport"],
  name: string,
  more: Partial<ServedProviderLane> = {},
): ServedProviderLane => ({
  provider_id: provider,
  transport,
  display_name: name,
  auth_kind: "api_key",
  execution_mode: "native",
  executable: true,
  model_source: "catalog",
  health: OK,
  catalog: {
    state: { status: "available", checked_at: CHECKED },
    models: [],
  },
  background_requests: {
    text: "proven",
    image: "unsupported",
    pdf: "unsupported",
    options: [],
    accepts_images: false,
    accepts_pdfs: false,
  },
  model_download: "none",
  ...more,
});

const MANY = Array.from({ length: 40 }, (_, index) =>
  model(
    `deep:${index + 1}`,
    `ex-deep-${index + 1}`,
    `Example Deep ${index + 1}`,
  ),
);

const CATALOG: ServedProviderCatalog = {
  task_kinds: [
    {
      id: "classification",
      display_name: "Classification",
      description: "Sorts things.",
    },
    {
      id: "extraction",
      display_name: "Extraction",
      description: "Reads things.",
    },
  ],
  providers: [
    lane("claude", "cli", "Example Alpha App", {
      auth_kind: "provider_sign_in_only",
      health: { ...OK, authentication: "unauthenticated", selectable: false },
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        models: [model("alpha-cli:pro", "ex-alpha-pro", "Example Alpha Pro")],
      },
    }),
    lane("claude", "api", "Example Alpha", {
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        recommended_entry_id: "alpha:mini",
        models: [
          model("alpha:pro", "ex-alpha-pro", "Example Alpha Pro", {
            description: "The deep one.",
            efforts: ["low", "medium", "high"],
            default_effort: "medium",
          }),
          model("alpha:mini", "ex-alpha-mini", "Example Alpha Mini"),
        ],
      },
      background_requests: {
        text: "proven",
        image: "unsupported",
        pdf: "unsupported",
        options: ["effort"],
        accepts_images: false,
        accepts_pdfs: false,
      },
    }),
    lane("qwen", "api", "Example Gamma", {
      health: { ...OK, configured: "unavailable", selectable: false },
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        models: [model("gamma:1", "ex-gamma-1", "Example Gamma One")],
      },
    }),
    lane("deepseek", "api", "Example Deep", {
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        models: MANY,
      },
    }),
    lane("llamacpp", "api", "Example Local", {
      auth_kind: "none",
      health: {
        ...OK,
        authentication: "not_applicable",
        engine: { engine: "llamacpp", state: "running" },
      },
      model_download: "required",
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        recommended: {
          vision: "ex-local-1",
          text: "ex-local-2",
          code: "ex-local-5",
        },
        models: [
          model("local:1", "ex-local-1", "Example Local One"),
          model("local:2", "ex-local-2", "Example Local Two", {
            installed: false,
          }),
          model("local:3", "ex-local-3", "Example Local Three"),
          model("local:4", "ex-local-4", "Example Local Four", {
            installed: false,
          }),
          model("local:5", "ex-local-5", "Example Local Five"),
          model("local:6", "ex-local-6", "Example Local Six"),
        ],
      },
    }),
    lane("minimax", "api", "Example Gateway", {
      auth_kind: "api_key_with_base_url",
      model_source: "declared",
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        native_controls: [
          {
            control_id: "thinking",
            kind: "thought_level",
            display_name: "Thinking",
            options: [
              { option_id: "low", display_name: "Low" },
              { option_id: "auto", display_name: "Auto" },
              { option_id: "high", display_name: "High" },
            ],
          },
        ],
      },
    }),
    lane("moonshot", "api", "Example Moon", {
      background_requests: {
        text: "unsupported",
        image: "unsupported",
        pdf: "unsupported",
        options: [],
        accepts_images: false,
        accepts_pdfs: false,
      },
      catalog: {
        state: { status: "available", checked_at: CHECKED },
        models: [model("moon:1", "ex-moon-1", "Example Moon One")],
      },
    }),
    // An engine stated on a command-line lane is outside the contract.
    lane("ollama", "cli", "Example Broken", {
      health: { ...OK, engine: { engine: "ollama", state: "running" } },
    }),
  ],
};

const LISTS: LocalModelListStatus = {
  unreadable: false,
  models: [
    { lane: "llamacpp_api", model: "ex-local-3" },
    { lane: "llamacpp_api", model: "my-added-model" },
  ],
  reading: { lane: "llamacpp_api", model: "ex-local-1" },
  reading_source: "default",
  tasks: [
    {
      task_kind: "classification",
      lane: "llamacpp_api",
      model: "my-added-model",
      effort: null,
    },
    {
      task_kind: "extraction",
      lane: "claude_api",
      model: "ex-alpha-retired",
      effort: "high",
    },
  ],
  local_lanes: ["llamacpp_api"],
  revision: "revision-1",
};

const record = (
  id: string,
  provider: string,
  transport: "api" | "cli",
  mode: ProviderSettingsRecord["mode"],
  readsOffHost = true,
): ProviderSettingsRecord => ({
  id,
  provider,
  transport,
  display_name: id,
  reads_off_host: readsOffHost,
  auth_kind: "api_key",
  consumers: ["assistant"],
  mode,
  credential_saved: mode !== "unset",
  available: mode !== "disabled",
  source: mode === "unset" ? "none" : "profile",
  readiness: mode === "disabled" ? "disabled" : "not_verified",
  sign_out_available: false,
  revision: `r-${id}`,
});

const SETTINGS = {
  providers: [
    record("claude_api", "claude", "api", "key"),
    record("qwen_api", "qwen", "api", "unset"),
    record("deepseek_api", "deepseek", "api", "disabled"),
    record("llamacpp_api", "llamacpp", "api", "unset", false),
  ],
};

const offer = agentOffer(words, CATALOG, LISTS, SETTINGS);
const laneOf = (id: string) => offer.lanes.get(id)!;

test("each lane is offered once, in served order, under both of its ids", () => {
  expect([...offer.lanes.keys()]).toEqual([
    "claude_cli",
    "claude_api",
    "qwen_api",
    "deepseek_api",
    "llamacpp_api",
    "minimax_api",
    "moonshot_api",
  ]);
  expect(laneOf("claude_cli").wayId).toBe("claude/cli");
  expect(laneIdOf("claude", "cli")).toBe("claude_cli");
  expect(wayIdOf("claude", "cli")).toBe("claude/cli");
  expect(offer.observed).toBe(true);
  expect(offer.incompatible).toBe(false);
  expect(offer.stillReading).toBe(false);
});

test("a provider is listed once, named as its first served lane, its API first", () => {
  expect(offer.providers.map((provider) => provider.id)).toEqual([
    "claude",
    "qwen",
    "deepseek",
    "llamacpp",
    "minimax",
    "moonshot",
  ]);
  const alpha = offer.providers[0]!;
  expect(alpha.name).toBe("Example Alpha App");
  expect(alpha.ways.map((way) => way.id)).toEqual(["claude/api", "claude/cli"]);
  expect(alpha.lanes.map((held) => held.id)).toEqual([
    "claude_api",
    "claude_cli",
  ]);
  expect(alpha.selectable).toBe(true);
  expect(offer.providers[1]!.selectable).toBe(false);
});

test("a held lane says why, with the step there is", () => {
  expect(laneOf("claude_cli").runs).toBe(false);
  expect(laneOf("claude_cli").held).toEqual({
    words: "desktop.agent.lane_signed_out",
    step: "sign_in",
  });
  expect(laneOf("qwen_api").runs).toBe(false);
  expect(laneOf("qwen_api").held).toEqual({
    words: "desktop.agent.lane_not_configured",
  });
  expect(laneOf("claude_api").held).toBeNull();
});

test("off and not configured are separate facts: the settings' mode and the catalog's health", () => {
  // Turned off in the settings, yet the catalog still serves it as runnable.
  expect(laneOf("deepseek_api").on).toBe(false);
  expect(laneOf("deepseek_api").runs).toBe(true);
  // Not configured: on in the settings, and it cannot run.
  expect(laneOf("qwen_api").on).toBe(true);
  expect(laneOf("qwen_api").setting?.mode).toBe("unset");
  // The served record is carried as served, `available` included.
  expect(laneOf("deepseek_api").setting?.available).toBe(false);
  expect(laneOf("llamacpp_api").readsOffHost).toBe(false);
  // No record for a lane, and no settings read at all, say nothing.
  expect(laneOf("minimax_api").on).toBeNull();
  const unread = agentOffer(words, CATALOG, LISTS, null);
  expect(unread.lanes.get("claude_api")?.on).toBeNull();
  expect(unread.lanes.get("claude_api")?.setting).toBeNull();
});

test("a hosted lane offers every model with its efforts, and many stay many", () => {
  expect(offer.models["claude/api"]).toEqual([
    {
      id: "alpha:pro",
      name: "Example Alpha Pro",
      description: "The deep one.",
      efforts: [
        { id: "low", name: "desktop.agent.effort_low" },
        { id: "medium", name: "desktop.agent.effort_medium" },
        { id: "high", name: "desktop.agent.effort_high" },
      ],
      defaultEffort: "medium",
    },
    { id: "alpha:mini", name: "Example Alpha Mini", efforts: [] },
  ]);
  const way = offer.providers[0]!.ways[0]!;
  expect(way.defaultModelId).toBe("alpha:mini");
  const deep = offer.models["deepseek/api"]!;
  expect(deep).toHaveLength(40);
  expect(deep[0]?.id).toBe("deep:1");
  expect(deep[39]?.name).toBe("Example Deep 40");
});

test("a keyless local lane offers its list: in catalog order in the column, in list order for tasks", () => {
  const local = laneOf("llamacpp_api");
  expect(local.engine).toEqual({
    engine: "llamacpp",
    state: "running",
    reason: null,
    door: null,
  });
  expect(local.engineNotRunning).toBeNull();
  // The column: what the lane recommends for any capability, and what the
  // person added, as the catalog orders them.
  expect(offer.models["llamacpp/api"]?.map((each) => each.id)).toEqual([
    "local:1",
    "local:2",
    "local:3",
    "local:5",
  ]);
  expect(
    offer.models["llamacpp/api"]?.find((each) => each.id === "local:2")
      ?.installed,
  ).toBe(false);
  expect(local.modelsToDownload).toBe(true);
  expect(local.runs).toBe(true);
  // Tasks: the recommended models by capability, then what was added,
  // a name the catalog does not list included.
  expect(taskModelsOf(local).map((each) => [each.model, each.entryId])).toEqual(
    [
      ["ex-local-1", "local:1"],
      ["ex-local-2", "local:2"],
      ["ex-local-3", "local:3"],
      ["my-added-model", null],
    ],
  );
  expect(taskModelsOf(local)[3]?.installed).toBeNull();
});

test("a lane whose model is written offers its declared efforts and no list", () => {
  const gateway = laneOf("minimax_api");
  expect(gateway.modelWritten).toEqual({ efforts: ["low", "high"] });
  expect(offer.models["minimax/api"]).toEqual([]);
  expect(
    selectionRecord(offer, {
      providerId: "minimax",
      wayId: "minimax/api",
      modelId: "  my-gateway-model ",
      effort: "high",
    }),
  ).toEqual({
    provider: "minimax",
    transport: "api",
    model: "my-gateway-model",
    effort: "high",
  });
});

test("task lanes are the observed catalog lanes that take background text, in served order", () => {
  expect(offer.taskLanes.map((held) => held.id)).toEqual([
    "claude_cli",
    "claude_api",
    "qwen_api",
    "deepseek_api",
    "llamacpp_api",
  ]);
  // Efforts only where the lane takes an effort for a background request.
  const background = (lane: string, model: string) =>
    taskModelsOf(laneOf(lane)).find((held) => held.model === model)
      ?.backgroundEfforts;
  expect(background("claude_api", "ex-alpha-pro")).toEqual([
    "low",
    "medium",
    "high",
  ]);
  expect(background("llamacpp_api", "ex-local-1")).toEqual([]);
});

test("each served task kind carries its stored setting and whether a lane still offers it", () => {
  expect(
    offer.tasks.map((task) => [task.id, task.setting?.model, task.offered]),
  ).toEqual([
    ["classification", "my-added-model", true],
    ["extraction", "ex-alpha-retired", false],
  ]);
  expect(offer.reading).toEqual({
    lane: "llamacpp_api",
    model: "ex-local-1",
    source: "default",
  });
  expect(offer.listsRevision).toBe("revision-1");
  const unreadable = agentOffer(
    words,
    CATALOG,
    { ...LISTS, unreadable: true },
    SETTINGS,
  );
  expect(unreadable.listsUnreadable).toBe(true);
  expect(unreadable.tasks.map((task) => task.setting)).toEqual([null, null]);
  expect(unreadable.reading).toBeNull();
});

test("a task kind the window knows is said in its own words, not the agent's English", () => {
  // The catalogue serves "Classification" / "Sorts things."; the offer says
  // each known kind through its locale key instead.
  expect(
    offer.tasks.map((task) => [task.id, task.name, task.description]),
  ).toEqual([
    [
      "classification",
      "desktop.providers.task_kind_classification",
      "desktop.providers.task_kind_classification_description",
    ],
    [
      "extraction",
      "desktop.providers.task_kind_extraction",
      "desktop.providers.task_kind_extraction_description",
    ],
  ]);
});

test("a choice and a run convert through the offer both ways", () => {
  const chosen = {
    providerId: "claude",
    wayId: "claude/api",
    modelId: "alpha:pro",
    effort: "medium",
  };
  expect(selectionRecord(offer, chosen)).toEqual({
    provider: "claude",
    transport: "api",
    model: "ex-alpha-pro",
    effort: "medium",
  });
  expect(
    ranSelection(offer, {
      provider: "claude",
      transport: "api",
      model: "ex-alpha-pro",
      effort: "medium",
    }),
  ).toEqual(chosen);
  expect(
    readingSelection(offer, { lane: "llamacpp_api", model: "ex-local-1" }),
  ).toEqual({
    providerId: "llamacpp",
    wayId: "llamacpp/api",
    modelId: "local:1",
  });
  // A model the catalog says this computer lacks is not run.
  expect(
    selectionRecord(offer, {
      providerId: "llamacpp",
      wayId: "llamacpp/api",
      modelId: "local:2",
    }),
  ).toBeNull();
});

test("a catalog whose every lane is outside the contract is incompatible", () => {
  const broken = agentOffer(
    words,
    { ...CATALOG, providers: [CATALOG.providers![7]!] },
    null,
    null,
  );
  expect(broken.incompatible).toBe(true);
  expect(broken.providers).toEqual([]);
});

test("the declared catalogue lists every lane as not observed, none to choose", () => {
  const declared = agentOffer(words, FIXTURE_DECLARED_CATALOG, null, null);
  expect(declared.observed).toBe(false);
  expect(declared.taskLanes).toEqual([]);
  const lanes = [...declared.lanes.values()];
  expect(lanes.length).toBeGreaterThan(0);
  for (const held of lanes) {
    expect(held.runs).toBe(false);
    expect(held.held).toEqual({
      words: "desktop.agent.lane_not_observed",
      step: "retry",
    });
    expect(declared.models[held.wayId]).toEqual([]);
  }
  // A declared lane is never a run.
  const first = lanes[0]!;
  expect(
    selectionRecord(declared, {
      providerId: first.provider,
      wayId: first.wayId,
      modelId: "x",
    }),
  ).toBeNull();
});

test("the search matches every typed word anywhere in the words, in any order, case and padding aside", () => {
  const entry = ["Example Alpha", "App"];
  expect(offerMatches(entry, "  ALPHA app ")).toBe(true);
  expect(offerMatches(entry, "app")).toBe(true);
  expect(offerMatches(entry, "")).toBe(true);
  expect(offerMatches(entry, "   ")).toBe(true);
  expect(offerMatches(entry, "app alpha")).toBe(true);
  // Every word has to be held: one that is not keeps the entry out.
  expect(offerMatches(entry, "app beta")).toBe(false);
  expect(offerMatches([], "a")).toBe(false);
});

test("a lane turned off that the catalog does not serve is kept as its settings record", () => {
  const off: ProviderSettingsRecord = {
    ...SETTINGS.providers[0]!,
    id: "absent_cli",
    provider: "absent",
    transport: "cli",
    mode: "disabled",
  };
  const unset: ProviderSettingsRecord = {
    ...off,
    id: "unserved_api",
    mode: "unset",
  };
  const turned = agentOffer(words, CATALOG, LISTS, {
    providers: [...SETTINGS.providers, off, unset],
  });
  expect(turned.turnedOff.map((record) => record.id)).toEqual(["absent_cli"]);
  // A served lane turned off is an offered lane, not one of these.
  expect(agentOffer(words, CATALOG, LISTS, null).turnedOff).toEqual([]);
});

test("lanes group by provider in first-served order, the API before the app", () => {
  const lanes = [
    ["b", "cli"],
    ["a", "api"],
    ["b", "api"],
    ["a", "cli"],
    ["c", "cli"],
  ] as const;
  expect(
    groupedByProvider(
      lanes,
      ([provider]) => provider,
      ([, transport]) => transport,
    ),
  ).toEqual([
    [
      ["b", "api"],
      ["b", "cli"],
    ],
    [
      ["a", "api"],
      ["a", "cli"],
    ],
    [["c", "cli"]],
  ]);
});
