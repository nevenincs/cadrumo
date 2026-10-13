import { useCallback, useEffect, useRef, useState } from "react";
import { failureCode } from "../errors";
import { questionnaireFaults } from "./agentClarification";
import type {
  AgentApproval,
  AgentQuestionnaire,
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
} from "./agentSession";
import {
  isLiveStatus,
  replyIdOf,
  type AgentRead,
  type AgentReplyRecord,
  type AgentToolStatus,
  type AgentTurnRecord,
  type AgentViews,
} from "./agentViews";

// A conversation as it is being written: its history, read from the host,
// with the host's stream applied on top. The stream is watched before the
// history is read, and what it sends meanwhile is held and applied after.
//
// cadrumo-agent records a message when its turn ends, so a reply in progress
// is not in the history: its text is what the stream sends, and a new watch
// is replayed it from the run's first frame. That is how a lost stream is
// recovered. The host resumes a stream after its last frame as far as the
// agent's replay reaches; when it cannot, it says `lost`, and the column reads
// the history and what is pending again and watches anew, taking the reply's
// text again from the replay. Text is applied in the order of its sequence,
// and one whose sequence has been applied is dropped.
//
// What the person has sent is shown as sent until the history has it. The
// agent returns no id for a message, and two identical messages have the same
// id in the history, so a message sent here is matched to the history by its
// reply, its words and its order: it takes the next message of that reply
// that the history lists and no earlier one has taken.

/** Prefix of the ids of messages sent here that the history may not have yet.
 * An id of cadrumo-agent's is a hash and never begins so. The second part
 * says where the message belongs in its reply: `start` for the message that
 * began it, `end` for one that continued it. */
const LOCAL = "local:";

type Person = Extract<AgentTurnRecord, { kind: "person" }>;
type Tool = Extract<AgentTurnRecord, { kind: "tool" }>;

const isLocal = (record: AgentTurnRecord): boolean =>
  record.kind === "person" && record.id.startsWith(LOCAL);

/** The messages sent here that `turns` holds, in the order they were sent. */
const localMessages = (turns: readonly AgentTurnRecord[]): Person[] =>
  turns.filter(
    (record): record is Person =>
      record.kind === "person" && record.id.startsWith(LOCAL),
  );

/** A conversation's records so far, and what its reply waits on. */
export type LiveTurns = {
  /** The history's records with the stream's applied, in the order a
   * conversation lists them. */
  turns: AgentTurnRecord[];
  /** The messages the history holds, by reply and id: their text is whole,
   * and the stream's text for them is not added to it. */
  recorded: readonly string[];
  /** The last sequence of text applied, by reply. */
  applied: Readonly<Record<string, number>>;
  /** The questions a reply waits on the person to answer. */
  questionnaires: AgentQuestionnaire[];
  /** The decisions a reply waits on the person to make. */
  approvals: AgentApproval[];
};

/** What a conversation's unfinished reply waits on. */
export type LivePending = Pick<LiveTurns, "questionnaires" | "approvals">;

const NOTHING_PENDING: LivePending = { questionnaires: [], approvals: [] };
/** A conversation with nothing yet. */
export const NO_TURNS: LiveTurns = {
  turns: [],
  recorded: [],
  applied: {},
  ...NOTHING_PENDING,
};

// A request that cannot be answered is not one the reply waits on. The agent
// builds its questionnaires strictly and reads back one it cannot read as no
// question pending; an approval with nothing to decide with it does not park
// at all. What breaks those rules did not come from the agent, and a card for
// it would only be a door that does not open.
const askable = (questionnaire: AgentQuestionnaire) =>
  questionnaireFaults(questionnaire).length === 0;
const decidable = (approval: AgentApproval) => approval.options.length > 0;

/** `pending` without the requests that cannot be answered. */
const answerable = (pending: LivePending): LivePending => ({
  questionnaires: pending.questionnaires.filter(askable),
  approvals: pending.approvals.filter(decidable),
});

const upserted = <T extends { request_id: string }>(
  list: readonly T[],
  item: T,
): T[] => [...list.filter((held) => held.request_id !== item.request_id), item];

/** `live` without the request `requestId`, answered here or elsewhere. A reply
 * that waited only on it goes on. */
export function withoutRequest(live: LiveTurns, requestId: string): LiveTurns {
  const owner = [...live.questionnaires, ...live.approvals].find(
    (held) => held.request_id === requestId,
  )?.reply_id;
  const next: LiveTurns = {
    ...live,
    questionnaires: live.questionnaires.filter(
      (held) => held.request_id !== requestId,
    ),
    approvals: live.approvals.filter((held) => held.request_id !== requestId),
  };
  if (owner === undefined) return next;
  const waiting = [...next.questionnaires, ...next.approvals].some(
    (held) => held.reply_id === owner,
  );
  return waiting ? next : replied(next, owner, "input_required", "running");
}

