import type { LocalModelListStatus } from "./localModelsContract";
import type { Translate } from "./strings";

// The person's local model lists: the models added to each lane, and why a
// change to a list or to the engine was not made, in words. The lanes and
// their models are the agent offer's (agentOffer.ts).

/** The models the person added to `lane`, in the order added. */
export function addedTo(lists: LocalModelListStatus, lane: string): string[] {
  return !lists.unreadable
    ? lists.models
        .filter((entry) => entry.lane === lane)
        .map((entry) => entry.model)
    : [];
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
    case "agent_reconnecting":
      return t("desktop.account.reconnecting");
    default:
      return t("desktop.providers.local_models_refused_unknown");
  }
}

/** Why the engine or placement was not changed, in words. */
export function engineRefusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_local_models_revision_conflict":
    case "agent_local_models_committed_readback_failed":
    case "agent_local_models_catalog_unavailable":
    case "agent_local_models_unknown":
      return listRefusalWords(t, code);
    case "agent_local_engine_unavailable":
      return t("desktop.providers.local_engine_unavailable");
    default:
      return t("desktop.providers.local_engine_change_failed");
  }
}
