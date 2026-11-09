import type { AgentServiceStatus } from "../../shell/agentSession";
import type { Translate } from "../../shell/strings";

/** Why the agent service is not serving, in words; null when it is. */
export function serviceWords(
  t: Translate,
  status: AgentServiceStatus,
): string | null {
  if (status.state === "ready") return null;
  if (status.state === "starting") return t("desktop.agent.service_starting");
  if (status.state === "stopped") return t("desktop.agent.service_stopped");
  return refusalWords(t, status.code);
}

/** A refusal code of the agent's, in words where it is one we know. */
export function refusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_platform_unsupported":
      return t("desktop.agent.platform_unsupported");
    case "agent_service_absent":
      return t("desktop.agent.service_absent");
    case "agent_service_incompatible":
      return t("desktop.agent.service_incompatible");
    case "agent_signed_out":
      return t("desktop.agent.service_signed_out");
    case "agent_runtime_unavailable":
      return t("desktop.agent.service_runtime_unavailable");
    case "agent_provider_credential_missing":
      return t("desktop.agent.service_credential_missing");
    case "agent_service_failed":
      return t("desktop.agent.service_failed");
    case "agent_timeout":
      return t("desktop.agent.service_timeout");
    case "agent_service_busy":
      return t("desktop.agent.service_starting");
    case "agent_reconnecting":
      return t("desktop.account.reconnecting");
    case "agent_reply_in_progress":
      return t("desktop.agent.reply_in_progress");
    case "agent_conversation_delete_incomplete":
      return t("desktop.agent.delete_incomplete");
    case "agent_gateway_attachment_not_found":
      return t("desktop.agent.reference_missing");
    case "agent_gateway_attachment_changed":
      return t("desktop.agent.reference_changed");
    case "agent_gateway_attachment_refused":
    case "agent_gateway_attachments_invalid":
      return t("desktop.agent.reference_refused");
    case "agent_gateway_attachments_unavailable":
      return t("desktop.agent.references_unavailable");
    case "agent_gateway_conversation_deleting":
      return t("desktop.agent.conversation_deleting");
    case "agent_gateway_conversation_id_taken":
      return t("desktop.agent.conversation_id_taken");
    case "agent_gateway_model_not_installed":
      return t("desktop.agent.model_not_installed_refused");
    default:
      return t("desktop.agent.request_failed");
  }
}
