import type {
  AgentApproval,
  AgentApprovalOption,
  AgentConsentGrant,
  AgentProviderRecord,
  AgentQuestion,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
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

/** What every fixture reply stops to wait on, if anything: questions, a
 * tool the agent wants to use, or a Cadrumo operation to review. */
export type FixtureAsks = "questions" | "approval" | "review";

/** Between one streamed event and the next, in milliseconds. */
const STEP_MS = 40;
/** The length of each streamed piece of text. */
const PIECE = 8;
/** The bounds the agent sets on a questionnaire. */
const MOST_QUESTIONS = 4;
const MOST_OPTIONS = 4;
const ANSWER_MAX = 2048;

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

const QUESTIONS: AgentQuestion[] = [
  {
    id: "q-trimestre",
    prompt: "¿Qué trimestre preparo?",
    kind: "choice",
    options: ["Primer trimestre", "Segundo trimestre", "Tercer trimestre"],
    required: true,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    required: false,
  },
];

const EVERY_OPTION: AgentApprovalOption[] = [
  { option_id: "allow-once", name: "Allow once", kind: "allow_once" },
  { option_id: "allow-always", name: "Always allow", kind: "allow_always" },
  { option_id: "reject-once", name: "Reject", kind: "reject_once" },
  { option_id: "reject-always", name: "Always reject", kind: "reject_always" },
];

const coded = (code: string) => Object.assign(new Error(code), { code });

const pieces = (text: string) => {
  const out: { offset: number; delta: string }[] = [];
  for (let offset = 0; offset < text.length; offset += PIECE)
    out.push({ offset, delta: text.slice(offset, offset + PIECE) });
  return out;
};

/** Why `answers` cannot answer `questions`, as the agent refuses it. */
function answerFault(
  questions: readonly AgentQuestion[],
  answers: Record<string, string>,
): string | null {
  for (const [id, answer] of Object.entries(answers)) {
    const question = questions.find((held) => held.id === id);
    if (!question) return "agent_answer_unknown_question";
    if (question.kind === "choice" && !question.options?.includes(answer))
      return "agent_answer_not_an_option";
    if (question.kind === "text" && answer.length > ANSWER_MAX)
      return "agent_answer_too_long";
  }
  if (
    questions.some((question) => question.required && !(question.id in answers))
  )
    return "agent_answer_missing";
  return null;
}

type Reply = {
  conversationId: string;
  timers: number[];
  ids: string[];
};

type Waiting =
  | {
      kind: "questions";
      questionnaire: AgentQuestionnaire;
      then: (answer: AgentQuestionnaireAnswer) => void;
    }
  | {
      kind: "approval";
      approval: AgentApproval;
      then: (option: AgentApprovalOption) => void;
    };

export function fixtureAgent({
  say,
  wait,
  readable,
  empty,
  stream,
  asks,
  refused,
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in that the conversations belong to. */
  readable: () => boolean;
  /** The profile has no conversations yet. */
  empty: boolean;
  stream: FixtureStream;
  asks: FixtureAsks | null;
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
  const replies = new Map<string, Reply>();
  // What each reply waits on, by request id.
  const waiting = new Map<string, Waiting>();
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
  const granted = (
    conversationId: string,
    providerId: string,
    modelId: string,
  ) =>
    grants.some(
      (grant) =>
        grant.conversation_id === conversationId &&
        grant.provider_id === providerId &&
        grant.model_id === modelId,
    );

  const status = (): AgentServiceStatus =>
    readable()
      ? { state: "ready", agent_version: "0.0.0-fixture", lane: "development" }
      : { state: "refused", code: "agent_signed_out", lane: "development" };

  /** Runs `steps` one after another from now, as the reply's stream. */
  const run = (reply: Reply, steps: (() => void)[]) => {
    reply.timers = steps.map((step, index) =>
      window.setTimeout(step, STEP_MS * (index + 1)),
    );
  };

  // A turn begun ends the reply's agent turns before it.
  const begin = (reply: Reply, turnId: string) => {
    if (reply.ids.includes(turnId)) return;
    for (const turn of turnsOf(reply.conversationId))
      if (
        turn.kind === "agent" &&
        turn.state === "working" &&
        reply.ids.includes(turn.id)
      )
        put(reply.conversationId, { ...turn, state: "complete" });
    reply.ids.push(turnId);
  };

  /** The steps that write `words` as a new agent turn of the reply. */
  const write = (replyId: string, reply: Reply, words: string) => {
    const turnId = id("t");
    const { conversationId } = reply;
    const all = pieces(words);
    return all.map((piece, index) => () => {
      begin(reply, turnId);
      const first = reply.ids[0] === turnId;
      const held = turnsOf(conversationId).find((turn) => turn.id === turnId);
      put(conversationId, {
        kind: "agent",
        id: turnId,
        text: (held?.kind === "agent" ? held.text : "") + piece.delta,
        state: "working",
      });
      // One piece is never sent, where the stream has a gap.
      if (stream === "gap" && first && index === 1) return;
      const event: AgentStreamEvent = {
        type: "text",
        reply_id: replyId,
        turn_id: turnId,
        ...piece,
      };
      emit(conversationId, event);
      // And one is sent twice, where it has none.
      if (stream === "steady" && !first && index === 1)
        emit(conversationId, { ...event, ...all[0]! });
    });
  };

  /** The steps of a tool the agent calls, from running to done. */
  const tool = (replyId: string, reply: Reply, label: string) => {
    const toolId = id("t");
    return (["running", "done"] as const).map((state) => () => {
      const turn: Extract<AgentTurnRecord, { kind: "tool" }> = {
        kind: "tool",
        id: toolId,
        label,
        state,
      };
      begin(reply, toolId);
      put(reply.conversationId, turn);
      emit(reply.conversationId, {
        type: "tool",
        reply_id: replyId,
        tool: turn,
      });
    });
  };

  /** A step that parks the reply until the person decides `on`. */
  const park = (replyId: string, reply: Reply, on: Waiting) => () => {
    const event: AgentStreamEvent =
      on.kind === "questions"
        ? {
            type: "questions",
            reply_id: replyId,
            questionnaire: on.questionnaire,
          }
        : { type: "approval", reply_id: replyId, approval: on.approval };
    const requestId =
      on.kind === "questions"
        ? on.questionnaire.request_id
        : on.approval.request_id;
    waiting.set(requestId, on);
    emit(reply.conversationId, event);
  };

  const finish = (replyId: string) => () => settle(replyId, "complete");

  /** Plays one reply to `text`: some text, a tool, and more text, or a
   * stop for what this run asks of the person. */
  const play = (conversationId: string, replyId: string, text: string) => {
    const reply: Reply = { conversationId, timers: [], ids: [] };
    replies.set(replyId, reply);
    const started = () =>
      emit(conversationId, { type: "reply_started", reply_id: replyId });
    const goOn = (steps: (() => void)[]) => run(reply, steps);
    if (asks === "questions") {
      const request_id = id("q");
      run(reply, [
        started,
        ...write(replyId, reply, "Necesito un par de datos antes de seguir."),
        park(replyId, reply, {
          kind: "questions",
          questionnaire: {
            request_id,
            reply_id: replyId,
            questions: QUESTIONS,
          },
          then: (answer) =>
            goOn([
              ...write(
                replyId,
                reply,
                answer.kind === "answers"
                  ? `Con eso me basta: ${Object.values(answer.answers).join(", ")}.`
                  : answer.kind === "message"
                    ? `Has respondido: «${answer.text}».`
                    : "De acuerdo, sigo sin esas respuestas.",
              ),
              finish(replyId),
            ]),
        }),
      ]);
      return;
    }
    if (asks === "approval" || asks === "review") {
      const review = asks === "review";
      const label = review
        ? "Registrar la factura 2026-031"
        : "Leer los apuntes del libro";
      run(reply, [
        started,
        ...write(replyId, reply, "Para eso necesito tu permiso."),
        park(replyId, reply, {
          kind: "approval",
          approval: {
            request_id: id("p"),
            reply_id: replyId,
            source: review ? "cadrumo_review" : "agent_tool",
            title: label,
            description: review
              ? "Añade la factura al libro de ingresos del tercer trimestre."
              : "Lee los apuntes del tercer trimestre de este perfil.",
            options: review
              ? EVERY_OPTION.filter((option) => option.kind.endsWith("_once"))
              : EVERY_OPTION,
          },
          then: (option) =>
            goOn(
              option.kind.startsWith("allow")
                ? [
                    ...tool(replyId, reply, label),
                    ...write(replyId, reply, "Hecho."),
                    finish(replyId),
                  ]
                : [
                    ...write(replyId, reply, "Sin ese permiso no sigo."),
                    finish(replyId),
                  ],
            ),
        }),
      ]);
      return;
    }
    run(reply, [
      started,
      ...write(replyId, reply, "Lo miro en tus apuntes."),
      ...tool(replyId, reply, "Leer los apuntes del libro del trimestre"),
      ...write(
        replyId,
        reply,
        `Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`,
      ),
      finish(replyId),
    ]);
  };

  const settle = (replyId: string, state: "complete" | "stopped") => {
    const reply = replies.get(replyId);
    if (!reply) return;
    replies.delete(replyId);
    for (const timer of reply.timers) window.clearTimeout(timer);
    for (const [requestId, on] of waiting) {
      const owner =
        on.kind === "questions"
          ? on.questionnaire.reply_id
          : on.approval.reply_id;
      if (owner === replyId) waiting.delete(requestId);
    }
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

  /** The request `requestId` of reply `replyId`, taken off what waits. */
  const take = (replyId: string, requestId: string) => {
    const on = waiting.get(requestId);
    const owner =
      on?.kind === "questions"
        ? on.questionnaire.reply_id
        : on?.approval.reply_id;
    const reply = replies.get(replyId);
    if (!on || !reply || owner !== replyId)
      throw coded("agent_request_unknown");
    return { on, reply };
  };
  const resolve = (replyId: string, requestId: string, reply: Reply) => {
    waiting.delete(requestId);
    emit(reply.conversationId, {
      type: "resolved",
      reply_id: replyId,
      request_id: requestId,
    });
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
      return granted(
        request.conversation_id,
        request.selection.provider_id,
        request.selection.model_id,
      )
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
        !granted(
          conversationId,
          request.selection.provider_id,
          request.selection.model_id,
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
    async pending(conversationId) {
      say(`agentPending ${conversationId}`);
      await check();
      const questionnaires: AgentQuestionnaire[] = [];
      const approvals: AgentApproval[] = [];
      for (const on of waiting.values()) {
        const replyId =
          on.kind === "questions"
            ? on.questionnaire.reply_id
            : on.approval.reply_id;
        if (replies.get(replyId)?.conversationId !== conversationId) continue;
        if (on.kind === "questions") questionnaires.push(on.questionnaire);
        else approvals.push(on.approval);
      }
      return { questionnaires, approvals };
    },
    async answerQuestions(questionnaire, answer) {
      say(`agentAnswerQuestions ${questionnaire.request_id} ${answer.kind}`);
      await check();
      const { on, reply } = take(
        questionnaire.reply_id,
        questionnaire.request_id,
      );
      if (on.kind !== "questions") throw coded("agent_request_unknown");
      const { questions } = on.questionnaire;
      if (questions.length > MOST_QUESTIONS) throw coded("agent_too_many");
      if (
        questions.some(
          (question) => (question.options?.length ?? 0) > MOST_OPTIONS,
        )
      )
        throw coded("agent_too_many");
      if (answer.kind === "answers") {
        const fault = answerFault(questions, answer.answers);
        if (fault) throw coded(fault);
      }
      let person_turn: Extract<AgentTurnRecord, { kind: "person" }> | undefined;
      if (answer.kind === "message") {
        person_turn = {
          kind: "person",
          id: id("t"),
          text: answer.text,
          sent_at: new Date().toISOString(),
        };
        put(reply.conversationId, person_turn);
      }
      resolve(questionnaire.reply_id, questionnaire.request_id, reply);
      on.then(answer);
      return person_turn ? { person_turn } : {};
    },
    async decideApproval(approval, optionId) {
      say(`agentDecideApproval ${approval.request_id} ${optionId}`);
      await check();
      const { on, reply } = take(approval.reply_id, approval.request_id);
      if (on.kind !== "approval") throw coded("agent_request_unknown");
      const option = on.approval.options.find(
        (held) => held.option_id === optionId,
      );
      if (!option) throw coded("agent_option_unknown");
      resolve(approval.reply_id, approval.request_id, reply);
      on.then(option);
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