/** The record of reply `id`, if the records have it. */
export const replyRecord = (
  turns: readonly AgentTurnRecord[],
  id: string,
): AgentReplyRecord | undefined =>
  turns.find(
    (record): record is AgentReplyRecord =>
      record.kind === "reply" && record.id === id,
  );

/** The newest reply of a conversation. */
export const newestReply = (
  turns: readonly AgentTurnRecord[],
): AgentReplyRecord | undefined =>
  [...turns]
    .reverse()
    .find((record): record is AgentReplyRecord => record.kind === "reply");

/** The reply still going, if there is one. */
export const liveReply = (
  turns: readonly AgentTurnRecord[],
): AgentReplyRecord | undefined =>
  [...turns]
    .reverse()
    .find(
      (record): record is AgentReplyRecord =>
        record.kind === "reply" && isLiveStatus(record.status),
    );

/** `turns` with a record for reply `id`, which the stream names before any
 * history does. A reply is running until something says otherwise. */
function withReply(turns: AgentTurnRecord[], id: string): AgentTurnRecord[] {
  return replyRecord(turns, id)
    ? turns
    : [...turns, { kind: "reply", id, status: "running" }];
}

/** `turns` with `record` inserted at `at`. */
const inserted = (
  turns: AgentTurnRecord[],
  at: number,
  record: AgentTurnRecord,
) => [...turns.slice(0, at), record, ...turns.slice(at)];

/** Where a reply's records begin, its tool calls begin, and its record is. */
function placesOf(turns: readonly AgentTurnRecord[], id: string) {
  const own = turns
    .map((record, index) => ({ record, index }))
    .filter(({ record }) => replyIdOf(record) === id);
  const first = own[0]?.index ?? turns.length;
  const marker = own.find(({ record }) => record.kind === "reply")?.index;
  const agent = own.find(({ record }) => record.kind === "agent")?.index;
  const end = marker ?? (own.at(-1)?.index ?? turns.length - 1) + 1;
  return { first, tools: agent ?? end, end };
}

/** `live` with reply `id` in `to` where it was in `from` (any, if `from`
 * is null). */
function replied(
  live: LiveTurns,
  id: string,
  from: AgentReplyRecord["status"] | null,
  to: AgentReplyRecord["status"],
): LiveTurns {
  const turns = withReply(live.turns, id);
  return {
    ...live,
    turns: turns.map((record) =>
      record.kind === "reply" &&
      record.id === id &&
      (from === null || record.status === from)
        ? { ...record, status: to }
        : record,
    ),
  };
}

const RANK: Record<AgentToolStatus, number> = {
  pending: 0,
  in_progress: 1,
  completed: 2,
  failed: 2,
};

/** `live` after one stream event, and whether the history must be read
 * again, and the conversation watched anew, because of it. */
export type StreamStep = {
  live: LiveTurns;
  reread: boolean;
  resubscribe: boolean;
};

const quiet = (live: LiveTurns): StreamStep => ({
  live,
  reread: false,
  resubscribe: false,
});

