import type {
  AuthKind,
  BackgroundOption,
  BackgroundRequestSupportResponse,
  DeclaredLicence,
  DeclaredModel,
  DeclaredTaskKind,
  Effort,
  EffortCapability,
  EngineHealthResponse,
  LaneCapability,
  LocalEngine,
  Provider,
  ProviderNativeControlResponse,
  ProviderTransport,
  ServedCatalogModel,
  ServedDeclaredProviderCatalog,
  ServedProviderCatalog,
  ServedProviderLane,
} from "../../shell/agentCatalogContract";
import { fixtureInstant } from "@/dev/fixtureDates";

// A provider catalog in the shape cadrumo-agent serves it, for the scenario
// host. Cadrumo keeps no list of the agent's providers: each lane takes a
// provider id from the agent's closed set only because the schema demands
// one, and every name, lane and model here is made up for this host, named
// "Example ..." or "Fixture ...". A real desktop reads the catalog from the
// running agent.
// The lanes below cover each way a lane can differ (a catalog or a declared
// model list, an API or a program, held back or free). Each lane's health,
// so that every way a lane can be held back is shown, and the models of a
// lane that lists them are written here too.

/** What the made-up agent states of one lane. */
type DeclaredLane = Pick<
  ServedProviderLane,
  | "provider_id"
  | "transport"
  | "display_name"
  | "auth_kind"
  | "execution_mode"
  | "executable"
  | "model_source"
> & {
  catalog_revision: string | null;
  native_controls: ProviderNativeControlResponse[];
};

const CAPABILITIES: LaneCapability[] = [
  "tool_access",
  "writing",
  "web_retrieval",
  "image_reading",
  "pdf_reading",
];

/** What each made-up lane is authenticated with, by `<provider>/<transport>`;
 * a lane not named here takes a key. */
const AUTH_KINDS: Record<string, AuthKind> = {
  "antigravity/cli": "provider_sign_in_only",
  "qwen/cli": "provider_sign_in_only",
  "zhipu/cli": "api_key_with_base_url",
  "minimax/cli": "api_key_with_base_url",
  "zai/api": "none",
  "ollama/api": "none",
  "llamacpp/api": "none",
};

/** What the made-up agent states `provider`'s `transport` lane is
 * authenticated with. */
export const fixtureAuthKind = (
  provider: string,
  transport: ProviderTransport,
): AuthKind => AUTH_KINDS[`${provider}/${transport}`] ?? "api_key";

/** A made-up lane of `provider_id`, shown by the made-up `name`. */
const declare = (
  provider_id: Provider,
  name: string,
  transport: ProviderTransport,
  model_source: "catalog" | "declared",
  native_controls: DeclaredLane["native_controls"] = [],
): DeclaredLane => ({
  provider_id,
  transport,
  auth_kind: fixtureAuthKind(provider_id, transport),
  display_name: `Example ${name}`,
  execution_mode: `example-${transport}`,
  executable: true,
  model_source,
  catalog_revision: model_source === "declared" ? "declared" : null,
  native_controls,
});

const DECLARED_LANES: readonly DeclaredLane[] = [
  declare("antigravity", "Gamma", "cli", "catalog"),
  declare("kimi", "Alpha", "api", "catalog"),
  declare("kimi", "Alpha", "cli", "catalog"),
  declare("qwen", "Beta", "api", "catalog"),
  declare("qwen", "Beta", "cli", "catalog"),
  declare("zhipu", "Gateway", "cli", "declared", [
    {
      control_id: "effort",
      kind: "thought_level",
      display_name: "Effort",
      options: [{ option_id: "max", display_name: "max", description: null }],
      default_option_id: null,
      description: null,
    },
  ]),
  declare("deepseek", "Delta", "cli", "catalog"),
  declare("minimax", "Relay", "cli", "declared"),
  declare("moonshot", "Zeta", "cli", "declared"),
  // A lane run on this computer, with no key: its models state what they are.
  declare("zai", "Local", "api", "catalog"),
  // The two engines' keyless lanes: the engine setting shows one of them.
  declare("ollama", "Ollama", "api", "catalog"),
  declare("llamacpp", "Llamacpp", "api", "catalog"),
];

