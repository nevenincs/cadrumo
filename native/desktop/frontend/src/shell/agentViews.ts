import { useEffect, useMemo, useState } from "react";
import type {
  AgentReplyState,
  ConversationGroup,
  TranscriptItem,
} from "@/components/agent/types";
import { failureCode } from "../errors";
import { effortWords } from "./agentCatalog";
import type {
  AgentEffort,
  AgentToolKind,
  AgentTransport,
} from "./agentSession";
import { conditionWords, toolKindWords } from "./agentWords";
import type { Translate } from "./strings";

// What a host serves the agent column, as the host answers it. A desktop
// host serves these through its closed set of agent commands, from
// cadrumo-agent's gateway. A host that cannot serves none of them, and the
// column shows each view as not available yet: never as empty, and never made
// up.
//
// cadrumo-agent has no conversation: its unit is the run, one message and the
// reply to it. A conversation here is a chain of runs, each continuing the
// one before, and the host composes everything below from the runs it reads.
// What the agent does not serve is not here: no title but the first run's, no
// message id that tells two identical messages apart, no place for a tool call
// among a reply's text.

/** A run's lifecycle: cadrumo-agent's `ThreadStatus`, as it is served. */
export type AgentRunStatus =
  | "submitted"
  | "running"
  | "input_required"
  | "cancelling"
  | "cancelled"
  | "completed"
  | "failed"
  | "archived"
  | "repair_needed"
  | "reconciling"
  | "deleting";

/** Why a provider failed a run: cadrumo-agent's `ProviderCondition`. */
export type AgentProviderCondition =
  | "network_unreachable"
  | "provider_overloaded"
  | "unauthenticated"
  | "throttled"
  | "usage_exhausted"
  | "credits_exhausted"
  | "budget_exhausted"
  | "invalid_request"
  | "unknown";

/** Where a tool call is: cadrumo-agent's `ToolCallStatus`. */
export type AgentToolStatus =
  "pending" | "in_progress" | "completed" | "failed";

/** A tool call as the agent reports it: its `tool_call_id`, its `title` (the
 * tool's name), its `kind` and its `status`. Its input and result are not
 * here: the stream carries none, and the history's input may be private. */
export type AgentToolCall = {
  id: string;
  title: string;
  tool_kind: AgentToolKind;
  status: AgentToolStatus;
};

/** What a reply ran with, as the agent froze it when the run started: the
 * provider and the way into it, the model and the effort it applied. The
 * display names are the agent's own and are absent where it served none. */
export type AgentRanWith = {
  provider: string;
  transport: AgentTransport;
  provider_display_name?: string | null;
  model: string;
  model_display_name?: string | null;
  effort?: AgentEffort | null;
};

/** The tokens a run's provider reported, as the agent counts them. The agent
 * serves no cost, and none is made up. */
export type AgentUsage = {
  input_tokens: number;
  output_tokens: number;
};

/** One conversation: a chain of runs, composed by the host. */
export type AgentConversationRecord = {
  /** The first run's id: the head of the chain. */
  id: string;
  /** The first run's title; empty where the agent was given none. */
  title: string;
  /** When its newest run was last updated, as an ISO instant. */
  last_active_at: string;
  /** Every run of the chain is archived. Archiving is per run, of a settled
   * run only, and cannot be undone. */
  archived: boolean;
};

/** A document of a conversation. Cadrumo's custody serves none yet: no host
 * answers `documents`, and the column does not ask. */
export type AgentDocumentRecord = {
  id: string;
  name: string;
  media_type: string;
  size_bytes: number;
};

/** The record of a reply (a run) itself. */
export type AgentReplyRecord = {
  kind: "reply";
  /** The run's id: the reply's handle. */
  id: string;
  status: AgentRunStatus;
  /** For a failed run, why its provider failed. */
  provider_condition?: AgentProviderCondition | null;
  /** For a failed run, the agent's one line about it. */
  failure_reason?: string | null;
  /** Messages queued behind the run's current turn. */
  queued_messages?: number;
  selection?: AgentRanWith | null;
  usage?: AgentUsage | null;
};

