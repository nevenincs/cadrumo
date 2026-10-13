import type {
  AgentSelection,
  Choice,
  ModelControl,
  ModelOption,
  ProviderOption,
} from "@/components/agent/types";
import type {
  AgentCatalogEntry,
  AgentEffort,
  AgentLaneCapability,
  AgentProviderCatalog,
  AgentProviderLane,
  AgentSelectionRecord,
} from "./agentSession";
import type { Translate } from "./strings";

// The agent column's choices, deduced from cadrumo-agent's provider catalog
// alone: every lane it lists is a provider, each lane's models are its own,
// and each model's efforts, settings and proven capabilities are that
// model's. The column adds only the words for the catalog's closed values;
// it names no provider, model, effort or capability of its own.

/** A lane's identity: one provider run one way. */
const laneId = (lane: AgentProviderLane) =>
  `${lane.provider_id} ${lane.execution_mode}`;

export function effortWords(t: Translate, effort: AgentEffort): string {
  switch (effort) {
    case "low":
      return t("desktop.agent.effort_low");
    case "medium":
      return t("desktop.agent.effort_medium");
    case "high":
      return t("desktop.agent.effort_high");
    case "xhigh":
      return t("desktop.agent.effort_xhigh");
    case "max":
      return t("desktop.agent.effort_max");
    case "ultra":
      return t("desktop.agent.effort_ultra");
  }
}

function capabilityWords(t: Translate, capability: AgentLaneCapability) {
  switch (capability) {
    case "tool_access":
      return t("desktop.agent.can_use_tools");
    case "writing":
      return t("desktop.agent.can_write");
    case "web_retrieval":
      return t("desktop.agent.can_search_web");
    case "image_reading":
      return t("desktop.agent.can_read_images");
    case "pdf_reading":
      return t("desktop.agent.can_read_pdfs");
  }
}

/** Why a lane cannot be chosen, from the first of its health axes that
 * says so. */
function laneHeldBy(t: Translate, lane: AgentProviderLane): string {
  const { health } = lane;
  if (health.configured === "unavailable")
    return t("desktop.agent.lane_not_configured");
  if (health.authentication === "unauthenticated")
    return t("desktop.agent.lane_signed_out");
  if (health.transport === "unavailable" || !lane.executable)
    return t("desktop.agent.lane_unreachable");
  if (health.admission === "not_admitted")
    return t("desktop.agent.lane_not_admitted");
  if (health.catalog === "unavailable")
    return t("desktop.agent.lane_no_catalog");
  return t("desktop.agent.unavailable");
}

const selectable = (lane: AgentProviderLane) =>
  lane.health.selectable && lane.executable;

function modelOption(
  t: Translate,
  lane: AgentProviderLane,
  entry: AgentCatalogEntry,
): ModelOption {
  const controls = (entry.native_control_ids ?? []).flatMap(
    (controlId): ModelControl[] => {
      const control = lane.catalog.native_controls?.find(
        (held) => held.control_id === controlId,
      );
      if (!control?.options?.length) return [];
      return [
        {
          id: control.control_id,
          name: control.display_name,
          ...(control.description ? { description: control.description } : {}),
          options: control.options.map((option): Choice => ({
            id: option.option_id,
            name: option.display_name,
            ...(option.description ? { description: option.description } : {}),
          })),
          ...(control.default_option_id
            ? { defaultOptionId: control.default_option_id }
            : {}),
        },
      ];
    },
  );
  // Proven for this model, or for the whole lane.
  const capabilities = (lane.capability_proofs ?? [])
    .filter(
      (proof) =>
        proof.state === "proven" &&
        (proof.entry == null || proof.entry === entry.entry_id),
    )
    .map((proof) => capabilityWords(t, proof.capability));
  return {
    id: entry.entry_id,
    name: entry.display_name,
    ...(entry.description ? { description: entry.description } : {}),
    efforts: (entry.efforts ?? []).map((effort) => ({
      id: effort,
      name: effortWords(t, effort),
    })),
    ...(entry.default_effort ? { defaultEffort: entry.default_effort } : {}),
    ...(controls.length > 0 ? { controls } : {}),
    ...(capabilities.length > 0
      ? { capabilities: [...new Set(capabilities)] }
      : {}),
  };
}

