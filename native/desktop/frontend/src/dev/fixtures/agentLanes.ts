import type {
  ConversationCarry,
  SeededHistory,
  SelectedModel,
} from "../../shell/agentGatewayContract";
import type {
  AgentSelectionRecord,
  AgentSendRequest,
} from "../../shell/agentSession";
import { isLiveStatus } from "../../shell/agentViews";
import type { ServedProviderCatalog } from "../../shell/agentCatalogContract";
import { SEED_DEPTH, type FixtureMessage, type FixtureRun } from "./agent";

// What the scenario host's agent answers where a conversation changes lane or
// model, in the shapes cadrumo-agent states them. The counts are derived from
// the conversation's own messages, as the agent derives them from its
// checkpoint; the estimator is the fixture's own, a quarter token a character.

/** A message that makes the continuing send be refused because the agent
 * cannot read which lane the conversation runs on. */
export const LANE_UNREADABLE = /carril ilegible/i;
/** A message whose run fails because its model is not one the lane serves
 * any more. */
export const MODEL_UNAVAILABLE = /modelo no disponible/i;
export const MODEL_UNAVAILABLE_WHY = {
  provider_condition: "model_unavailable" as const,
  failure_reason: "Internal provider error: model not found.",
};

/** The most turns a carry takes: the fixture's budget. */
export const CARRY_TURN_LIMIT = 1;

const tokensOf = (messages: readonly FixtureMessage[]) =>
  Math.ceil(
    messages.reduce((sum, message) => sum + message.text.length, 0) / 4,
  );

const modelOf = (
  model: string | null,
  effort: SelectedModel["effort"],
): SelectedModel => ({ model: model ?? "", effort: effort ?? null });

/** Whether `requested` is a model or effort other than the one `run` ran
 * with. */
export function changesSelection(
  run: FixtureRun,
  requested: AgentSelectionRecord,
): boolean {
  const ran = run.selection;
  if (!ran) return false;
  return (
    ran.model !== requested.model ||
    (ran.effort ?? null) !== (requested.effort ?? null)
  );
}

/** What the agent states of a change of model: the one `run` ran with, the one
 * asked for, and how much of the history the new one reads uncached. */
export function selectionChangeFacts(
  run: FixtureRun,
  requested: AgentSelectionRecord,
): {
  previous: SelectedModel;
  requested: SelectedModel;
  history: SeededHistory;
} {
  const retained = run.messages.slice(-SEED_DEPTH);
  return {
    previous: modelOf(run.selection?.model ?? null, run.selection?.effort),
    requested: modelOf(requested.model, requested.effort),
    history: {
      retained_messages: retained.length,
      estimated_tokens: tokensOf(retained),
      omitted_messages: Math.max(0, run.messages.length - retained.length),
    },
  };
}

/** What a first message carries from `source`'s newest run: whole turns,
 * newest first, up to the fixture's budget, and the messages those turns
 * seed the new run with. */
export function carryFrom(source: FixtureRun): {
  carry: ConversationCarry;
  seeded: FixtureMessage[];
} {
  // A turn is a person's message and what followed it.
  const starts = source.messages.flatMap((message, index) =>
    message.role === "user" ? [index] : [],
  );
  const taken = starts.slice(-CARRY_TURN_LIMIT);
  const first = taken[0] ?? source.messages.length;
  const seeded = source.messages.slice(first);
  const left = source.messages.slice(0, first);
  const lane = source.selection?.provider
    ? `${source.selection.provider}/${source.selection.transport}`
    : null;
  return {
    seeded,
    carry: {
      source_run_id: source.id,
      source_lane: lane,
      carried_turns: taken.length,
      omitted_turns: starts.length - taken.length,
      carried_tokens: tokensOf(seeded),
      omitted_tokens: tokensOf(left),
      limit: null,
    },
  };
}

const coded = (code: string) => Object.assign(new Error(code), { code });

declare global {
  interface Window {
    /** How many of the next catalog reads answer the first lane's model list
     * as the packaged one, stale, while the account's is still being read. */
    __fixtureCatalogStaleReads?: number;
  }
}

/**
 * What the agent decides of a request before it starts a run, by the runs it
 * holds: a conversation that has run stays on the lane of its newest run, and
 * a change of model or effort within it waits on the person's word; a first
 * message may carry another conversation, which must be settled. Throws the
 * agent's refusal; returns what a carried first message took over. What the
 * request asked of the lane is said first, whether the agent takes it or not.
 */
export function admitted(
  say: (call: string) => void,
  runsOf: Record<string, FixtureRun[]>,
  request: AgentSendRequest,
): { carry: ConversationCarry; seeded: FixtureMessage[] } | undefined {
  const { conversation_id: id } = request;
  if (request.carries_from)
    say(`agentSendCarriesFrom ${id} ${request.carries_from}`);
  if (request.acknowledge_selection_change) say(`agentSendAcknowledged ${id}`);
  const last = runsOf[id]?.at(-1);
  const { provider, transport } = request.selection;
  if (request.carries_from && last) throw coded("agent_invalid_request");
  if (last) {
    if (LANE_UNREADABLE.test(request.text))
      throw coded("agent_gateway_conversation_lane_unreadable");
    const ran = last.selection;
    if (
      ran?.provider &&
      (ran.provider !== provider || ran.transport !== transport)
    )
      throw Object.assign(coded("agent_gateway_conversation_lane_fixed"), {
        lane: { provider: ran.provider, transport: ran.transport },
      });
    if (
      changesSelection(last, request.selection) &&
      !request.acknowledge_selection_change
    )
      throw Object.assign(
        coded("agent_gateway_selection_change_unacknowledged"),
        { selection_change: selectionChangeFacts(last, request.selection) },
      );
  }
  if (!request.carries_from) return undefined;
  const source = runsOf[request.carries_from]?.at(-1);
  if (!source) throw coded("agent_gateway_carry_source_not_found");
  if (isLiveStatus(source.status))
    throw coded("agent_gateway_carry_source_not_settled");
  return carryFrom(source);
}

/** `answer` with the first lane's model list the packaged one, stale, for as
 * many reads as the scenario asked in `__fixtureCatalogStaleReads`: the
 * account's own list is still being read. */
export function withStaleReads(
  answer: ServedProviderCatalog,
): ServedProviderCatalog {
  const stale = window.__fixtureCatalogStaleReads ?? 0;
  if (stale <= 0) return answer;
  window.__fixtureCatalogStaleReads = stale - 1;
  return {
    ...answer,
    providers: (answer.providers ?? []).map((lane, index) =>
      index === 0
        ? {
            ...lane,
            catalog: {
              ...lane.catalog,
              model_list_source: "packaged" as const,
              state: {
                status: "stale" as const,
                checked_at: lane.catalog.state.checked_at,
              },
            },
          }
        : lane,
    ),
  };
}
