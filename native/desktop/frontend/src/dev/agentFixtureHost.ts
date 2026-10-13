import type {
  AgentConsentGrant,
  AgentProviderRecord,
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
} from "../shell/agentSession";
import type {
  AgentConversationRecord,
  AgentTurnRecord,
  AgentViews,
} from "../shell/agentViews";
import {
  FIXTURE_CONVERSATIONS,
  FIXTURE_DOCUMENTS,
  FIXTURE_HISTORY,
} from "./fixtures/agent";

// The scenario host's agent: its views over the fixture conversations, and
// a session that answers every message with a made-up reply, streamed as
// the desktop host would stream one. Nothing is sent anywhere; the reply
// only repeats the message. Its provider and models are named as fixtures.

/** How the fixture stream behaves: in order with one text sent twice, or
 * with one text never sent, which only reading the history recovers. */
export type FixtureStream = "steady" | "gap";

/** Between one streamed event and the next, in milliseconds. */
const STEP_MS = 40;
/** The length of each streamed piece of text. */
const PIECE = 8;

const PROVIDERS: AgentProviderRecord[] = [
  {
    id: "fixture-provider",
    name: "Fixture provider",
    selectable: true,
    models: [
      {
        id: "fixture-large",
        display_name: "Fixture Large",
        created_at: "2026-01-01T00:00:00Z",
        max_input_tokens: 200_000,
        max_output_tokens: 32_000,
        efforts: ["low", "medium", "high"],
        default_effort: "medium",
      },
      {
        id: "fixture-small",
        display_name: "Fixture Small",
        created_at: "2025-06-01T00:00:00Z",
        efforts: [],
      },
    ],
  },
  {
    id: "fixture-local",
    name: "Fixture local",
    selectable: false,
    unavailable_reason: "agent_service_absent",
    models: [],
  },
];

const coded = (code: string) => Object.assign(new Error(code), { code });

const pieces = (text: string) => {
  const out: { offset: number; delta: string }[] = [];
  for (let offset = 0; offset < text.length; offset += PIECE)
    out.push({ offset, delta: text.slice(offset, offset + PIECE) });
  return out;
};