const CHECKED = fixtureInstant(10, 13, "08:00:00Z");

type Health = ServedProviderLane["health"];

const HEALTHY: Health = {
  configured: "available",
  transport: "available",
  authentication: "authenticated",
  catalog: "available",
  admission: "admitted",
  selectable: true,
  reasons: [],
  checked_at: CHECKED,
  // Only the local engines' API lanes state one, below.
  engine: null,
};

/** A lane held back, with the axis that holds it. */
const HELD: Record<string, Partial<Health>> = {
  notConfigured: {
    configured: "unavailable",
    catalog: "unknown",
    admission: "unknown",
    selectable: false,
    reasons: ["credential_missing"],
  },
  signedOut: {
    authentication: "unauthenticated",
    catalog: "unknown",
    selectable: false,
    reasons: ["sign_in_required"],
  },
  unreachable: {
    transport: "unavailable",
    catalog: "unknown",
    admission: "unknown",
    selectable: false,
    reasons: ["cli_not_installed"],
  },
};

/** The effort control a lane advertises for models that take `efforts`; the
 * catalog serves a model's efforts through it. */
const effortControl = (efforts: Effort[]): ProviderNativeControlResponse => ({
  control_id: `effort:${efforts.join("-")}`,
  kind: "thought_level",
  display_name: "Effort",
  options: efforts.map((effort) => ({
    option_id: effort,
    display_name: effort,
  })),
  default_option_id: null,
});

type FixtureModel = {
  entry_id: string;
  display_name: string;
  description?: string;
  efforts: Effort[];
  default_effort?: Effort;
  vision?: boolean | null;
  size_bytes?: number | null;
  licence?: DeclaredLicence | null;
  /** False for a model this computer does not hold yet. */
  installed?: boolean;
};

/** The lane's models and the controls they take, as the catalog serves them:
 * whether this computer holds a model only on a lane whose models are
 * downloaded to it. */
function modelsOf(models: FixtureModel[], downloaded: boolean) {
  const controls = new Map<string, ProviderNativeControlResponse>();
  const entries = models.map((model): ServedCatalogModel => {
    const control = model.efforts.length
      ? effortControl(model.efforts)
      : undefined;
    if (control) controls.set(control.control_id, control);
    return {
      entry_id: model.entry_id,
      model: model.entry_id,
      display_name: model.display_name,
      ...(model.description ? { description: model.description } : {}),
      native_control_ids: control ? [control.control_id] : [],
      efforts: model.efforts,
      default_effort: model.default_effort ?? null,
      vision: model.vision ?? null,
      size_bytes: model.size_bytes ?? null,
      context_length: null,
      licence: model.licence ?? null,
      llamacpp_default_context: null,
      ...(downloaded ? { installed: model.installed ?? true } : {}),
    };
  });
  return { entries, controls: [...controls.values()] };
}

type Fixture = {
  held?: keyof typeof HELD;
  models?: FixtureModel[];
  recommended?: string;
  /** What the lane recommends per capability, by model. */
  recommendedFor?: Partial<Record<"vision" | "text", string>>;
  /** The run options a background request on the lane takes. */
  background?: BackgroundOption[];
  /** Controls beyond efforts that the lane advertises; the column offers none. */
  extraControls?: ProviderNativeControlResponse[];
  /** The capabilities that have been proven on this made-up host; every
   * other one the agent states for the lane is not. */
  proven?: LaneCapability[];
};

