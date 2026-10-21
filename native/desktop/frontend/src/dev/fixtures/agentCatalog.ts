import type {
  AgentCatalogEntry,
  AgentEffort,
  AgentLaneCapability,
  AgentNativeControl,
  AgentProviderCatalog,
  AgentProviderLane,
} from "../../shell/agentSession";

// A provider catalog in the shape cadrumo-agent serves it, for the scenario
// host. Cadrumo keeps no list of the agent's providers: every provider, lane
// and model here is made up for this host, named "Example ..." or
// "Fixture ...", and a real desktop reads the catalog from the running agent.
// The lanes below cover each way a lane can differ (a catalog or a declared
// model list, an API or a program, held back or free). Each lane's health,
// so that every way a lane can be held back is shown, and the models of a
// lane that lists them are written here too.

/** What the made-up agent states of one lane. */
type DeclaredLane = Pick<
  AgentProviderLane,
  | "provider_id"
  | "transport"
  | "display_name"
  | "execution_mode"
  | "executable"
  | "model_source"
> & {
  catalog_revision: string | null;
  native_controls: NonNullable<AgentProviderLane["catalog"]["native_controls"]>;
};

const CAPABILITIES: AgentLaneCapability[] = [
  "tool_access",
  "writing",
  "web_retrieval",
  "image_reading",
  "pdf_reading",
];

const declare = (
  provider_id: string,
  transport: "api" | "cli",
  model_source: "catalog" | "declared",
  native_controls: DeclaredLane["native_controls"] = [],
): DeclaredLane => ({
  provider_id,
  transport,
  display_name: `Example ${provider_id[0]?.toUpperCase()}${provider_id.slice(1)}`,
  execution_mode: `example-${transport}`,
  executable: true,
  model_source,
  catalog_revision: model_source === "declared" ? "declared" : null,
  native_controls,
});

const DECLARED_LANES: readonly DeclaredLane[] = [
  declare("gamma", "cli", "catalog"),
  declare("alpha", "api", "catalog"),
  declare("alpha", "cli", "catalog"),
  declare("beta", "api", "catalog"),
  declare("beta", "cli", "catalog"),
  declare("gateway", "cli", "declared", [
    {
      control_id: "effort",
      kind: "thought_level",
      display_name: "Effort",
      options: [{ option_id: "max", display_name: "max", description: null }],
      default_option_id: null,
      description: null,
    },
  ]),
  declare("delta", "cli", "catalog"),
  declare("relay", "cli", "declared"),
  declare("epsilon", "cli", "declared"),
  declare("zeta", "cli", "declared"),
  declare("eta", "cli", "declared"),
  declare("theta", "cli", "declared"),
];

const CHECKED = "2026-10-13T08:00:00Z";

type Health = AgentProviderLane["health"];

const HEALTHY: Health = {
  configured: "available",
  transport: "available",
  authentication: "authenticated",
  catalog: "available",
  admission: "admitted",
  selectable: true,
  reasons: [],
  checked_at: CHECKED,
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
const effortControl = (efforts: AgentEffort[]): AgentNativeControl => ({
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
  efforts: AgentEffort[];
  default_effort?: AgentEffort;
};

/** The lane's models and the controls they take, as the catalog serves them. */
function modelsOf(models: FixtureModel[]) {
  const controls = new Map<string, AgentNativeControl>();
  const entries = models.map((model): AgentCatalogEntry => {
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
    };
  });
  return { entries, controls: [...controls.values()] };
}

type Fixture = {
  held?: keyof typeof HELD;
  models?: FixtureModel[];
  recommended?: string;
  /** Controls beyond efforts that the lane advertises; the column offers none. */
  extraControls?: AgentNativeControl[];
  /** The capabilities that have been proven on this made-up host; every
   * other one the agent states for the lane is not. */
  proven?: AgentLaneCapability[];
};

/** What this fixture makes up, by lane. A lane not listed has nothing made up
 * but a gateway's key, which is not set. */
const FIXTURES: Record<string, Fixture> = {
  "alpha/api": {
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
  },
  "alpha/cli": { held: "signedOut" },
  // The compatible API contract advertises no efforts or controls.
  "beta/api": {
    models: [
      { entry_id: "fixture-coder", display_name: "Fixture Coder", efforts: [] },
      { entry_id: "fixture-chat", display_name: "Fixture Chat", efforts: [] },
    ],
  },
  "beta/cli": {
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
  "gamma/cli": { held: "unreachable" },
  "delta/cli": { held: "notConfigured" },
  // The one gateway whose key is set: its models are written, not listed.
  "gateway/cli": {},
};

const KEYED = new Set(["gateway/cli"]);

function lane(declared: DeclaredLane): AgentProviderLane {
  const key = `${declared.provider_id}/${declared.transport}`;
  const fixture = FIXTURES[key] ?? {};
  const { entries, controls } = modelsOf(fixture.models ?? []);
  const declaredModels = declared.model_source === "declared";
  // A gateway with no key is held back; every other lane is as written above.
  const held =
    fixture.held ??
    (declaredModels && !KEYED.has(key) ? "notConfigured" : undefined);
  return {
    provider_id: declared.provider_id,
    transport: declared.transport,
    display_name: declared.display_name,
    execution_mode: declared.execution_mode,
    executable: declared.executable,
    model_source: declared.model_source,
    health: { ...HEALTHY, ...(held ? HELD[held] : {}) },
    catalog: {
      schema_version: 1,
      state: held
        ? { status: "unknown", checked_at: CHECKED }
        : {
            status: "available",
            checked_at: CHECKED,
            revision: declared.catalog_revision ?? "fixture-1",
          },
      recommended_entry_id: fixture.recommended ?? entries[0]?.entry_id ?? null,
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
  };
}

export const FIXTURE_CATALOG: AgentProviderCatalog = {
  api_version: "v1",
  providers: DECLARED_LANES.map(lane),
};