export function fixtureAgent({
  say,
  wait,
  readable,
  empty,
  stream,
  refused,
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in that the conversations belong to. */
  readable: () => boolean;
  /** The profile has no conversations yet. */
  empty: boolean;
  stream: FixtureStream;
  /** Thrown by a read while nobody is signed in. */
  refused: () => unknown;
}): { agent: AgentViews; session: AgentSession } {
  // This run's conversations, which a send adds to.
  const conversations: AgentConversationRecord[] = empty
    ? []
    : FIXTURE_CONVERSATIONS.map((record) => ({ ...record }));
  const turns: Record<string, AgentTurnRecord[]> = empty
    ? {}
    : Object.fromEntries(
        Object.entries(FIXTURE_HISTORY).map(([id, list]) => [id, [...list]]),
      );
  const grants: AgentConsentGrant[] = [];
  const listeners = new Map<string, Set<(event: AgentStreamEvent) => void>>();
  const replies = new Map<
    string,
    { conversationId: string; timers: number[]; ids: string[] }
  >();
  let next = 0;
  const id = (prefix: string) => `${prefix}-${++next}`;

  const emit = (conversationId: string, event: AgentStreamEvent) => {
    for (const listener of listeners.get(conversationId) ?? []) listener(event);
  };
  const turnsOf = (conversationId: string) => (turns[conversationId] ??= []);
  const put = (conversationId: string, turn: AgentTurnRecord) => {
    const list = turnsOf(conversationId);
    const at = list.findIndex((held) => held.id === turn.id);
    if (at < 0) list.push(turn);
    else list[at] = turn;
  };
  const check = async () => {
    await wait();
    if (!readable()) throw refused();
  };

  const status = (): AgentServiceStatus =>
    readable()
      ? { state: "ready", agent_version: "0.0.0-fixture", lane: "development" }
      : { state: "refused", code: "agent_signed_out", lane: "development" };

  /** Plays one reply to `text`: some text, a tool, and more text. */
  const play = (conversationId: string, replyId: string, text: string) => {
    const reply = {
      conversationId,
      timers: [] as number[],
      ids: [] as string[],
    };
    replies.set(replyId, reply);
    const steps: (() => void)[] = [];
    // A turn begun ends the reply's agent turns before it.
    const begin = (turnId: string) => {
      if (reply.ids.includes(turnId)) return;
      for (const turn of turnsOf(conversationId))
        if (
          turn.kind === "agent" &&
          turn.state === "working" &&
          reply.ids.includes(turn.id)
        )
          put(conversationId, { ...turn, state: "complete" });
      reply.ids.push(turnId);
    };
    const write = (turnId: string, words: string) => {
      const all = pieces(words);
      all.forEach((piece, index) => {
        steps.push(() => {
          begin(turnId);
          const held = turnsOf(conversationId).find(
            (turn) => turn.id === turnId,
          );
          put(conversationId, {
            kind: "agent",
            id: turnId,
            text: (held?.kind === "agent" ? held.text : "") + piece.delta,
            state: "working",
          });
          // One piece is never sent, where the stream has a gap.
          if (stream === "gap" && turnId === reply.ids[0] && index === 1)
            return;
          emit(conversationId, {
            type: "text",
            reply_id: replyId,
            turn_id: turnId,
            ...piece,
          });
          // And one is sent twice, where it has none.
          if (stream === "steady" && turnId !== reply.ids[0] && index === 1)
            emit(conversationId, {
              type: "text",
              reply_id: replyId,
              turn_id: turnId,
              ...all[0]!,
            });
        });
      });
    };
    steps.push(() =>
      emit(conversationId, { type: "reply_started", reply_id: replyId }),
    );
    write(id("t"), "Lo miro en tus apuntes.");
    const toolId = id("t");
    for (const state of ["running", "done"] as const)
      steps.push(() => {
        const tool: Extract<AgentTurnRecord, { kind: "tool" }> = {
          kind: "tool",
          id: toolId,
          label: "Leer los apuntes del libro del trimestre",
          state,
        };
        begin(toolId);
        put(conversationId, tool);
        emit(conversationId, { type: "tool", reply_id: replyId, tool });
      });
    write(
      id("t"),
      `Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`,
    );
    steps.push(() => {
      settle(replyId, "complete");
    });
    steps.forEach((step, index) =>
      reply.timers.push(window.setTimeout(step, STEP_MS * (index + 1))),
    );
  };

  const settle = (replyId: string, state: "complete" | "stopped") => {
    const reply = replies.get(replyId);
    if (!reply) return;
    replies.delete(replyId);
    for (const timer of reply.timers) window.clearTimeout(timer);
    const list = turnsOf(reply.conversationId);
    const agentIds = reply.ids.filter((turnId) =>
      list.some((turn) => turn.kind === "agent" && turn.id === turnId),
    );
    // A reply stopped before it wrote anything still has its turn.
    if (agentIds.length === 0) {
      const turnId = id("t");
      put(reply.conversationId, { kind: "agent", id: turnId, text: "", state });
    }
    for (const turn of list)
      if (turn.kind === "agent" && agentIds.includes(turn.id))
        put(reply.conversationId, {
          ...turn,
          state: turn.id === agentIds.at(-1) ? state : "complete",
        });
    emit(reply.conversationId, { type: "settled", reply_id: replyId, state });
  };

  const agent: AgentViews = {
    async conversations() {
      say("agentConversations");
      await check();
      return conversations.map((record) => ({ ...record }));
    },
    async history(conversationId) {
      say(`agentHistory ${conversationId}`);
      await check();
      return turnsOf(conversationId).map((turn) => ({ ...turn }));
    },
    async documents(conversationId) {
      say(`agentDocuments ${conversationId}`);
      await check();
      return empty ? [] : (FIXTURE_DOCUMENTS[conversationId] ?? []);
    },
  };

  const session: AgentSession = {
    async status() {
      say("agentStatus");
      await wait();
      return status();
    },
    observeStatus() {
      say("agentObserveStatus");
      return Promise.resolve(() => undefined);
    },
    async providers() {
      say("agentProviders");
      await check();
      return PROVIDERS;
    },
    async startConversation() {
      say("agentStartConversation");
      await check();
      const record: AgentConversationRecord = {
        id: id("c"),
        title: "",
        last_active_at: new Date().toISOString(),
        document_count: 0,
        archived: false,
      };
      conversations.unshift(record);
      return { ...record };
    },
    async consentNeeded(request) {
      say(`agentConsentNeeded ${request.conversation_id}`);
      await check();
      const granted = grants.some(
        (grant) =>
          grant.conversation_id === request.conversation_id &&
          grant.provider_id === request.selection.provider_id &&
          grant.model_id === request.selection.model_id,
      );
      return granted
        ? null
        : {
            conversation_id: request.conversation_id,
            provider_id: request.selection.provider_id,
            model_id: request.selection.model_id,
            items: [{ kind: "messages" }],
          };
    },
    async grantConsent(request) {
      say(`agentGrantConsent ${request.conversation_id}`);
      await check();
      const grant = {
        ...request,
        grant_id: id("g"),
        granted_at: new Date().toISOString(),
      };
      grants.push(grant);
      return grant;
    },
    async withdrawConsent(grantId) {
      say(`agentWithdrawConsent ${grantId}`);
      await check();
      const at = grants.findIndex((grant) => grant.grant_id === grantId);
      if (at >= 0) grants.splice(at, 1);
    },
    async consents(conversationId) {
      say(`agentConsents ${conversationId}`);
      await check();
      return grants.filter((grant) => grant.conversation_id === conversationId);
    },
    async send(request) {
      say(`agentSend ${request.conversation_id}`);
      await check();
      const conversationId = request.conversation_id;
      if (
        !grants.some(
          (grant) =>
            grant.conversation_id === conversationId &&
            grant.provider_id === request.selection.provider_id &&
            grant.model_id === request.selection.model_id,
        )
      )
        throw coded("agent_consent_required");
      const record = conversations.find((held) => held.id === conversationId);
      if (record) {
        record.title ||= request.text.slice(0, 48);
        record.last_active_at = new Date().toISOString();
      }
      const person_turn: Extract<AgentTurnRecord, { kind: "person" }> = {
        kind: "person",
        id: id("t"),
        text: request.text,
        sent_at: new Date().toISOString(),
      };
      put(conversationId, person_turn);
      const reply_id = id("r");
      play(conversationId, reply_id, request.text);
      return { person_turn, reply_id };
    },
    async cancel(replyId) {
      say(`agentCancel ${replyId}`);
      await check();
      settle(replyId, "stopped");
    },
    observe(conversationId, listener) {
      say(`agentObserve ${conversationId}`);
      const set = listeners.get(conversationId) ?? new Set();
      listeners.set(conversationId, set);
      set.add(listener);
      return Promise.resolve(() => {
        set.delete(listener);
      });
    },
  };

  return { agent, session };
}