/** What this fixture makes up for one engine's lane. */
function engineLane(engine: string, name: string): Fixture {
  return {
    models: [
      {
        entry_id: `synthetic-${engine}:1`,
        display_name: `Synthetic ${name} 1`,
        efforts: [],
        vision: false,
      },
      {
        entry_id: `synthetic-${engine}-vision:1`,
        display_name: `Synthetic ${name} Vision 1`,
        efforts: [],
        vision: true,
        // Recommended, but not downloaded yet.
        installed: false,
        size_bytes: 3_435_973_837,
        licence: {
          spdx: null,
          name: "Example community licence",
          digest: `sha256:${"b".repeat(64)}`,
        },
      },
    ],
    recommendedFor: {
      vision: `synthetic-${engine}-vision:1`,
      text: `synthetic-${engine}:1`,
    },
  };
}

/** What this fixture makes up, by lane. A lane not listed has nothing made up
 * but a gateway's key, which is not set. */
const FIXTURES: Record<string, Fixture> = {
  "kimi/api": {
    models: [
      {
        entry_id: "fixture-deep",
        display_name: "Fixture Deep",
        description: "A made-up model that takes every effort up to max.",
        efforts: ["low", "medium", "high", "xhigh", "max"],
      },
      {
        entry_id: "fixture-quick",
        display_name: "Fixture Quick",
        efforts: ["low", "medium"],
        default_effort: "medium",
      },
      { entry_id: "fixture-plain", display_name: "Fixture Plain", efforts: [] },
    ],
    proven: ["tool_access", "web_retrieval", "pdf_reading"],
    background: ["effort"],
  },
  "kimi/cli": { held: "signedOut" },
  // The compatible API contract advertises no efforts or controls.
  "qwen/api": {
    models: [
      { entry_id: "fixture-coder", display_name: "Fixture Coder", efforts: [] },
      { entry_id: "fixture-chat", display_name: "Fixture Chat", efforts: [] },
    ],
  },
  "qwen/cli": {
    recommended: "fixture-ultra",
    models: [
      {
        entry_id: "fixture-tiered",
        display_name: "Fixture Tiered",
        efforts: ["low", "medium", "high"],
        default_effort: "medium",
      },
      {
        entry_id: "fixture-ultra",
        display_name: "Fixture Ultra",
        efforts: ["high", "ultra"],
        default_effort: "high",
      },
    ],
    extraControls: [
      {
        control_id: "service_tier",
        kind: "service_tier",
        display_name: "Fixture service tier",
        options: [
          { option_id: "standard", display_name: "Fixture standard" },
          { option_id: "priority", display_name: "Fixture priority" },
        ],
        default_option_id: "standard",
      },
    ],
    proven: ["tool_access"],
  },
  "antigravity/cli": { held: "unreachable" },
  "deepseek/cli": { held: "notConfigured" },
  // The one gateway whose key is set: its models are written, not listed.
  "zhipu/cli": {},
  "zai/api": {
    models: [
      {
        entry_id: "synthetic-text:1",
        display_name: "Synthetic Text 1",
        efforts: [],
        vision: false,
        size_bytes: 2_684_354_560,
        licence: {
          spdx: "Apache-2.0",
          name: "Example Apache-style licence",
          digest: `sha256:${"a".repeat(64)}`,
        },
      },
      {
        entry_id: "synthetic-vision:1",
        display_name: "Synthetic Vision 1",
        efforts: [],
        vision: true,
        // Recommended, but not downloaded yet.
        installed: false,
        size_bytes: 3_435_973_837,
        licence: {
          spdx: null,
          name: "Example community licence",
          digest: `sha256:${"b".repeat(64)}`,
        },
      },
      {
        entry_id: "synthetic-plain:1",
        display_name: "Synthetic Plain 1",
        efforts: [],
      },
    ],
    recommendedFor: { vision: "synthetic-vision:1", text: "synthetic-text:1" },
  },
  // Each engine's lane is made as the generic local lane is: a text model this
  // computer holds and a recommended vision model it does not hold yet, so
  // the two engines are told apart by their names alone.
  "ollama/api": engineLane("ollama", "Ollama"),
  "llamacpp/api": engineLane("llamacpp", "Llamacpp"),
};

const KEYED = new Set(["zhipu/cli"]);

