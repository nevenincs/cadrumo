import type { AgentLocalModels } from "../ipc/contract";
import { isDeclared } from "./agentCatalog";
import type {
  AgentCatalogAnswer,
  AgentModelLicenceFacts,
  AgentRecommendedCapability,
  AgentTransport,
} from "./agentSession";
import type { Translate } from "./strings";

// A local lane's model list: the models cadrumo-agent's catalog recommends
// for the lane, then the models the person added by name. The lanes, the
// models and what each one is are the catalog's, the served one while the
// agent runs and the declared one before. Cadrumo names no model here and
// ranks none beyond the catalog's own order.

/** One model of a lane, with what the catalog states of it. */
export type LaneModel = {
  /** The model as a run names it. */
  id: string;
  name: string;
  sizeBytes: number | null;
  licence: AgentModelLicenceFacts | null;
  /** Whether this computer holds the model; null where the catalog does not
   * say, as the declared one does not. */
  installed: boolean | null;
};

/** One catalog lane with its models and the ones it recommends. */
export type CatalogLane = {
  /** The catalogue lane id the lists store. */
  id: string;
  provider: string;
  transport: AgentTransport;
  name: string;
  models: LaneModel[];
  /** What cadrumo-agent recommends on this lane, in its capability order,
   * each once. Each names one of `models`. */
  recommended: string[];
};

/** One entry of a lane's model list. */
export type ListedLaneModel = {
  model: LaneModel;
  /** Added by the person, so the person can take it off the list; a
   * recommended model stays listed. */
  added: boolean;
};

const CAPABILITIES: readonly AgentRecommendedCapability[] = ["vision", "text"];

function recommendedOf(
  recommended: Partial<Record<AgentRecommendedCapability, string>> | undefined,
  models: readonly LaneModel[],
): string[] {
  const named = CAPABILITIES.flatMap((capability) => {
    const model = recommended?.[capability];
    return model && models.some((held) => held.id === model) ? [model] : [];
  });
  return named.filter((id, index) => named.indexOf(id) === index);
}

const understood = (transport: string): transport is AgentTransport =>
  transport === "api" || transport === "cli";

/** Every lane of `answer` that lists models. A lane whose models the person
 * writes lists none, so it is not one. */
export function catalogLanes(answer: AgentCatalogAnswer): CatalogLane[] {
  if (isDeclared(answer))
    return (answer.catalog.providers ?? []).flatMap((lane): CatalogLane[] => {
      if (!understood(lane.transport)) return [];
      const models = (lane.models ?? []).map((model): LaneModel => ({
        id: model.id,
        name: model.display_name,
        sizeBytes: model.size_bytes ?? null,
        licence: model.licence ?? null,
        installed: null,
      }));
      if (models.length === 0) return [];
      return [
        {
          id: lane.id,
          provider: lane.provider,
          transport: lane.transport,
          name: lane.display_name,
          models,
          recommended: recommendedOf(lane.recommended, models),
        },
      ];
    });
  return (answer.providers ?? []).flatMap((lane): CatalogLane[] => {
    if (!understood(lane.transport) || lane.model_source !== "catalog")
      return [];
    const models = (lane.catalog.models ?? []).map((entry): LaneModel => ({
      id: entry.model,
      name: entry.display_name,
      sizeBytes: entry.size_bytes ?? null,
      licence: entry.licence ?? null,
      // The served catalog marks only a model this computer lacks.
      installed: entry.installed ?? true,
    }));
    if (models.length === 0) return [];
    return [
      {
        id: `${lane.provider_id}_${lane.transport}`,
        provider: lane.provider_id,
        transport: lane.transport,
        name: lane.display_name,
        models,
        recommended: recommendedOf(lane.catalog.recommended, models),
      },
    ];
  });
}

/** The models the person added to `lane`, in the order added. */
export function addedTo(lists: AgentLocalModels, lane: string): string[] {
  return lists.state === "readable"
    ? lists.models
        .filter((entry) => entry.lane === lane)
        .map((entry) => entry.model)
    : [];
}

/** `lane`'s model list: the recommended models, then `added` that are not
 * already listed. An added model the catalog lists carries its facts; one it
 * does not list is known by its name alone. */
export function laneModelList(
  lane: CatalogLane,
  added: readonly string[],
): ListedLaneModel[] {
  const entry = (id: string): LaneModel =>
    lane.models.find((model) => model.id === id) ?? {
      id,
      name: id,
      sizeBytes: null,
      licence: null,
      installed: null,
    };
  const recommended = lane.recommended.map((id) => ({
    model: entry(id),
    added: false,
  }));
  const extra = added
    .filter(
      (id, index) =>
        !lane.recommended.includes(id) && added.indexOf(id) === index,
    )
    .map((id) => ({ model: entry(id), added: true }));
  return [...recommended, ...extra];
}

/** Why a change to a list was not made, in words. */
export function listRefusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_local_models_full":
      return t("desktop.providers.local_models_refused_full");
    case "agent_local_models_revision_conflict":
      return t("desktop.providers.local_models_refused_revision_conflict");
    case "agent_local_models_committed_readback_failed":
      return t(
        "desktop.providers.local_models_refused_committed_readback_failed",
      );
    case "agent_local_models_catalog_unavailable":
      return t("desktop.providers.local_models_refused_catalog_unavailable");
    case "agent_invalid_request":
      return t("desktop.providers.local_models_refused_invalid_name");
    case "agent_signed_out":
      return t("desktop.agent.service_signed_out");
    case "agent_service_busy":
    case "agent_service_not_ready":
      return t("desktop.agent.service_starting");
    default:
      return t("desktop.providers.local_models_refused_unknown");
  }
}

/** A download size in the window's language. */
export function sizeWords(locale: string, bytes: number): string {
  const gigabytes = bytes / 1e9;
  const [value, unit] =
    gigabytes >= 1 ? [gigabytes, "gigabyte"] : [bytes / 1e6, "megabyte"];
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit,
    maximumFractionDigits: 1,
  }).format(value);
}
