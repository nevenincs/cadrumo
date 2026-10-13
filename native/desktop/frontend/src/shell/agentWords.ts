import type { AgentToolKind } from "./agentSession";
import type { AgentProviderCondition, AgentRunStatus } from "./agentViews";
import type { Translate } from "./strings";

// The words for the closed values cadrumo-agent serves, and for nothing else:
// a tool's kind, why a provider failed a run, and the states of a run that
// the transcript draws no indicator for. Each value has one string in every
// locale, and none adds to what the value says.

const TOOL_KINDS = {
  read: "desktop.agent.tool_kind_read",
  edit: "desktop.agent.tool_kind_edit",
  delete: "desktop.agent.tool_kind_delete",
  move: "desktop.agent.tool_kind_move",
  search: "desktop.agent.tool_kind_search",
  execute: "desktop.agent.tool_kind_execute",
  think: "desktop.agent.tool_kind_think",
  fetch: "desktop.agent.tool_kind_fetch",
  switch_mode: "desktop.agent.tool_kind_switch_mode",
  other: "desktop.agent.tool_kind_other",
} as const satisfies Record<AgentToolKind, string>;

/** What kind of tool a call or a request is: one of cadrumo-agent's ten. */
export function toolKindWords(t: Translate, kind: AgentToolKind): string {
  return t(TOOL_KINDS[kind]);
}

const CONDITIONS = {
  network_unreachable: "desktop.agent.condition_network_unreachable",
  provider_overloaded: "desktop.agent.condition_provider_overloaded",
  unauthenticated: "desktop.agent.condition_unauthenticated",
  throttled: "desktop.agent.condition_throttled",
  usage_exhausted: "desktop.agent.condition_usage_exhausted",
  credits_exhausted: "desktop.agent.condition_credits_exhausted",
  budget_exhausted: "desktop.agent.condition_budget_exhausted",
  invalid_request: "desktop.agent.condition_invalid_request",
  unknown: "desktop.agent.condition_unknown",
} as const satisfies Record<AgentProviderCondition, string>;

/** Why a provider failed a run: one of cadrumo-agent's nine conditions. */
export function conditionWords(
  t: Translate,
  condition: AgentProviderCondition,
): string {
  return t(CONDITIONS[condition]);
}

/** The run states a reply is neither written in nor finished in, and that the
 * transcript draws no indicator for. Null for every other state. */
export function runStateWords(
  t: Translate,
  status: AgentRunStatus,
): string | null {
  switch (status) {
    case "cancelling":
      return t("desktop.agent.reply_stopping");
    case "repair_needed":
      return t("desktop.agent.reply_repair_needed");
    case "reconciling":
      return t("desktop.agent.reply_reconciling");
    case "deleting":
      return t("desktop.agent.reply_deleting");
    case "submitted":
    case "running":
    case "input_required":
    case "cancelled":
    case "completed":
    case "failed":
    case "archived":
      return null;
  }
}

/** Messages queued behind a run's current turn. */
export function queuedWords(t: Translate, count: number): string {
  return t("desktop.agent.reply_queued", { count });
}