/**
 * What history lists of a conversation, oldest first, in the order the host
 * composes it from its runs. Each record names the reply (run) it comes from,
 * and a reply's records are listed together: the person's messages, then its
 * tool calls, then the agent's messages, and last the reply's own record.
 * Each message is listed once: a run that continues another is seeded with
 * the last of its messages under new ids, and the host leaves those out.
 * cadrumo-agent links no tool call to a message, so a call has no place among
 * the agent's text.
 *
 * A reply in progress has no agent message here: the agent records a message
 * when its turn ends, and the text so far comes from the stream. A reply that
 * failed before it wrote has no message either, and its reply record says
 * why. The host invents neither.
 */
export type AgentTurnRecord =
  | {
      kind: "person";
      /** cadrumo-agent's `message_id`, a hash of role and content where it
       * has none. Two identical messages can share one: only their order
       * tells them apart. */
      id: string;
      reply_id: string;
      text: string;
      /** When it was sent, as an ISO instant; null where the agent has no
       * time for it. */
      sent_at: string | null;
    }
  | {
      kind: "agent";
      /** cadrumo-agent's `message_id`: the id the stream's text names. */
      id: string;
      reply_id: string;
      text: string;
    }
  | ({ kind: "tool"; reply_id: string } & AgentToolCall)
  | AgentReplyRecord;

/** The reply a record belongs to. */
export const replyIdOf = (record: AgentTurnRecord): string =>
  record.kind === "reply" ? record.id : record.reply_id;

/** The agent views a host offers. Each read is refused while nobody is
 * signed in, as the profile's own views are. */
export interface AgentViews {
  /** Every conversation of the signed-in profile, archived ones included. */
  conversations(): Promise<AgentConversationRecord[]>;
  /** The records of one conversation, oldest first. */
  history(conversationId: string): Promise<AgentTurnRecord[]>;
  /** Not served by any host yet, and not asked for. */
  documents?(conversationId: string): Promise<AgentDocumentRecord[]>;
}

/** A read the column makes: not offered by the host, on its way, refused,
 * or answered. Not offered is its own state, never shown as empty. */
export type AgentRead<T> =
  | { kind: "unavailable" }
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: T };

/**
 * Reads what `read` asks for whenever it changes, and drops the answer to a
 * question no longer asked. Null means the host does not offer the read, or
 * nobody it would belong to is signed in. A change of `again` asks the same
 * question again, keeping the last answer on screen until the new one.
 */
export function useAgentRead<T>(
  read: (() => Promise<T>) | null,
  again = 0,
): AgentRead<T> {
  const [state, setState] = useState<{
    for: (() => Promise<T>) | null;
    read: AgentRead<T>;
  }>({ for: null, read: { kind: "unavailable" } });
  useEffect(() => {
    if (!read) return;
    let current = true;
    read().then(
      (value) => {
        if (current) setState({ for: read, read: { kind: "ready", value } });
      },
      (error: unknown) => {
        if (current)
          setState({
            for: read,
            read: { kind: "failed", code: failureCode(error) },
          });
      },
    );
    return () => {
      current = false;
    };
  }, [read, again]);
  if (!read) return { kind: "unavailable" };
  // An answer belongs to the read that asked for it: a new read is loading
  // until it has its own.
  return state.for === read ? state.read : { kind: "loading" };
}

/** Whether a run is still going: neither settled nor past help. */
export const isLiveStatus = (status: AgentRunStatus): boolean =>
  status === "submitted" ||
  status === "running" ||
  status === "input_required" ||
  status === "cancelling";

/** How a reply's run reads in the transcript. A run that is stopping, needs
 * repair or is being reconciled is neither being written nor finished: the
 * column says so beside the conversation, and the transcript draws no
 * indicator for it. */
function replyState(status: AgentRunStatus): AgentReplyState {
  switch (status) {
    case "submitted":
    case "running":
    case "input_required":
      return "working";
    case "cancelled":
      return "stopped";
    case "failed":
      return "failed";
    case "completed":
    case "archived":
    case "cancelling":
    case "repair_needed":
    case "reconciling":
    case "deleting":
      return "complete";
  }
}

