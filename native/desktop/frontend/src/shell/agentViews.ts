import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AgentReplyState,
  ConversationGroup,
  TranscriptItem,
} from "@/components/agent/types";
import { failureCode } from "../errors";
import { effortWords } from "./agentCatalog";
import { sentFiles } from "./agentDocuments";
import type {
  AgentApproval,
  AgentQuestionnaire,
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
 * tool's name), its `kind` and its `status`. The stream carries nothing of
 * its input or result; the history may say more in `details`. */
export type AgentToolCall = {
  id: string;
  title: string;
  tool_kind: AgentToolKind;
  status: AgentToolStatus;
  /** What the history says of the call, as the agent worded it and the
   * host cut it: its input, its result and the places it touched. Absent
   * while the call is only streamed. */
  details?: string[];
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

/** A document stored for a conversation, as cadrumo-agent lists the files
 * of that conversation's own storage: the storage is the record, so a
 * document is its name, and the digest tells one version from another. The
 * conversation's messages name it, the agent reads it where it is stored,
 * and nothing is uploaded again. */
export type AgentDocumentRecord = {
  /** A plain file name, unique in the directory. */
  name: string;
  size_bytes: number;
  /** When the file last changed, as an ISO instant. */
  modified_at: string;
  /** SHA-256 of its bytes, as 64 lowercase hex digits. */
  sha256: string;
  /** Its type, where the agent can tell; null where it cannot. */
  media_type: string | null;
};

/** One page of the stored documents, ordered by name. */
export type AgentDocumentPage = {
  documents: AgentDocumentRecord[];
  /** The name the next page starts after; null on the last page. */
  next_after: string | null;
};

/** Which page to read: the documents after a name, whose names hold `q`,
 * ignoring case. */
export type AgentDocumentsQuery = {
  /** The conversation, by its first run's id; one reserved and not sent yet
   * has its own storage too. */
  conversation_id: string;
  after?: string;
  q?: string;
};

/** A stored document a message names, as the history echoes it. */
export type AgentDocumentReference = {
  name: string;
  sha256: string | null;
  media_type: string | null;
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
      /** The stored documents the message named, in the order it named
       * them; absent where none. */
      attachments?: AgentDocumentReference[];
      /** The skills the message loaded, by name; absent or empty where
       * none. */
      skills?: string[];
    }
  | {
      kind: "agent";
      /** cadrumo-agent's `message_id`: the id the stream's text names. */
      id: string;
      reply_id: string;
      text: string;
    }
  | ({ kind: "tool"; reply_id: string } & AgentToolCall)
  /** What the agent thought on the way, by the stream's `message_id`. The
   * history lists none: only the stream has it, and the column keeps it
   * beside what it reads for as long as it watches. */
  | { kind: "thought"; id: string; reply_id: string; text: string }
  | AgentReplyRecord;

/** The reply a record belongs to. */
export const replyIdOf = (record: AgentTurnRecord): string =>
  record.kind === "reply" ? record.id : record.reply_id;

export type AgentSnapshot = {
  history: AgentTurnRecord[];
  pending: { questionnaires: AgentQuestionnaire[]; approvals: AgentApproval[] };
};

/** The agent views a host offers. Each read is refused while nobody is
 * signed in, as the profile's own views are. */
export interface AgentViews {
  /** Every conversation of the signed-in profile, archived ones included. */
  conversations(): Promise<AgentConversationRecord[]>;
  /** The records of one conversation, oldest first. */
  history(conversationId: string): Promise<AgentTurnRecord[]>;
  /** A host can serve history and outstanding requests from one read. */
  snapshot?(conversationId: string): Promise<AgentSnapshot>;
  /** One page of the documents stored for a conversation. Refused while
   * its storage cannot be read. */
  documents?(query: AgentDocumentsQuery): Promise<AgentDocumentPage>;
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

/**
 * A read whose answer is kept for `owner` and shown while it is asked again,
 * so it is loading only the first time. It is asked whenever `enabled` and
 * either `ask` changes or it has no answer yet; leaving it disabled keeps the
 * answer for when it is enabled again. A re-read that fails keeps the answer
 * it would have replaced. An answer for an earlier owner is dropped, and
 * `put` sets the answer from a read made elsewhere, without asking again.
 */
export function useCachedRead<T>(
  read: (() => Promise<T>) | null,
  owner: string | null,
  enabled: boolean,
  ask: number,
): { read: AgentRead<T>; put: (value: T) => void } {
  const [state, setState] = useState<{
    owner: string | null;
    read: AgentRead<T>;
  }>({ owner, read: { kind: "loading" } });
  const asked = useRef<{ owner: string | null; ask: number } | null>(null);
  if (state.owner !== owner) setState({ owner, read: { kind: "loading" } });
  useEffect(() => {
    if (!read || !enabled) return;
    const last = asked.current;
    if (last && last.owner === owner && last.ask === ask) return;
    asked.current = { owner, ask };
    let current = true;
    let settled = false;
    read().then(
      (value) => {
        settled = true;
        if (current) setState({ owner, read: { kind: "ready", value } });
      },
      (error: unknown) => {
        settled = true;
        if (current)
          setState((held) =>
            held.owner === owner && held.read.kind === "ready"
              ? held
              : { owner, read: { kind: "failed", code: failureCode(error) } },
          );
      },
    );
    return () => {
      // A read cut short is asked again when it can be.
      if (!settled) asked.current = null;
      current = false;
    };
  }, [read, owner, enabled, ask]);
  const put = useCallback(
    (value: T) => setState({ owner, read: { kind: "ready", value } }),
    [owner],
  );
  if (!read) return { read: { kind: "unavailable" }, put };
  return {
    read: state.owner === owner ? state.read : { kind: "loading" },
    put,
  };
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

/** Why a reply failed, in localized words from its typed provider condition.
 * The agent's failure prose remains for diagnostics and is not shown here. */
function failureWords(
  t: Translate,
  reply: AgentReplyRecord,
): string | undefined {
  return reply.provider_condition
    ? conditionWords(t, reply.provider_condition)
    : undefined;
}

/** When a message was sent, in words: the time today, else the day too. */
const timeFormats = new Map<string, Intl.DateTimeFormat>();

function sentLabel(locale: string, at: Date, now: Date): string | undefined {
  if (!Number.isFinite(at.getTime())) return undefined;
  const sameDay = dayStart(at) === dayStart(now);
  const key = `${locale}:${sameDay}`;
  let format = timeFormats.get(key);
  if (!format) {
    format = new Intl.DateTimeFormat(locale, {
      ...(sameDay ? {} : { day: "numeric", month: "short" }),
      hour: "numeric",
      minute: "2-digit",
    });
    timeFormats.set(key, format);
  }
  return format.format(at);
}

type TranscriptProjectionEntry = {
  item: TranscriptItem;
  reply: AgentReplyRecord | undefined;
  last: boolean;
  thinking: string | undefined;
};

type TranscriptProjectionCache = {
  locale?: string;
  t?: Translate;
  day?: number;
  entries: Map<AgentTurnRecord, TranscriptProjectionEntry>;
};

/** Retains unchanged rows only for this transcript's latest projection. */
export function createTranscriptProjection() {
  const cache: TranscriptProjectionCache = { entries: new Map() };
  return (
    records: readonly AgentTurnRecord[],
    locale: string,
    t: Translate,
    now = new Date(),
  ) => transcriptItems(records, locale, t, now, cache);
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
  cache?: TranscriptProjectionCache,
): TranscriptItem[] {
  const replies = new Map<string, AgentReplyRecord>();
  const lastAgent = new Map<string, number>();
  const thoughts = new Map<string, string[]>();
  records.forEach((record, index) => {
    if (record.kind === "reply") replies.set(record.id, record);
    else if (record.kind === "agent") lastAgent.set(record.reply_id, index);
    else if (record.kind === "thought" && record.text.trim()) {
      const held = thoughts.get(record.reply_id);
      if (held) held.push(record.text);
      else thoughts.set(record.reply_id, [record.text]);
    }
  });
  // A reply's thoughts go with the item its state is drawn on.
  const thinking = (reply: string) => {
    const thought = thoughts.get(reply);
    return thought ? { thinking: thought.join("\n\n") } : {};
  };
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
      ...(state === "failed" && reply.provider_condition === "unauthenticated"
        ? { failureAction: "provider_settings" as const }
        : {}),
      ...(reply.status === "input_required"
        ? { waitingOnPerson: true as const }
        : {}),
    };
  };
  const items: TranscriptItem[] = [];
  const previous =
    cache?.locale === locale && cache.t === t && cache.day === dayStart(now)
      ? cache.entries
      : undefined;
  const entries = new Map<AgentTurnRecord, TranscriptProjectionEntry>();
  records.forEach((record, index) => {
    if (
      record.kind === "thought" ||
      (record.kind === "reply" && lastAgent.has(record.id))
    )
      return;
    const id =
      record.kind === "reply"
        ? unique(`reply:${record.id}`)
        : unique(`${record.kind}:${record.reply_id}:${record.id}`);
    const reply =
      record.kind === "agent" ? replies.get(record.reply_id) : undefined;
    const last =
      record.kind === "agent" && lastAgent.get(record.reply_id) === index;
    const thought =
      record.kind === "agent" && last
        ? thinking(record.reply_id).thinking
        : record.kind === "reply"
          ? thinking(record.id).thinking
          : undefined;
    const before = previous?.get(record);
    if (
      before &&
      before.item.id === id &&
      before.reply === reply &&
      before.last === last &&
      before.thinking === thought
    ) {
      items.push(before.item);
      entries.set(record, before);
      return;
    }
    let item: TranscriptItem | undefined;
    switch (record.kind) {
      case "person": {
        const sentAtLabel = record.sent_at
          ? sentLabel(locale, new Date(record.sent_at), now)
          : undefined;
        item = {
          kind: "person",
          id,
          text: record.text,
          ...(record.attachments?.length
            ? { files: sentFiles(record.attachments) }
            : {}),
          ...(record.skills?.length ? { skills: record.skills } : {}),
          ...(sentAtLabel ? { sentAtLabel } : {}),
        };
        break;
      }
      case "tool":
        item = {
          kind: "tool",
          id,
          label: record.title,
          state: record.status,
          detail: toolKindWords(t, record.tool_kind),
          ...(record.details?.length ? { internals: record.details } : {}),
        };
        break;
      case "agent":
        item = {
          kind: "agent",
          id,
          text: record.text,
          ...(last && reply ? drawn(reply) : { state: "complete" as const }),
          ...(thought ? { thinking: thought } : {}),
        };
        break;
      case "reply": {
        const state = drawn(record);
        if (state.state === "complete") break;
        item = {
          kind: "agent",
          id,
          text: "",
          ...state,
          ...(thought ? { thinking: thought } : {}),
        };
      }
    }
    if (item) {
      items.push(item);
      entries.set(record, { item, reply, last, thinking: thought });
    }
  });
  if (cache) Object.assign(cache, { locale, t, day: dayStart(now), entries });
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

/** What the newest reply of a conversation that says so ran with; undefined
 * where none says. */
export function newestRanWith(
  records: readonly AgentTurnRecord[],
): AgentRanWith | undefined {
  for (let index = records.length - 1; index >= 0; index -= 1) {
    const record = records[index];
    if (record?.kind === "reply" && record.selection) return record.selection;
  }
  return undefined;
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
  const selection = newestRanWith(records);
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
