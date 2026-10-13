import { useCallback, useEffect, useRef, useState } from "react";
import { failureCode } from "../errors";
import type {
  AgentSendResult,
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
} from "./agentSession";
import type { AgentRead, AgentTurnRecord, AgentViews } from "./agentViews";

// A conversation as it is being written: its history, read from the host,
// with the host's stream applied on top. The stream is watched before the
// history is read, and what it sends meanwhile is held and applied after, so
// nothing between the two is lost. Where the stream shows that something was
// missed, the history is read again: it holds every turn as far as it has
// gone, under the ids the stream uses.

/** A conversation's turns so far, and the replies they belong to. */
export type LiveTurns = {
  turns: AgentTurnRecord[];
  /** The ids of each reply's agent and tool turns, in order, by the
   * reply's handle. */
  replies: Readonly<Record<string, readonly string[]>>;
  /** The reply still being written, where its handle is known. */
  open: string | null;
};

const NO_TURNS: LiveTurns = { turns: [], replies: {}, open: null };

/** `live` after one stream event, and whether the history must be read
 * again because the event shows that something was missed. */
export type StreamStep = { live: LiveTurns; reread: boolean };

const joined = (
  replies: LiveTurns["replies"],
  replyId: string,
  turnId?: string,
): LiveTurns["replies"] => {
  const held = replies[replyId] ?? [];
  if (turnId === undefined || held.includes(turnId))
    return replyId in replies ? replies : { ...replies, [replyId]: held };
  return { ...replies, [replyId]: [...held, turnId] };
};

const replaced = (
  turns: readonly AgentTurnRecord[],
  at: number,
  turn: AgentTurnRecord,
) => turns.map((held, index) => (index === at ? turn : held));

/** `turns` with the reply's agent turns written so far finished: a reply
 * that goes on to a tool or to new text has done writing them. */
const finished = (
  turns: readonly AgentTurnRecord[],
  ids: readonly string[],
): AgentTurnRecord[] =>
  turns.map((turn) =>
    turn.kind === "agent" && turn.state === "working" && ids.includes(turn.id)
      ? { ...turn, state: "complete" }
      : turn,
  );

export function applyStreamEvent(
  live: LiveTurns,
  event: AgentStreamEvent,
): StreamStep {
  switch (event.type) {
    case "reply_started":
      return {
        live: {
          ...live,
          replies: joined(live.replies, event.reply_id),
          open: event.reply_id,
        },
        reread: false,
      };
    case "text": {
      const at = live.turns.findIndex(
        (turn) => turn.kind === "agent" && turn.id === event.turn_id,
      );
      let turns: AgentTurnRecord[];
      if (at < 0) {
        // A turn's first text starts at its beginning; anything else
        // means its start was missed.
        if (event.offset !== 0) return { live, reread: true };
        turns = [
          ...finished(live.turns, live.replies[event.reply_id] ?? []),
          {
            kind: "agent",
            id: event.turn_id,
            text: event.delta,
            state: "working",
          },
        ];
      } else {
        const turn = live.turns[at] as Extract<
          AgentTurnRecord,
          { kind: "agent" }
        >;
        const held = turn.text.length;
        if (event.offset > held) return { live, reread: true };
        // Text already held is not added twice.
        if (event.offset + event.delta.length <= held)
          return { live, reread: false };
        turns = replaced(live.turns, at, {
          ...turn,
          text: turn.text + event.delta.slice(held - event.offset),
        });
      }
      return {
        live: {
          turns,
          replies: joined(live.replies, event.reply_id, event.turn_id),
          open: event.reply_id,
        },
        reread: false,
      };
    }
    case "tool": {
      const at = live.turns.findIndex(
        (turn) => turn.kind === "tool" && turn.id === event.tool.id,
      );
      return {
        live: {
          turns:
            at < 0
              ? [
                  ...finished(live.turns, live.replies[event.reply_id] ?? []),
                  event.tool,
                ]
              : replaced(live.turns, at, event.tool),
          replies: joined(live.replies, event.reply_id, event.tool.id),
          open: event.reply_id,
        },
        reread: false,
      };
    }
    case "settled": {
      const ids = live.replies[event.reply_id] ?? [];
      const agentIds = ids.filter((id) =>
        live.turns.some((turn) => turn.kind === "agent" && turn.id === id),
      );
      const last = agentIds.at(-1);
      const open = live.open === event.reply_id ? null : live.open;
      // A reply that ended before writing anything is kept by the history
      // alone, with why it ended.
      if (last === undefined) return { live: { ...live, open }, reread: true };
      const turns = live.turns.map((turn): AgentTurnRecord => {
        if (turn.kind !== "agent" || !agentIds.includes(turn.id)) return turn;
        if (turn.id !== last)
          return turn.state === "working"
            ? { ...turn, state: "complete" }
            : turn;
        return {
          ...turn,
          state: event.state,
          ...(event.failure_reason
            ? { failure_reason: event.failure_reason }
            : {}),
        };
      });
      return { live: { ...live, turns, open }, reread: false };
    }
    case "lost":
      return { live, reread: true };
  }
}