/** Why a reply failed, in words: the provider's condition, then the agent's
 * own line. Undefined where the agent served neither. */
function failureWords(
  t: Translate,
  reply: AgentReplyRecord,
): string | undefined {
  const words = [
    reply.provider_condition
      ? conditionWords(t, reply.provider_condition)
      : undefined,
    reply.failure_reason || undefined,
  ].filter((part): part is string => part !== undefined);
  return words.length > 0 ? words.join(": ") : undefined;
}

/** When a message was sent, in words: the time today, else the day too. */
function sentLabel(locale: string, at: Date, now: Date): string | undefined {
  if (!Number.isFinite(at.getTime())) return undefined;
  const sameDay = dayStart(at) === dayStart(now);
  return new Intl.DateTimeFormat(locale, {
    ...(sameDay ? {} : { day: "numeric", month: "short" }),
    hour: "numeric",
    minute: "2-digit",
  }).format(at);
}

/**
 * A conversation's records as the transcript lists them. Every item has an id
 * of its own, though two identical messages share the agent's: it is the
 * reply, the record's id and how many came before it. A reply's state is
 * drawn on its last agent message, or, where it has none (it is still
 * starting, or it ended before it wrote), on an item of its own that the
 * reply's record alone makes.
 */
export function transcriptItems(
  records: readonly AgentTurnRecord[],
  locale: string,
  t: Translate,
  now: Date = new Date(),
): TranscriptItem[] {
  const replies = new Map<string, AgentReplyRecord>();
  const lastAgent = new Map<string, number>();
  records.forEach((record, index) => {
    if (record.kind === "reply") replies.set(record.id, record);
    else if (record.kind === "agent") lastAgent.set(record.reply_id, index);
  });
  const counts = new Map<string, number>();
  const unique = (key: string) => {
    const before = counts.get(key) ?? 0;
    counts.set(key, before + 1);
    return before === 0 ? key : `${key}#${before}`;
  };
  const drawn = (reply: AgentReplyRecord) => {
    const state = replyState(reply.status);
    const reason = state === "failed" ? failureWords(t, reply) : undefined;
    return {
      state,
      ...(reason ? { failureReason: reason } : {}),
      ...(reply.status === "input_required"
        ? { waitingOnPerson: true as const }
        : {}),
    };
  };
  const items: TranscriptItem[] = [];
  records.forEach((record, index) => {
    switch (record.kind) {
      case "person": {
        const sentAtLabel = record.sent_at
          ? sentLabel(locale, new Date(record.sent_at), now)
          : undefined;
        items.push({
          kind: "person",
          id: unique(`person:${record.reply_id}:${record.id}`),
          text: record.text,
          ...(sentAtLabel ? { sentAtLabel } : {}),
        });
        return;
      }
      case "tool":
        items.push({
          kind: "tool",
          id: unique(`tool:${record.reply_id}:${record.id}`),
          label: record.title,
          state: record.status,
          detail: toolKindWords(t, record.tool_kind),
        });
        return;
      case "agent": {
        const reply = replies.get(record.reply_id);
        const last = lastAgent.get(record.reply_id) === index;
        items.push({
          kind: "agent",
          id: unique(`agent:${record.reply_id}:${record.id}`),
          text: record.text,
          ...(last && reply ? drawn(reply) : { state: "complete" as const }),
        });
        return;
      }
      case "reply": {
        if (lastAgent.has(record.id)) return;
        const state = drawn(record);
        if (state.state === "complete") return;
        items.push({
          kind: "agent",
          id: unique(`reply:${record.id}`),
          text: "",
          ...state,
        });
      }
    }
  });
  return items;
}

const capitalized = (text: string, locale: string) =>
  text.charAt(0).toLocaleUpperCase(locale) + text.slice(1);

/** How long ago an instant was, in the largest whole unit, in words. */
function agoLabel(locale: string, at: Date, now: Date): string {
  const words = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const seconds = Math.round((at.getTime() - now.getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 365 * 86_400],
    ["month", 30 * 86_400],
    ["week", 7 * 86_400],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units)
    if (Math.abs(seconds) >= size)
      return words.format(Math.round(seconds / size), unit);
  return words.format(0, "minute");
}