export function applyStreamEvent(
  live: LiveTurns,
  event: AgentStreamEvent,
): StreamStep {
  switch (event.type) {
    case "reply_started":
      return quiet({
        ...live,
        turns: withReply(live.turns, event.reply_id),
      });
    case "text": {
      const reply = event.reply_id;
      if (event.sequence <= (live.applied[reply] ?? 0)) return quiet(live);
      const applied = { ...live.applied, [reply]: event.sequence };
      // A message the history holds is whole there.
      if (live.recorded.includes(`${reply}\u0000${event.message_id}`))
        return quiet({ ...live, applied });
      const turns = withReply(live.turns, reply);
      const at = turns.findIndex(
        (record) =>
          record.kind === "agent" &&
          record.reply_id === reply &&
          record.id === event.message_id,
      );
      const held = turns[at];
      return quiet({
        ...live,
        applied,
        turns:
          held?.kind === "agent"
            ? turns.map((record, index) =>
                index === at
                  ? { ...held, text: held.text + event.delta }
                  : record,
              )
            : inserted(turns, placesOf(turns, reply).end, {
                kind: "agent",
                id: event.message_id,
                reply_id: reply,
                text: event.delta,
              }),
      });
    }
    case "tool": {
      const reply = event.reply_id;
      const turns = withReply(live.turns, reply);
      const call: Tool = { kind: "tool", reply_id: reply, ...event.tool };
      const at = turns.findIndex(
        (record) =>
          record.kind === "tool" &&
          record.reply_id === reply &&
          record.id === call.id,
      );
      if (at >= 0) {
        const held = turns[at];
        // A call does not go back to an earlier state.
        if (held?.kind === "tool" && RANK[call.status] < RANK[held.status])
          return quiet(live);
        return quiet({
          ...live,
          turns: turns.map((record, index) => (index === at ? call : record)),
        });
      }
      return quiet({
        ...live,
        turns: inserted(turns, placesOf(turns, reply).tools, call),
      });
    }
    case "questions":
      if (!askable(event.questionnaire)) return quiet(live);
      return quiet(
        replied(
          {
            ...live,
            questionnaires: upserted(live.questionnaires, event.questionnaire),
          },
          event.reply_id,
          "running",
          "input_required",
        ),
      );
    case "approval":
      if (!decidable(event.approval)) return quiet(live);
      return quiet(
        replied(
          { ...live, approvals: upserted(live.approvals, event.approval) },
          event.reply_id,
          "running",
          "input_required",
        ),
      );
    case "resolved":
      return quiet(withoutRequest(live, event.request_id));
    case "settled": {
      // A finished reply waits on nothing.
      const turns = withReply(live.turns, event.reply_id).map((record) =>
        record.kind === "reply" && record.id === event.reply_id
          ? {
              ...record,
              status: event.status,
              provider_condition: event.provider_condition ?? null,
              failure_reason: event.failure_reason ?? null,
            }
          : record,
      );
      // What the agent recorded of the reply, its final text and its
      // account, is in the history now.
      return {
        live: {
          ...live,
          turns,
          questionnaires: live.questionnaires.filter(
            (held) => held.reply_id !== event.reply_id,
          ),
          approvals: live.approvals.filter(
            (held) => held.reply_id !== event.reply_id,
          ),
        },
        reread: true,
        resubscribe: false,
      };
    }
    case "lost":
      // The reply's text so far is taken again from the replay.
      return {
        live: { ...live, applied: {} },
        reread: true,
        resubscribe: true,
      };
  }
}

/** The person's own message: a send, which began `reply_id`, or an answer
 * given in words, which went on with it. */
export type PersonSent = {
  reply_id: string;
  text: string;
  /** `start` for a message that began the reply, `end` for one that continued
   * it. */
  at: "start" | "end";
};

/** `live` with the person's own message. */
export function withSent(
  live: LiveTurns,
  sent: PersonSent,
  now: Date,
): LiveTurns {
  const turns = withReply(live.turns, sent.reply_id);
  const sentBefore = turns.filter(
    (record) => isLocal(record) && replyIdOf(record) === sent.reply_id,
  ).length;
  const message: Person = {
    kind: "person",
    id: `${LOCAL}${sent.at}:${sent.reply_id}:${sentBefore}`,
    reply_id: sent.reply_id,
    text: sent.text,
    sent_at: now.toISOString(),
  };
  const places = placesOf(turns, sent.reply_id);
  return {
    ...live,
    turns: inserted(
      turns,
      sent.at === "start" ? places.first : places.end,
      message,
    ),
  };
}

/** `live` with the history read again: the history's records, with what the
 * person sent that it does not have yet, and what the reply waits on. */
export function withHistory(
  live: LiveTurns,
  records: AgentTurnRecord[],
  pending: LivePending,
): LiveTurns {
  let turns = [...records];
  let taken = new Set<number>();
  for (const sent of localMessages(live.turns)) {
    const at = turns.findIndex(
      (record, index) =>
        !taken.has(index) &&
        record.kind === "person" &&
        !isLocal(record) &&
        record.reply_id === sent.reply_id &&
        record.text === sent.text,
    );
    if (at >= 0) {
      taken.add(at);
      continue;
    }
    turns = withReply(turns, sent.reply_id);
    const places = placesOf(turns, sent.reply_id);
    const start = sent.id.startsWith(`${LOCAL}start:`);
    turns = inserted(turns, start ? places.first : places.end, sent);
    // Inserting before a record moves the indexes of those taken.
    const where = start ? places.first : places.end;
    taken = new Set(
      [...taken].map((index) => (index >= where ? index + 1 : index)),
    );
  }
  return {
    ...live,
    ...answerable(pending),
    turns,
    recorded: records.flatMap((record) =>
      record.kind === "agent" ? [`${record.reply_id}\u0000${record.id}`] : [],
    ),
  };
}