export type CatalogChoices = {
  providers: ProviderOption[];
  /** Each lane's models, by provider option id. */
  models: Record<string, ModelOption[]>;
};

/** The providers and models the column offers, as the catalog has them. */
export function catalogChoices(
  t: Translate,
  catalog: AgentProviderCatalog,
): CatalogChoices {
  const lanes = catalog.providers ?? [];
  // A provider run more than one way names the way.
  const named = (lane: AgentProviderLane) =>
    lanes.filter((held) => held.provider_id === lane.provider_id).length > 1
      ? `${lane.display_name} · ${lane.execution_mode}`
      : lane.display_name;
  const providers = lanes.map((lane): ProviderOption => ({
    id: laneId(lane),
    name: named(lane),
    selectable: selectable(lane),
    ...(selectable(lane) ? {} : { unavailableReason: laneHeldBy(t, lane) }),
    ...(lane.catalog.recommended_entry_id
      ? { defaultModelId: lane.catalog.recommended_entry_id }
      : {}),
  }));
  const models = Object.fromEntries(
    lanes.map((lane) => [
      laneId(lane),
      (lane.catalog.models ?? []).map((entry) => modelOption(t, lane, entry)),
    ]),
  );
  return { providers, models };
}

/** The settings a model starts with: each one's default, else its first. */
export function startingControls(
  model: ModelOption,
): Record<string, string> | undefined {
  if (!model.controls?.length) return undefined;
  return Object.fromEntries(
    model.controls.map((control) => [
      control.id,
      control.defaultOptionId ?? control.options[0]?.id ?? "",
    ]),
  );
}

/** The model a provider starts with: the catalog's recommendation where it
 * lists it, else its first. */
export function startingModel(
  provider: ProviderOption,
  models: readonly ModelOption[],
): ModelOption | undefined {
  return (
    models.find((model) => model.id === provider.defaultModelId) ?? models[0]
  );
}

/** `selection` where the catalog still offers it, else where the first lane
 * that can be chosen starts; null when none can. */
export function offeredSelection(
  choices: CatalogChoices,
  selection: AgentSelection | null,
): AgentSelection | null {
  if (selection) {
    const provider = choices.providers.find(
      (held) => held.id === selection.providerId && held.selectable,
    );
    const model = choices.models[selection.providerId]?.find(
      (held) => held.id === selection.modelId,
    );
    if (
      provider &&
      model &&
      (selection.effort === undefined ||
        model.efforts.some((effort) => effort.id === selection.effort))
    )
      return selection;
  }
  for (const provider of choices.providers) {
    if (!provider.selectable) continue;
    const model = startingModel(provider, choices.models[provider.id] ?? []);
    if (!model) continue;
    const controls = startingControls(model);
    return {
      providerId: provider.id,
      modelId: model.id,
      ...(model.defaultEffort ? { effort: model.defaultEffort } : {}),
      ...(controls ? { controls } : {}),
    };
  }
  return null;
}

/** What a send runs with, as the catalog names it. */
export function selectionRecord(
  catalog: AgentProviderCatalog,
  selection: AgentSelection,
): AgentSelectionRecord | null {
  const lane = catalog.providers?.find(
    (held) => laneId(held) === selection.providerId,
  );
  const entry = lane?.catalog.models?.find(
    (held) => held.entry_id === selection.modelId,
  );
  if (!lane || !entry) return null;
  const effort = entry.efforts?.find((held) => held === selection.effort);
  const controls = Object.entries(selection.controls ?? {}).map(
    ([control_id, option_id]) => ({ control_id, option_id }),
  );
  return {
    provider: lane.provider_id,
    execution_mode: lane.execution_mode,
    entry_id: entry.entry_id,
    model: entry.model,
    ...(effort ? { effort } : {}),
    ...(controls.length > 0 ? { controls } : {}),
  };
}
