import type {
  ProviderCondition,
  ThreadStatus,
  ToolKind,
  ToolReach,
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

const TOOL_REACHES = {
  local_read: "desktop.agent.tool_reach.local_read",
  local_write: "desktop.agent.tool_reach.local_write",
  online: "desktop.agent.tool_reach.online",
} as const satisfies Record<ToolReach, string>;

/** How far a tool reaches, in words; null where the agent did not say. */
export function toolReachWords(
  t: Translate,
  reach: ToolReach | null | undefined,
): string | null {
  const key = reach
    ? (TOOL_REACHES as Readonly<Record<string, string>>)[reach]
    : undefined;
  return key ? t(key) : null;
}

/** A segment the agent serves of a tool's identity, spelled as a key segment. */
const KEY_SEGMENT = /^[a-z0-9_-]+$/;

/** The words a key has, or null: a translator shows a key it lacks as the key
 * itself. */
function worded(t: Translate, key: string): string | null {
  const words = t(key);
  return words === key ? null : words;
}

/** What a tool is called and does, in words: the label every row and card
 * names it by, and the one sentence the catalogue gives of what it does. */
export type ToolWords = { label: string; description: string | null };

/**
 * The words for a tool by the identity the agent serves: its server and its
 * own name. A tool the catalogue has no words for is named generically by the
 * name it carries; a call that carries no name is shown under the title the
 * agent gave it, unless that is a provider's raw `mcp__` name, and otherwise
 * under its kind. No raw tool identifier is shown by a view that asks here.
 */
export function toolIdentityWords(
  t: Translate,
  call: {
    server?: string | null;
    name?: string | null;
    title?: string | null;
    kind?: ToolKind | null;
  },
): ToolWords {
  const { server, name, title, kind } = call;
  if (name && !name.startsWith("mcp__")) {
    if (server && KEY_SEGMENT.test(server) && KEY_SEGMENT.test(name)) {
      const label = worded(t, `desktop.agent.tool.${server}.${name}.label`);
      if (label)
        return {
          label,
          description: worded(
            t,
            `desktop.agent.tool.${server}.${name}.description`,
          ),
        };
    }
    return {
      label: t("desktop.agent.tool_generic", { name }),
      description: null,
    };
  }
  if (title && !title.startsWith("mcp__"))
    return { label: title, description: null };
  return {
    label: kind ? toolKindWords(t, kind) : t("desktop.agent.tool_unnamed"),
    description: null,
  };
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