export type LiveConversation = {
  /** The records, read and streamed. */
  read: AgentRead<AgentTurnRecord[]>;
  /** The reply still being written that can be stopped, by its handle. */
  open: string | null;
  /** A reply is still going: being written, waiting for the person,
   * stopping. */
  working: boolean;
  /** The questions the conversation's reply waits on. */
  questionnaires: readonly AgentQuestionnaire[];
  /** The decisions the conversation's reply waits on. */
  approvals: readonly AgentApproval[];
  /** Shows the person's message that a send, or an answer in words, sent,
   * until the history has it. */
  sent(message: PersonSent): void;
  /** Drops a question or approval the person has answered. */
  resolved(requestId: string): void;
  /** Marks a reply the agent took the stop of as stopping, until the stream
   * says how it ended. */
  stopping(replyId: string): void;
  /** Settles once the conversation is being watched. */
  watch(conversationId: string): Promise<void>;
};

type Waiter = { id: string; resolve: () => void; reject: () => void };

/** How long to wait before watching a conversation anew, after `losses`
 * streams in a row that were lost with nothing between them: at once, then
 * after a second, doubling to half a minute. */
export const resubscribeDelay = (losses: number): number =>
  losses <= 1 ? 0 : Math.min(30_000, 1_000 * 2 ** (losses - 2));

/**
 * The conversation `conversationId` while `enabled`: read from `views`, and
 * kept up to date from `session` where the host offers one. `onSettled` is
 * told whenever a reply finishes.
 */