/** `live` with the person's own message, as the send that started a reply
 * answered it. */
function withSent(live: LiveTurns, sent: AgentSendResult): LiveTurns {
  const turn = sent.person_turn;
  return {
    turns: live.turns.some((held) => held.id === turn.id)
      ? live.turns
      : [...live.turns, turn],
    replies: joined(live.replies, sent.reply_id),
    open: sent.reply_id,
  };
}

/** `live` with the history read again: the history's turns, and the open
 * reply closed when the history shows it has finished. */
function withHistory(live: LiveTurns, records: AgentTurnRecord[]): LiveTurns {
  const ids = live.open === null ? [] : (live.replies[live.open] ?? []);
  const agentTurns = records.filter(
    (turn) => turn.kind === "agent" && ids.includes(turn.id),
  );
  const finished =
    agentTurns.length > 0 &&
    agentTurns.every(
      (turn) => turn.kind === "agent" && turn.state !== "working",
    );
  return { ...live, turns: records, open: finished ? null : live.open };
}

export type LiveConversation = {
  /** The turns, read and streamed. */
  read: AgentRead<AgentTurnRecord[]>;
  /** The reply being written, by its handle, where it is known. */
  open: string | null;
  /** A reply is still being written, whether or not its handle is known. */
  working: boolean;
  /** Adds the person's message that a send answered with. */
  sent(result: AgentSendResult): void;
  /** Settles once the conversation is being watched, so that nothing a
   * send then starts is missed. */
  watch(conversationId: string): Promise<void>;
};

type Waiter = { id: string; resolve: () => void; reject: () => void };

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
  // How the current watch takes a send's answer, and which conversation it
  // watches.
  const take = useRef<((sent: AgentSendResult) => void) | null>(null);
  const watching = useRef<string | null>(null);
  const waiters = useRef<Waiter[]>([]);

  useEffect(() => {
    if (key === null || !views) return;
    const id = key;
    let alive = true;
    let current: LiveTurns | null = null;
    // Events that arrive while the history is read, applied once it is.
    let held: AgentStreamEvent[] | null = null;
    let sends: AgentSendResult[] = [];
    let stop: (() => void) | null = null;

    const show = (live: LiveTurns) => {
      current = live;
      setState({ for: id, live, failed: null });
    };
    const read = () => {
      held = [];
      views.history(id).then(
        (records) => {
          if (!alive) return;
          const events = held ?? [];
          held = null;
          let live = withHistory(current ?? NO_TURNS, records);
          for (const sent of sends) live = withSent(live, sent);
          sends = [];
          for (const event of events) {
            const step = applyStreamEvent(live, event);
            live = step.live;
            if (step.reread) {
              show(live);
              read();
              return;
            }
          }
          show(live);
        },
        (error: unknown) => {
          if (!alive) return;
          held = null;
          setState({ for: id, live: current, failed: failureCode(error) });
        },
      );
    };
    const onEvent = (event: AgentStreamEvent) => {
      if (!alive) return;
      if (held || !current) {
        held?.push(event);
        return;
      }
      const step = applyStreamEvent(current, event);
      show(step.live);
      if (step.reread) read();
      if (event.type === "settled") settled.current?.();
    };
    take.current = (sent) => {
      if (!alive) return;
      if (held || !current) sends.push(sent);
      else show(withSent(current, sent));
    };
    // A wait for another conversation will not be answered by this watch.
    const others = waiters.current.filter((waiter) => waiter.id !== id);
    waiters.current = waiters.current.filter((waiter) => waiter.id === id);
    for (const waiter of others) waiter.reject();
    const ready = () => {
      watching.current = id;
      const mine = waiters.current;
      waiters.current = [];
      for (const waiter of mine) waiter.resolve();
    };

    if (session)
      session.observe(id, onEvent).then(
        (unsubscribe) => {
          if (!alive) {
            unsubscribe();
            return;
          }
          stop = unsubscribe;
          ready();
          read();
        },
        (error: unknown) => {
          if (alive)
            setState({ for: id, live: null, failed: failureCode(error) });
        },
      );
    else read();

    return () => {
      alive = false;
      stop?.();
      take.current = null;
      if (watching.current === id) watching.current = null;
    };
  }, [key, views, session]);

  const sent = useCallback((result: AgentSendResult) => {
    take.current?.(result);
  }, []);
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
  return {
    read,
    open: live?.open ?? null,
    working:
      live !== null &&
      (live.open !== null ||
        live.turns.some(
          (turn) => turn.kind === "agent" && turn.state === "working",
        )),
    sent,
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