/** The lanes of the local engines, which state whether the engine runs. */
const ENGINE_LANES = new Set(["ollama/api", "llamacpp/api"]);
/** The lanes whose models are downloaded to this computer: the generic local
 * lane and each engine's. */
const DOWNLOAD_LANES = new Set(["zai/api", ...ENGINE_LANES]);

const runningEngine = (engine: LocalEngine): EngineHealthResponse => ({
  engine,
  state: "running",
  reason: null,
  door: null,
});

const isEngine = (provider: Provider): provider is LocalEngine =>
  provider === "llamacpp" || provider === "ollama";

/** What a background request on a made-up lane may carry: text alone, which
 * no live request has proven on this made-up host. */
const BACKGROUND: BackgroundRequestSupportResponse = {
  text: "unproven",
  image: "unsupported",
  pdf: "unsupported",
  options: [],
  accepts_images: false,
  accepts_pdfs: false,
};

function lane(declared: DeclaredLane): ServedProviderLane {
  const key = `${declared.provider_id}/${declared.transport}`;
  const fixture = FIXTURES[key] ?? {};
  const downloaded = DOWNLOAD_LANES.has(key);
  const { entries, controls } = modelsOf(fixture.models ?? [], downloaded);
  const declaredModels = declared.model_source === "declared";
  // A gateway with no key is held back; every other lane is as written above.
  const held =
    fixture.held ??
    (declaredModels && !KEYED.has(key) ? "notConfigured" : undefined);
  return {
    provider_id: declared.provider_id,
    transport: declared.transport,
    display_name: declared.display_name,
    auth_kind: declared.auth_kind,
    execution_mode: declared.execution_mode,
    executable: declared.executable,
    model_source: declared.model_source,
    model_download: downloaded ? "required" : "none",
    health: {
      ...HEALTHY,
      ...(held ? HELD[held] : {}),
      ...(ENGINE_LANES.has(key) && isEngine(declared.provider_id)
        ? { engine: runningEngine(declared.provider_id) }
        : {}),
    },
    catalog: {
      schema_version: 2,
      state: held
        ? { status: "unknown", checked_at: CHECKED }
        : {
            status: "available",
            checked_at: CHECKED,
            revision: declared.catalog_revision ?? "fixture-1",
          },
      recommended_entry_id: fixture.recommended ?? entries[0]?.entry_id ?? null,
      ...(fixture.recommendedFor
        ? { recommended: fixture.recommendedFor }
        : {}),
      models: entries,
      native_controls: [
        ...declared.native_controls,
        ...controls,
        ...(fixture.extraControls ?? []),
      ],
    },
    capability_proofs: CAPABILITIES.map((capability) => ({
      capability,
      entry:
        capability === "tool_access" || capability === "writing"
          ? "example"
          : null,
      state: fixture.proven?.includes(capability) ? "proven" : "unproven",
    })),
    background_requests: fixture.background
      ? { ...BACKGROUND, options: fixture.background }
      : BACKGROUND,
  };
}

/** The kinds of background task both catalogs serve, with made-up names
 * and sentences: the frontend keeps no list of its own. */
const TASK_KINDS: DeclaredTaskKind[] = [
  {
    id: "classification",
    display_name: "Made-up classification",
    description: "A made-up sentence about labelling a record.",
  },
  {
    id: "extraction",
    display_name: "Made-up extraction",
    description: "A made-up sentence about reading fields out of a document.",
  },
];

export const FIXTURE_CATALOG: ServedProviderCatalog = {
  api_version: "v1",
  providers: DECLARED_LANES.map(lane),
  task_kinds: TASK_KINDS,
};

/** How the service answers the catalog: served, busy starting the agent
 * until the scenario publishes the agent's status, busy while the agent
 * starts and for a moment after the scenario publishes it ready, or starting
 * with only the agent's declared catalog until the scenario publishes it
 * ready, or served with the local lane alone, as on a computer where no
 * other provider is set up, or with the two local engines' lanes alone, or
 * with the local lane and one hosted provider's lane that is signed out, or
 * refused, as `fixtureCatalogRefusal` says. */
