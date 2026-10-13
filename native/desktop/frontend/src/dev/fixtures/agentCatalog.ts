import type {
  AgentCatalogEntry,
  AgentEffort,
  AgentLaneCapability,
  AgentNativeControl,
  AgentProviderCatalog,
  AgentProviderLane,
} from "../../shell/agentSession";
import { DECLARED_LANES, type DeclaredLane } from "./agentLanes.generated";

// A provider catalog in the shape cadrumo-agent serves it, for the scenario
// host. Which lanes there are, each one's provider, transport, name,
// execution mode and a gateway's declared efforts are generated from
// cadrumo-agent (agentLanes.generated.ts). What follows is made up, because
// cadrumo-agent only learns it on a host at run time: each lane's health, so
// that every way a lane can be held back is shown, and the models of a lane
// that lists them. Every such model is named "Fixture ..." and takes the
// efforts written here, not any real model's.

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
  "claude/api": {
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
  "claude/cli": { held: "signedOut" },
  // The compatible API contract advertises no efforts or controls.
  "codex/api": {
    models: [
      { entry_id: "fixture-coder", display_name: "Fixture Coder", efforts: [] },
      { entry_id: "fixture-chat", display_name: "Fixture Chat", efforts: [] },
    ],
  },
  "codex/cli": {
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
  "kimi/cli": { held: "notConfigured" },
  // The one gateway whose key is set: its models are written, not listed.
  "deepseek/cli": {},
};

const KEYED = new Set(["deepseek/cli"]);

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
    capability_proofs: declared.capability_proofs.map((proof) => ({
      ...proof,
      state: fixture.proven?.includes(proof.capability) ? "proven" : "unproven",
    })),
  };
}

export const FIXTURE_CATALOG: AgentProviderCatalog = {
  api_version: "v1",
  providers: DECLARED_LANES.map(lane),
};
