import type {
  ProviderCondition,
  ThreadStatus,
  ToolKind,
} from "./agentGatewayContract";
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
} as const satisfies Record<ToolKind, string>;

/** What kind of tool a call or a request is: one of cadrumo-agent's ten. */
export function toolKindWords(t: Translate, kind: ToolKind): string {
  return t(TOOL_KINDS[kind]);
}

const CONDITIONS = {
  network_unreachable: "desktop.agent.condition_network_unreachable",
  provider_overloaded: "desktop.agent.condition_provider_overloaded",
  unauthenticated: "desktop.agent.lane_signed_out",
  throttled: "desktop.agent.condition_throttled",
  usage_exhausted: "desktop.agent.condition_usage_exhausted",
  credits_exhausted: "desktop.agent.condition_credits_exhausted",
  budget_exhausted: "desktop.agent.condition_budget_exhausted",
  invalid_request: "desktop.agent.condition_invalid_request",
  model_unavailable: "desktop.agent.condition_model_unavailable",
  model_does_not_fit: "desktop.agent.condition_model_does_not_fit",
  no_answer: "desktop.agent.condition_no_answer",
  unknown: "desktop.agent.condition_unknown",
} as const satisfies Record<ProviderCondition, string>;

/** Why a provider failed a run: one of cadrumo-agent's conditions. */
export function conditionWords(
  t: Translate,
  condition: ProviderCondition,
): string {
  const key = (CONDITIONS as Readonly<Record<string, string>>)[
    condition as string
  ];
  return typeof key === "string" ? t(key) : t("desktop.agent.reply_failed");
}

/** The run states a reply is neither written in nor finished in, and that the
 * transcript draws no indicator for. Null for every other state. */
export function runStateWords(
  t: Translate,
  status: ThreadStatus,
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