export type FixtureCatalog =
  | "served"
  | "busy"
  | "busy-past-ready"
  | "declared"
  | "unsupported"
  | "local-only"
  | "engines-only"
  | "hosted-signed-out"
  | "unavailable"
  | "unavailable-unreferenced";

/** The made-up reference of the service's log line a refused catalog
 * carries, in the hex and hyphen form the service mints. */
export const FIXTURE_CATALOG_LOG_REF = "0f1e2d3c-4b5a-4968-8776-655443322110";

/** The refusal the host hands the window for a catalog the scenario has the
 * service refuse as unavailable, with its log line's reference or without
 * one, as the host relays it; null for a catalog the service answers. */
export function fixtureCatalogRefusal(catalog: string): Error | null {
  if (catalog !== "unavailable" && catalog !== "unavailable-unreferenced")
    return null;
  return Object.assign(new Error("agent_catalog_unavailable"), {
    code: "agent_catalog_unavailable",
    ...(catalog === "unavailable" ? { log_ref: FIXTURE_CATALOG_LOG_REF } : {}),
  });
}

/** What a scenario makes the made-up service say of each local engine, by
 * engine token: the answer exactly as written, so a scenario can also state
 * one that pairs its fields outside the contract. Null states none was
 * measured. */
export type FixtureEngineHealth = Partial<
  Record<LocalEngine, EngineHealthResponse | null>
>;

/** `catalog` with each stated engine's health as written. An engine stated
 * as not running is held back as the service holds back a lane it cannot
 * reach. */
export function withEngineHealth(
  catalog: ServedProviderCatalog,
  health: FixtureEngineHealth,
): ServedProviderCatalog {
  return {
    ...catalog,
    providers: (catalog.providers ?? []).map((served) => {
      const key = `${served.provider_id}/${served.transport}`;
      if (
        !ENGINE_LANES.has(key) ||
        !isEngine(served.provider_id) ||
        !(served.provider_id in health)
      )
        return served;
      const stated = health[served.provider_id] ?? null;
      const down = stated?.state === "not_running";
      return {
        ...served,
        health: {
          ...served.health,
          engine: stated,
          ...(down
            ? {
                transport: "unavailable" as const,
                selectable: false,
                reasons: ["engine_not_running"],
              }
            : {}),
        },
      };
    }),
  };
}

/** The engine health a scenario's address states: a JSON object keyed by
 * engine token. */
export function parseFixtureEngineHealth(
  text: string | null,
): FixtureEngineHealth | undefined {
  if (text === null) return undefined;
  try {
    const parsed: unknown = JSON.parse(text);
    return typeof parsed === "object" &&
      parsed !== null &&
      !Array.isArray(parsed)
      ? (parsed as FixtureEngineHealth)
      : undefined;
  } catch {
    return undefined;
  }
}

/** Which models of the made-up catalog the made-up computer holds: the
 * setup fixture marks a model it downloaded or removed, and the made-up
 * agent's served catalog reports it so, as cadrumo-agent's catalog reports
 * what the local AI's program holds. A model never marked stays as written. */
export type FixtureModelPresence = {
  /** `model` is now on this computer, or no longer. */
  mark(model: string, installed: boolean): void;
  /** Every model is now on this computer, or none is; a model marked after
   * this is as marked. */
  markAll(installed: boolean): void;
  /** `catalog` with each marked model's `installed` as marked. */
  report(catalog: ServedProviderCatalog): ServedProviderCatalog;
};

export function fixtureModelPresence(): FixtureModelPresence {
  const marked = new Map<string, boolean>();
  let all: boolean | undefined;
  return {
    mark(model, installed) {
      marked.set(model, installed);
    },
    markAll(installed) {
      marked.clear();
      all = installed;
    },
    report: (catalog) => ({
      ...catalog,
      providers: (catalog.providers ?? []).map((served) => {
        const models = served.catalog.models;
        if (!models) return served;
        return {
          ...served,
          catalog: {
            ...served.catalog,
            models: models.map((entry) => {
              const installed = marked.get(entry.model) ?? all;
              return installed === undefined ? entry : { ...entry, installed };
            }),
          },
        };
      }),
    }),
  };
}

