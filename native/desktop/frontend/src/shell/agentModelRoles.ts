import type { AgentModelRoles } from "../ipc/contract";
import { isDeclared } from "./agentCatalog";
import type {
  AgentCatalogAnswer,
  AgentModelLicenceFacts,
  AgentRecommendedCapability,
  AgentTransport,
} from "./agentSession";
import type { Translate } from "./strings";

// What the person chooses a model for each role from: the lanes and models of
// cadrumo-agent's catalog, the served one while the agent runs and the
// declared one before. Cadrumo names no role, lane or model here: the roles
// are the service's selections read, and the lanes, the models, what each
// model is and what the agent recommends are the catalog's. Whether a model
// can serve a role is the service's to decide when the person saves it.

/** One model a role can be given, with what the catalog states of it. */
export type RoleModel = {
  /** The model as a run names it, which a selection stores. */
  id: string;
  name: string;
  /** Null where the catalog does not say. */
  vision: boolean | null;
  sizeBytes: number | null;
  licence: AgentModelLicenceFacts | null;
  /** Whether this computer holds the model; null where the catalog does not
   * say, as the declared one does not. */
  installed: boolean | null;
};

/** One lane a role can name, with its models. */
export type RoleLane = {
  /** The catalogue lane id a selection stores. */
  id: string;
  provider: string;
  transport: AgentTransport;
  name: string;
  models: RoleModel[];
  /** What cadrumo-agent recommends on this lane, per capability: offered to
   * the person, never applied. Each names one of `models`. */
  recommended: { capability: AgentRecommendedCapability; model: string }[];
};

const CAPABILITIES: readonly AgentRecommendedCapability[] = ["vision", "text"];

function recommendedOf(
  recommended: Partial<Record<AgentRecommendedCapability, string>> | undefined,
  models: readonly RoleModel[],
): RoleLane["recommended"] {
  return CAPABILITIES.flatMap((capability) => {
    const model = recommended?.[capability];
    return model && models.some((held) => held.id === model)
      ? [{ capability, model }]
      : [];
  });
}

const understood = (transport: string): transport is AgentTransport =>
  transport === "api" || transport === "cli";

/** Every lane of `answer` that lists a model a role can be given. A lane
 * whose models the person writes lists none, so it is not one. */
export function roleLanes(answer: AgentCatalogAnswer): RoleLane[] {
  if (isDeclared(answer))
    return (answer.catalog.providers ?? []).flatMap((lane): RoleLane[] => {
      if (!understood(lane.transport)) return [];
      const models = (lane.models ?? []).map((model): RoleModel => ({
        id: model.id,
        name: model.display_name,
        vision: model.vision ?? null,
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
  return (answer.providers ?? []).flatMap((lane): RoleLane[] => {
    if (!understood(lane.transport) || lane.model_source !== "catalog")
      return [];
    const models = (lane.catalog.models ?? []).map((entry): RoleModel => ({
      id: entry.model,
      name: entry.display_name,
      vision: entry.vision ?? null,
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

/** The lane's models with what cadrumo-agent recommends leading, in the
 * order it recommends them (vision first), then the rest in the catalogue's
 * own order. Nothing is ranked here beyond what the catalogue says. */
export function localModelOrder(
  lane: RoleLane,
): { model: RoleModel; recommended: AgentRecommendedCapability[] }[] {
  const recommended = (id: string) =>
    lane.recommended
      .filter((entry) => entry.model === id)
      .map((entry) => entry.capability);
  const leading = lane.recommended
    .map((entry) => entry.model)
    .filter((id, index, ids) => ids.indexOf(id) === index)
    .flatMap((id) => lane.models.filter((model) => model.id === id));
  const rest = lane.models.filter(
    (model) => !leading.some((held) => held.id === model.id),
  );
  return [...leading, ...rest].map((model) => ({
    model,
    recommended: recommended(model.id),
  }));
}

/** The roles of a readable snapshot, in the service's order. */
export function rolesOf(snapshot: AgentModelRoles) {
  return snapshot.state === "readable" ? snapshot.roles : [];
}

/** A role's name in words; a role the catalogue has no words for yet is
 * shown as the service names it. */
export function roleWords(t: Translate, role: string): string {
  const key = `desktop.setup.role.${role}`;
  const words = t(key);
  return words === key ? role : words;
}

/** A lane in words: its provider's name and how it is reached, as the
 * provider list names it, since one provider can have a lane of each. */
export function laneWords(
  t: Translate,
  lane: Pick<RoleLane, "name" | "transport">,
): string {
  const connection =
    lane.transport === "api"
      ? t("desktop.providers.connection_api")
      : t("desktop.providers.connection_app");
  return `${lane.name}, ${connection}`;
}

/** A capability cadrumo-agent recommends a model for, in words. */
export function capabilityWords(
  t: Translate,
  capability: AgentRecommendedCapability,
): string {
  return capability === "vision"
    ? t("desktop.agent.model_role_capability_vision")
    : t("desktop.agent.model_role_capability_text");
}

/** Why a change to a selection was not made, in words. */
export function roleRefusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_model_role_unknown_role":
      return t("desktop.agent.model_role_refused_unknown_role");
    case "agent_model_role_model_not_in_catalogue":
      return t("desktop.agent.model_role_refused_model_not_in_catalogue");
    case "agent_model_role_lane_not_runnable":
      return t("desktop.agent.model_role_refused_lane_not_runnable");
    case "agent_model_role_vision_required":
      return t("desktop.agent.model_role_refused_vision_required");
    case "agent_model_role_revision_conflict":
      return t("desktop.agent.model_role_refused_revision_conflict");
    case "agent_model_role_committed_readback_failed":
      return t("desktop.agent.model_role_refused_committed_readback_failed");
    case "agent_model_role_catalog_unavailable":
      return t("desktop.agent.model_role_refused_catalog_unavailable");
    case "agent_signed_out":
      return t("desktop.agent.service_signed_out");
    case "agent_service_busy":
    case "agent_service_not_ready":
      return t("desktop.agent.service_starting");
    default:
      return t("desktop.agent.model_role_refused_unknown");
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