export function useLiveConversation({
  views,
  session,
  conversationId,
  enabled,
  onSettled,
}: {
  views: AgentViews | undefined;
  session: AgentSession | undefined;
  conversationId: string | null;
  enabled: boolean;
  onSettled?: () => void;
}): LiveConversation {
  const key = enabled && views ? conversationId : null;
  const [state, setState] = useState<{
    for: string | null;
    live: LiveTurns | null;
    failed: string | null;
  }>({ for: null, live: null, failed: null });
  const settled = useRef(onSettled);
  settled.current = onSettled;
  // How the current watch takes a change of the person's making, and which
  // conversation it watches.
  const take = useRef<
    ((change: (live: LiveTurns) => LiveTurns) => void) | null
  >(null);
  const watching = useRef<string | null>(null);
  const waiters = useRef<Waiter[]>([]);

  useEffect(() => {
    if (key === null || !views) return;
    const id = key;
    const source = views;
    let alive = true;
    let current: LiveTurns | null = null;
    // Events that arrive while the history is read, applied once it is.
    let held: AgentStreamEvent[] | null = null;
    // The person's own changes while the history is read, made after it.
    let changes: ((live: LiveTurns) => LiveTurns)[] = [];
    let stop: (() => void) | null = null;
    let timer: number | undefined;
    // Reads made, so that an answer to an earlier one is dropped.
    let reads = 0;
    // Streams lost in a row, with no progress between them.
    let losses = 0;

    const show = (live: LiveTurns) => {
      current = live;
      setState({ for: id, live, failed: null });
    };
    // What a step asks of the watch.
    const follow = (step: { reread: boolean; resubscribe: boolean }) => {
      if (step.resubscribe) subscribe(false);
      else if (step.reread) load();
    };
    const apply = (live: LiveTurns, events: AgentStreamEvent[]) => {
      let reread = false;
      let resubscribe = false;
      for (const event of events) {
        const step = applyStreamEvent(live, event);
        live = step.live;
        reread ||= step.reread;
        resubscribe ||= step.resubscribe;
        if (event.type === "settled") settled.current?.();
        if (event.type === "lost") losses += 1;
        else if (event.type !== "reply_started") losses = 0;
      }
      return { live, reread, resubscribe };
    };
    function load() {
      held ??= [];
      const mine = ++reads;
      Promise.all([
        source.history(id),
        session ? session.pending(id) : NOTHING_PENDING,
      ]).then(
        ([records, pending]) => {
          if (!alive || mine !== reads) return;
          const events = held ?? [];
          held = null;
          let live = withHistory(current ?? NO_TURNS, records, pending);
          for (const change of changes) live = change(live);
          changes = [];
          const step = apply(live, events);
          show(step.live);
          follow(step);
        },
        (error: unknown) => {
          if (!alive || mine !== reads) return;
          held = null;
          setState({ for: id, live: current, failed: failureCode(error) });
        },
      );
    }
    // Watches the conversation, then reads it: what the stream sends
    // meanwhile is held. A watch that was lost is made again, at once the
    // first time and after a growing wait while it keeps being lost.
    function subscribe(first: boolean) {
      if (!session) {
        load();
        return;
      }
      stop?.();
      stop = null;
      window.clearTimeout(timer);
      held ??= [];
      const attach = () => {
        session.observe(id, onEvent).then(
          (unsubscribe) => {
            if (!alive) {
              unsubscribe();
              return;
            }
            stop = unsubscribe;
            if (first) ready();
            load();
          },
          (error: unknown) => {
            if (!alive) return;
            if (first) {
              held = null;
              setState({ for: id, live: null, failed: failureCode(error) });
            } else {
              losses += 1;
              timer = window.setTimeout(attach, resubscribeDelay(losses));
            }
          },
        );
      };
      if (first) attach();
      else timer = window.setTimeout(attach, resubscribeDelay(losses));
    }
    function onEvent(event: AgentStreamEvent) {
      if (!alive) return;
      if (held || !current) {
        held?.push(event);
        return;
      }
      const step = apply(current, [event]);
      show(step.live);
      follow(step);
    }
    take.current = (change) => {
      if (!alive) return;
      if (held || !current) changes.push(change);
      else show(change(current));
    };
    // A wait for another conversation will not be answered by this watch.
    const others = waiters.current.filter((waiter) => waiter.id !== id);
    waiters.current = waiters.current.filter((waiter) => waiter.id === id);
    for (const waiter of others) waiter.reject();
    function ready() {
      watching.current = id;
      const mine = waiters.current;
      waiters.current = [];
      for (const waiter of mine) waiter.resolve();
    }

    subscribe(true);

    return () => {
      alive = false;
      window.clearTimeout(timer);
      stop?.();
      take.current = null;
      if (watching.current === id) watching.current = null;
    };
  }, [key, views, session]);

  const sent = useCallback(
    (message: PersonSent) =>
      take.current?.((live) => withSent(live, message, new Date())),
    [],
  );
  const resolved = useCallback(
    (requestId: string) =>
      take.current?.((live) => withoutRequest(live, requestId)),
    [],
  );
  const stopping = useCallback(
    (replyId: string) =>
      take.current?.((live) => {
        const reply = replyRecord(live.turns, replyId);
        // A reply that has ended by then is not stopping.
        return reply && isLiveStatus(reply.status)
          ? replied(live, replyId, null, "cancelling")
          : live;
      }),
    [],
  );
  const watch = useCallback(
    (id: string) =>
      watching.current === id
        ? Promise.resolve()
        : new Promise<void>((resolve, reject) => {
            waiters.current.push({
              id,
              resolve,
              reject: () => reject(new Error("agent_conversation_closed")),
            });
          }),
    [],
  );

  const mine = key !== null && state.for === key;
  const live = mine ? state.live : null;
  const read: AgentRead<AgentTurnRecord[]> =
    key === null
      ? { kind: "unavailable" }
      : mine && state.failed !== null
        ? { kind: "failed", code: state.failed }
        : live
          ? { kind: "ready", value: live.turns }
          : { kind: "loading" };
  const going = live ? liveReply(live.turns) : undefined;
  return {
    read,
    // A reply that is already stopping cannot be stopped again.
    open: going && going.status !== "cancelling" ? going.id : null,
    working: going !== undefined,
    questionnaires: live?.questionnaires ?? NOTHING_PENDING.questionnaires,
    approvals: live?.approvals ?? NOTHING_PENDING.approvals,
    sent,
    resolved,
    stopping,
    watch,
  };
}

/** Where the agent service is, as the host reports it while `enabled`, or
 * null until it has said. */
export function useAgentStatus(
  session: AgentSession | undefined,
  enabled: boolean,
): AgentServiceStatus | null {
  const [state, setState] = useState<{
    for: AgentSession | null;
    status: AgentServiceStatus | null;
  }>({ for: null, status: null });
  useEffect(() => {
    if (!session || !enabled) return;
    let alive = true;
    let heard = false;
    let stop: (() => void) | null = null;
    const hear = (status: AgentServiceStatus) => {
      heard = true;
      if (alive) setState({ for: session, status });
    };
    session.observeStatus(hear).then(
      (unsubscribe) => {
        if (alive) stop = unsubscribe;
        else unsubscribe();
      },
      () => undefined,
    );
    // The first answer, unless the watch has already given a newer one. A
    // status that cannot be read is not known, and nothing says otherwise.
    session.status().then(
      (status) => {
        if (alive && !heard) setState({ for: session, status });
      },
      () => undefined,
    );
    return () => {
      alive = false;
      stop?.();
    };
  }, [session, enabled]);
  return session && enabled && state.for === session ? state.status : null;
}
