import type {
  AgentSelection,
  Choice,
  ModelOption,
  ProviderOption,
  ProviderWay,
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
// alone. The column adds only the words for the catalog's closed values; it
// names no provider, model, effort or capability of its own, and this is the
// one place any of it is worked out.
//
// A provider is the catalog's `provider_id` and a way into it is its
// `transport`, so the lanes of one provider are grouped under it, and the
// list the person chooses from has a row for each lane, named as the lane is
// (`display_name`). The person is never shown the transport. Both are served
// explicitly by cadrumo-agent's ProviderCatalogResponse
// (api/schemas/provider_catalog.py), from the lane's own definitions. A
// service that predates this serves the lanes by their private ids with no
// transport; those cannot be told apart without a table of cadrumo-agent's
// lane ids, which Cadrumo does not keep, so such a lane is not offered and the
// column says the service is incompatible.
//
// A lane is a way into one model list, and the pair (provider, transport) is
// its identity, as ExecutionLane.selection_key has it. `execution_mode` says
// how the lane runs and is not part of that identity.
//
// A run takes a provider, a transport, a model and an effort, and nothing
// else (AgentSpec, agent/spec.py): the execution mode and the catalog entry
// are the service's to resolve, and a model's native controls are not part of
// it, so none is offered. A capability proof names a tool server, not a model,
// so what a lane has been proven to do is shown for the way, not for a model.

/** The identity of a lane: one provider, reached one way. */
const wayId = (lane: AgentProviderLane) =>
  `${lane.provider_id}/${lane.transport}`;

const understood = (lane: AgentProviderLane) =>
  lane.provider_id !== "" &&
  (lane.transport === "api" || lane.transport === "cli");

/** The words for each effort cadrumo-agent names (agent/spec.py `Effort`). */
const EFFORT_WORDS = {
  low: "desktop.agent.effort_low",
  medium: "desktop.agent.effort_medium",
  high: "desktop.agent.effort_high",
  xhigh: "desktop.agent.effort_xhigh",
  max: "desktop.agent.effort_max",
  ultra: "desktop.agent.effort_ultra",
} as const satisfies Record<AgentEffort, string>;

const isEffort = (value: string): value is AgentEffort =>
  Object.hasOwn(EFFORT_WORDS, value);

export function effortWords(t: Translate, effort: AgentEffort): string {
  return t(EFFORT_WORDS[effort]);
}

const effortChoice = (t: Translate, effort: AgentEffort): Choice => ({
  id: effort,
  name: effortWords(t, effort),
});

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

/** What the lane has been proven to do on this host. A proof is the lane's,
 * not a model's: `entry` on one names a tool server, not a model, so the
 * proofs are shown for the way into a provider and never for a model. */
function provenCapabilities(t: Translate, lane: AgentProviderLane): string[] {
  const words = (lane.capability_proofs ?? [])
    .filter((proof) => proof.state === "proven")
    .map((proof) => capabilityWords(t, proof.capability));
  return [...new Set(words)];
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
  if (health.catalog === "unavailable" || health.catalog === "unknown")
    return t("desktop.agent.lane_no_catalog");
  return t("desktop.agent.unavailable");
}

const writesModel = (lane: AgentProviderLane) =>
  lane.model_source === "declared";

/** The efforts a lane that lists no models accepts with any model: the options
 * of its one thought-level control that are efforts, which is how a gateway's
 * declared efforts are served (providers/effort.py `declared_effort_control`
 * makes each option's id the effort's value). */
function laneEfforts(lane: AgentProviderLane): AgentEffort[] {
  const levels = (lane.catalog.native_controls ?? []).filter(
    (control) => control.kind === "thought_level",
  );
  if (levels.length !== 1) return [];
  return (levels[0]?.options ?? []).flatMap((option) =>
    isEffort(option.option_id) ? [option.option_id] : [],
  );
}

function modelOption(t: Translate, entry: AgentCatalogEntry): ModelOption {
  return {
    id: entry.entry_id,
    name: entry.display_name,
    ...(entry.description ? { description: entry.description } : {}),
    efforts: (entry.efforts ?? []).map((effort) => effortChoice(t, effort)),
    ...(entry.default_effort ? { defaultEffort: entry.default_effort } : {}),
  };
}

export type CatalogChoices = {
  providers: ProviderOption[];
  /** Each way's models, by way id. */
  models: Record<string, ModelOption[]>;
  /** The catalog lists lanes, but none says what provider or transport it
   * is: the service is older than this column. */
  incompatible: boolean;
};

/** The providers and models the column offers, as the catalog has them. */
export function catalogChoices(
  t: Translate,
  catalog: AgentProviderCatalog,
): CatalogChoices {
  const served = catalog.providers ?? [];
  const lanes = served.filter(
    (lane, index) =>
      understood(lane) &&
      served.findIndex((held) => wayId(held) === wayId(lane)) === index,
  );
  const models: Record<string, ModelOption[]> = {};
  // Providers in the order they were served, each with its lanes: the API
  // before the command-line app, whatever order they were served in.
  const grouped = new Map<string, AgentProviderLane[]>();
  for (const lane of lanes)
    grouped.set(lane.provider_id, [
      ...(grouped.get(lane.provider_id) ?? []),
      lane,
    ]);
  const providers = [...grouped].map(([id, group]): ProviderOption => {
    const ways = [...group]
      .sort(
        (a, b) => Number(a.transport === "cli") - Number(b.transport === "cli"),
      )
      .map((lane): ProviderWay => {
        const capabilities = provenCapabilities(t, lane);
        const listed = writesModel(lane)
          ? []
          : (lane.catalog.models ?? []).map((entry) => modelOption(t, entry));
        models[wayId(lane)] = listed;
        const usable =
          lane.health.selectable &&
          lane.executable &&
          (writesModel(lane) || listed.length > 0);
        return {
          id: wayId(lane),
          transport: lane.transport,
          selectable: usable,
          ...(usable ? {} : { unavailableReason: laneHeldBy(t, lane) }),
          ...(capabilities.length > 0 ? { capabilities } : {}),
          ...(lane.catalog.recommended_entry_id
            ? { defaultModelId: lane.catalog.recommended_entry_id }
            : {}),
          ...(writesModel(lane)
            ? {
                modelWritten: {
                  efforts: laneEfforts(lane).map((effort) =>
                    effortChoice(t, effort),
                  ),
                },
              }
            : {}),
        };
      });
    return {
      id,
      // Each lane of a provider carries its name; the first is the provider's.
      name: group[0]?.display_name ?? id,
      selectable: ways.some((way) => way.selectable),
      ways,
    };
  });
  return {
    providers,
    models,
    incompatible: served.length > 0 && lanes.length === 0,
  };
}

/** The model a way starts with: the catalog's recommendation where it lists
 * it, else its first. */
export function startingModel(
  way: ProviderWay,
  models: readonly ModelOption[],
): ModelOption | undefined {
  return models.find((model) => model.id === way.defaultModelId) ?? models[0];
}

/** What a provider starts with once `way` is chosen: its starting model, or,
 * where the person writes the model, none yet. It holds no effort: a model's
 * default is the provider's to apply, and an effort is held only once the
 * person has chosen one. */
export function startingSelection(
  provider: ProviderOption,
  way: ProviderWay,
  models: readonly ModelOption[],
): AgentSelection | null {
  if (way.modelWritten)
    return { providerId: provider.id, wayId: way.id, modelId: "" };
  const model = startingModel(way, models);
  if (!model) return null;
  return { providerId: provider.id, wayId: way.id, modelId: model.id };
}

/** `selection` where the catalog still offers it, else where the first way
 * that can be chosen starts; null when none can. */
export function offeredSelection(
  choices: CatalogChoices,
  selection: AgentSelection | null,
): AgentSelection | null {
  if (selection) {
    const provider = choices.providers.find(
      (held) => held.id === selection.providerId,
    );
    const way = provider?.ways.find((held) => held.id === selection.wayId);
    const model = choices.models[selection.wayId]?.find(
      (held) => held.id === selection.modelId,
    );
    const efforts = way?.modelWritten?.efforts ?? model?.efforts;
    if (
      way?.selectable &&
      (way.modelWritten || model) &&
      (selection.effort === undefined ||
        efforts?.some((effort) => effort.id === selection.effort))
    )
      return selection;
  }
  for (const provider of choices.providers) {
    for (const way of provider.ways) {
      if (!way.selectable) continue;
      const start = startingSelection(
        provider,
        way,
        choices.models[way.id] ?? [],
      );
      if (start) return start;
    }
  }
  return null;
}

// A model id the agent accepts: bounded, with no control character
// (agent/spec.py `MODEL_ID_PATTERN`, `MAX_MODEL_ID_CHARS`).
const MODEL_ID_MAX = 512;
const isModelId = (id: string) =>
  id.length > 0 &&
  id.length <= MODEL_ID_MAX &&
  [...id].every((char) => {
    const code = char.codePointAt(0) ?? 0;
    return code > 0x1f && code !== 0x7f;
  });

/** What a send runs with, as a run start takes it; null while the model is
 * not one the way offers or the person has written. */
export function selectionRecord(
  catalog: AgentProviderCatalog,
  selection: AgentSelection,
): AgentSelectionRecord | null {
  const lane = catalog.providers?.find(
    (held) => understood(held) && wayId(held) === selection.wayId,
  );
  if (!lane) return null;
  const base = { provider: lane.provider_id, transport: lane.transport };
  if (writesModel(lane)) {
    const model = selection.modelId.trim();
    if (!isModelId(model)) return null;
    const effort = laneEfforts(lane).find((held) => held === selection.effort);
    return { ...base, model, ...(effort ? { effort } : {}) };
  }
  const entry = lane.catalog.models?.find(
    (held) => held.entry_id === selection.modelId,
  );
  if (!entry) return null;
  const effort = entry.efforts?.find((held) => held === selection.effort);
  return { ...base, model: entry.model, ...(effort ? { effort } : {}) };
}