/** The calendar day of an instant, where the person is. */
const dayStart = (at: Date) =>
  new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime();

/**
 * The conversations the history shows, newest first, under the headings the
 * person reads them by: today, yesterday, then each earlier month. The
 * words come from the locale itself, so no heading is a translation. A
 * conversation whose first run has no title is named `untitled`.
 */
export function conversationGroups(
  records: readonly AgentConversationRecord[],
  {
    locale,
    archived,
    currentId,
    untitled,
    now = new Date(),
  }: {
    locale: string;
    archived: boolean;
    currentId: string | null;
    untitled: string;
    now?: Date;
  },
): ConversationGroup[] {
  const days = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const months = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
  });
  const today = dayStart(now);
  const groups: {
    heading: string;
    conversations: ConversationGroup["conversations"][number][];
  }[] = [];
  const shown = records
    .filter((record) => record.archived === archived)
    .map((record) => ({ record, at: new Date(record.last_active_at) }))
    .filter(({ at }) => Number.isFinite(at.getTime()))
    .sort((a, b) => b.at.getTime() - a.at.getTime());
  for (const { record, at } of shown) {
    const behind = Math.round((today - dayStart(at)) / 86_400_000);
    const heading = capitalized(
      behind <= 1
        ? days.format(-Math.max(0, behind), "day")
        : months.format(at),
      locale,
    );
    let group = groups.at(-1);
    if (group?.heading !== heading) {
      group = { heading, conversations: [] };
      groups.push(group);
    }
    group.conversations.push({
      id: record.id,
      title: record.title || untitled,
      lastActivityLabel: agoLabel(locale, at, now),
      // Cadrumo's custody serves no documents yet, so none is counted.
      documentCount: 0,
      archived: record.archived,
      current: record.id === currentId,
    });
  }
  return groups;
}

/** The archived conversations, counted for the history's toggle. */
export const archivedCount = (records: readonly AgentConversationRecord[]) =>
  records.filter((record) => record.archived).length;

/** The memoized groups of a read, or null until it has an answer. */
export function useConversationGroups(
  read: AgentRead<AgentConversationRecord[]>,
  options: {
    locale: string;
    archived: boolean;
    currentId: string | null;
    untitled: string;
  },
): ConversationGroup[] | null {
  const { locale, archived, currentId, untitled } = options;
  return useMemo(
    () =>
      read.kind === "ready"
        ? conversationGroups(read.value, {
            locale,
            archived,
            currentId,
            untitled,
          })
        : null,
    [read, locale, archived, currentId, untitled],
  );
}

/** What the replies of a conversation served about themselves, in words: what
 * the newest of them ran with, and the tokens all of them used. Each is null
 * where no reply served it. */
export function replyFacts(
  records: readonly AgentTurnRecord[],
  locale: string,
  t: Translate,
): { ranWith: string | null; usage: string | null } {
  const replies = records.filter(
    (record): record is AgentReplyRecord => record.kind === "reply",
  );
  const selection = [...replies]
    .reverse()
    .find((reply) => reply.selection)?.selection;
  const ranWith = selection
    ? [
        selection.provider_display_name || selection.provider,
        selection.model_display_name || selection.model,
        ...(selection.effort ? [effortWords(t, selection.effort)] : []),
      ].join(", ")
    : null;
  const counted = replies.flatMap((reply) =>
    reply.usage ? [reply.usage] : [],
  );
  const number = new Intl.NumberFormat(locale);
  return {
    ranWith: ranWith
      ? t("desktop.agent.ran_with", { selection: ranWith })
      : null,
    usage:
      counted.length > 0
        ? t("desktop.agent.usage", {
            input: number.format(
              counted.reduce((sum, used) => sum + used.input_tokens, 0),
            ),
            output: number.format(
              counted.reduce((sum, used) => sum + used.output_tokens, 0),
            ),
          })
        : null,
  };
}