/** What a served model's efforts say of its effort control, as the declared
 * catalog states it: the levels it takes, or no control. */
const effortOf = (entry: ServedCatalogModel): EffortCapability => {
  const levels = entry.efforts ?? [];
  return levels.length > 0
    ? {
        reasoning: "supported",
        control: "levels",
        levels,
        default: entry.default_effort ?? null,
      }
    : { reasoning: "unsupported", control: "none", levels: [], default: null };
};

const declaredModel = (entry: ServedCatalogModel): DeclaredModel => ({
  id: entry.model,
  display_name: entry.display_name,
  effort: effortOf(entry),
  vision: entry.vision,
  size_bytes: entry.size_bytes,
  context_length: entry.context_length,
  licence: entry.licence,
  artefacts: null,
});

/** The same made-up lanes as cadrumo-agent's declared catalog states them,
 * in the envelope the service answers with while no agent is ready. */
export const FIXTURE_DECLARED_CATALOG: ServedDeclaredProviderCatalog = {
  kind: "declared",
  catalog: {
    schema_version: 8,
    providers: (FIXTURE_CATALOG.providers ?? []).map((served) => {
      const id = `${served.provider_id}_${served.transport}`;
      const models = (served.catalog.models ?? []).map(declaredModel);
      const keyed =
        served.auth_kind === "api_key" ||
        served.auth_kind === "api_key_with_base_url";
      return {
        id,
        provider: served.provider_id,
        transport: served.transport,
        display_name: served.display_name,
        description: `A made-up lane of ${served.display_name}.`,
        auth_kind: served.auth_kind,
        default_base_url: null,
        agent_credential_id: keyed ? `fixture-${id}` : null,
        reads_off_host: served.model_download === "none",
        cli_programs:
          served.transport === "cli" ? [`example-${served.provider_id}`] : [],
        icon: null,
        platform: {
          docs_url: null,
          models_url: null,
          status: { kind: "none", page_url: null, api_url: null },
        },
        default_model: models[0]?.id ?? null,
        models,
        recommended: served.catalog.recommended ?? {},
        background: { runnable: false, inputs: [], options: [] },
        unread: [],
        model_download: served.model_download,
      };
    }),
    icon_attribution: {
      title: "Example icon set",
      url: "https://icons.example/",
      pin: "0.0.0",
      licence: "Example licence",
      notice: "Made-up artwork notice for the scenario host.",
      trademarks: "Every mark shown is its holder's.",
    },
    task_kinds: TASK_KINDS,
  },
};

/** Whether the service serves a lane while the engine record selects
 * `selected`: the keyless lane of a local engine it does not select is not
 * served, in the catalog or in the provider settings. */
export const servedUnderEngine = (
  provider: string,
  transport: string,
  selected: string,
): boolean =>
  !(ENGINE_LANES.has(`${provider}/${transport}`) && provider !== selected);

/** The fixture catalog and the declared catalog as the service serves them
 * while the engine record selects `selected`: the keyless lane of a local
 * engine it does not select is served in neither. */
export function catalogsUnderEngine(selected: string): {
  served: ServedProviderCatalog;
  declared: ServedDeclaredProviderCatalog;
} {
  const held = (provider: string, transport: string) =>
    !servedUnderEngine(provider, transport, selected);
  return {
    served: {
      ...FIXTURE_CATALOG,
      providers: (FIXTURE_CATALOG.providers ?? []).filter(
        (lane) => !held(lane.provider_id, lane.transport),
      ),
    },
    declared: {
      ...FIXTURE_DECLARED_CATALOG,
      catalog: {
        ...FIXTURE_DECLARED_CATALOG.catalog,
        providers: FIXTURE_DECLARED_CATALOG.catalog.providers.filter(
          (lane) => !held(lane.provider, lane.transport),
        ),
      },
    },
  };
}
