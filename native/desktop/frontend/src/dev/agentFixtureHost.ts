import {
  answerFaults,
  characters,
  continuationFault,
  questionnaireFaults,
  type AnswerFault,
} from "../shell/agentClarification";
import { offeredOptions } from "../shell/agentPermission";
import type {
  AgentApproval,
  AgentApprovalOption,
  AgentQuestion,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
} from "../shell/agentSession";
import {
  isLiveStatus,
  type AgentConversationRecord,
  type AgentRanWith,
  type AgentToolCall,
  type AgentToolStatus,
  type AgentViews,
} from "../shell/agentViews";
import { FIXTURE_CATALOG } from "./fixtures/agentCatalog";
import {
  FIXTURE_CONVERSATIONS,
  FIXTURE_RUNS,
  conversationRecords,
  seeded,
  type FixtureRun,
} from "./fixtures/agent";

// The scenario host's agent: its views over the fixture conversations, and
// a session that answers every message with a made-up reply, streamed as
// the desktop host would stream one. Nothing is sent anywhere; the reply
// only repeats the message. Its providers and models are a catalog in
// cadrumo-agent's shape, every model named as a fixture.
//
// It stands in for the desktop host and keeps to what that host serves. A
// conversation is a chain of runs, and a message that continues a settled
// one starts a run of its own. A reply's text is one message with a stream of
// sequenced chunks, and a tool call in between does not start another. The
// agent records a message when its turn ends, so a reply in progress is not in
// the history, and the stream, which the host replays from the run's first
// frame to a new watch, is the only place its text so far can be had. A reply
// takes no second message while it is going.
//
/** How the fixture stream behaves: in order, with one frame sent twice, as a
 * resumed stream does; or with the stream lost once, as one the host could not
 * resume is, which the column recovers by reading the history and what is
 * pending again and watching anew. */
export type FixtureStream = "steady" | "gap";

/** What every fixture reply stops to wait on, if anything: questions, a
 * tool the agent wants to use, or a Cadrumo operation to review. */
export type FixtureAsks = "questions" | "approval" | "review";

/** Between one streamed event and the next, in milliseconds. */
const STEP_MS = 40;
/** The length of each streamed piece of text. */
const PIECE = 8;

// The questions, as cadrumo-agent serves them: every field present, a text
// question's options null. A reply that asks is given these unless its
// message asks for the most the agent can: four questions of four options,
// a prompt and an option at the longest they can be.
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
    options: null,
    required: false,
  },
];

/** `words` repeated, and ended with a full stop, to exactly `length`
 * characters. */
const exactly = (words: string, length: number) =>
  `${words.repeat(Math.ceil(length / words.length)).slice(0, length - 1)}.`;

const MOST_QUESTIONS: AgentQuestion[] = [
  {
    id: "q-trimestre",
    prompt: exactly(
      "¿Para qué trimestre preparo la declaración, y por qué? ",
      512,
    ),
    kind: "choice",
    options: [
      "Primer trimestre",
      "Segundo trimestre",
      "Tercer trimestre",
      exactly("Cuarto trimestre, con el ajuste de fin de año incluido ", 128),
    ],
    required: true,
  },
  {
    id: "q.nif_2",
    prompt: "¿Cuál es el NIF del cliente de la factura 2026-031?",
    kind: "text",
    options: null,
    required: true,
  },
  {
    id: "q-prorrata",
    prompt: "¿Aplicas la prorrata del IVA?",
    kind: "choice",
    options: ["Sí", "No"],
    required: false,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    options: null,
    required: false,
  },
];

// The options of a permission request, in the order the agent lists them,
// each under its own name. The agent offers only options that answer the call
// alone: one it would remember is withheld unless nothing else is offered.
// Their order on the card is decided by kind.
const TOOL_OPTIONS: AgentApprovalOption[] = [
  { option_id: "allow-once", name: "Allow this read", kind: "allow_once" },
  { option_id: "reject-once", name: "Skip this read", kind: "reject_once" },
];

const REVIEW_OPTIONS: AgentApprovalOption[] = [
  { option_id: "allow-once", name: "Registrar la factura", kind: "allow_once" },
  { option_id: "reject-once", name: "No registrar", kind: "reject_once" },
];

// Options the agent gives no name: absent, null, empty or only spaces.
const UNNAMED_OPTIONS: AgentApprovalOption[] = [
  { option_id: "a", name: "", kind: "allow_once" },
  { option_id: "b", kind: "reject_once" },
  { option_id: "c", name: null, kind: "allow_once" },
  { option_id: "d", name: "   ", kind: "reject_once" },
];

// A request that offers nothing but options the agent would remember, which it
// then keeps: narrowing it to nothing would refuse a question a person can
// answer. Unnamed, so the card words them by their kind.
const REMEMBERED_OPTIONS: AgentApprovalOption[] = [
  { option_id: "always-allow", kind: "allow_always" },
  { option_id: "always-reject", kind: "reject_always" },
];

// The most a request can hold: sixteen options, alternating kinds, the first
// of each named at the longest, around a tool name and a description at theirs.
const MOST_OPTIONS: AgentApprovalOption[] = [1, 2, 3, 4, 5, 6, 7, 8].flatMap(
  (number) =>
    (["allow_once", "reject_once"] as const).map(
      (kind): AgentApprovalOption => ({
        option_id: `${kind.replace("_", "-")}-${number}`,
        name:
          number === 1
            ? exactly(`${kind} with a name that goes on and on `, 128)
            : `${kind} ${number}`,
        kind,
      }),
    ),
);
const MOST_TOOL_CALL = exactly("ledger_list_every_entry_of_the_quarter_", 128);
const MOST_DESCRIPTION = exactly(
  "Permission required: ledger_list_every_entry_of_the_quarter. ",
  4096,
);

// What the agent bounds on a permission request.
const PERMISSION_OPTIONS_MAX = 16;
const PERMISSION_OPTION_ID_MAX = 64;
const PERMISSION_OPTION_NAME_MAX = 128;
const PERMISSION_TOOL_CALL_MAX = 128;
const PERMISSION_DESCRIPTION_MAX = 4096;

/** Why cadrumo-agent could not have asked for this permission. */
function approvalFaults(approval: AgentApproval): string[] {
  const notes: string[] = [];
  const { options } = approval;
  if (options.length < 1 || options.length > PERMISSION_OPTIONS_MAX)
    notes.push("a request offers one to sixteen options");
  if (new Set(options.map((option) => option.option_id)).size < options.length)
    notes.push("option ids repeat");
  if (offeredOptions(options).length < options.length)
    notes.push("an option it would remember is offered beside others");
  for (const option of options) {
    if (
      option.option_id === "" ||
      characters(option.option_id) > PERMISSION_OPTION_ID_MAX
    )
      notes.push("an option id is empty or longer than 64");
    if (characters(option.name ?? "") > PERMISSION_OPTION_NAME_MAX)
      notes.push("an option name is longer than 128");
  }
  if (characters(approval.tool_call ?? "") > PERMISSION_TOOL_CALL_MAX)
    notes.push("the tool name is longer than 128");
  if (characters(approval.description ?? "") > PERMISSION_DESCRIPTION_MAX)
    notes.push("the description is longer than 4096");
  return notes;
}

/** What the agent's answer route says when it refuses an answer. A question
 * that is not answered as the questions require is explained in a sentence
 * of its own; an answer whose shape is wrong is refused by the schema. Either
 * way it is a 422 with prose, never a code, and the host can pass on only
 * the status. */
function refusalProse(fault: AnswerFault): string {
  switch (fault.kind) {
    case "unknown_question":
      return `unknown question id '${fault.id}'`;
    case "missing":
      return `question '${fault.id}' is required and unanswered`;
    case "not_an_option":
      return `answer to question '${fault.id}' is not one of its declared options`;
    case "control_characters":
      return "clarification text must not contain control characters";
    case "too_long":
      return "String should have at most 2048 characters";
    case "invalid_id":
      return "String should match pattern for a question id";
    case "too_many":
      return "Dictionary should have at most 4 items after validation";
  }
}

/** A refusal the way the host reports the agent's: by the status alone. */
const refusedWith = (status: number, prose: string) =>
  Object.assign(new Error(prose), { code: `agent_gateway_${status}` });

declare global {
  interface Window {
    /** The agent session the page is using, for the specs that check what the
     * agent refuses where the column would not let anything through. A run
     * may make more than one session; this is the one that has been called. */
    __fixtureAgentSession?: AgentSession;
    /** Every resolution of a questionnaire the page has handed the host, in
     * order, whether the agent took it or not. */
    __fixtureAgentAnswers?: AgentQuestionnaireAnswer[];
  }
}

const coded = (code: string) => Object.assign(new Error(code), { code });

/** `text` in pieces of a few characters, whole characters each. */
const pieces = (text: string) => {
  const out: string[] = [];
  const characters = [...text];
  for (let at = 0; at < characters.length; at += PIECE)
    out.push(characters.slice(at, at + PIECE).join(""));
  return out;
};

/** What the fixture asks, checked as the agent checks what it asks: a
 * request it would not have built is a mistake of the fixture. */
function asked(questionnaire: AgentQuestionnaire): AgentQuestionnaire {
  const notes = questionnaireFaults(questionnaire);
  if (notes.length > 0)
    throw new Error(`The fixture asks what the agent would not: ${notes}`);
  return questionnaire;
}

/** What the fixture requests permission for, checked the same way. */
function requested(approval: AgentApproval): AgentApproval {
  const notes = approvalFaults(approval);
  if (notes.length > 0)
    throw new Error(`The fixture requests what the agent would not: ${notes}`);
  return approval;
}

/** The messages the fixture's triggers are written in, as an agent would be
 * asked: each makes the reply do something the real one can. */
const FAILS_FIRST = /falla antes de escribir/i;
const TOOL_FAILS = /herramienta falla/i;
const BUSY_ELSEWHERE = /ocupado/i;

/** How long a reply takes to stop, once the person asks, in milliseconds. */
const STOPPING_MS = 600;
/** What a message can be: the agent's own bound. */
const MESSAGE_MAX = 65_536;

type Reply = {
  conversationId: string;
  run: FixtureRun;
  timers: number[];
  /** The frames the agent retains for the run, from its first: what a new
   * watch is replayed. */
  frames: AgentStreamEvent[];
  /** The sequence of the last frame. */
  sequence: number;
  /** The message being written: its id, and its text so far. The agent
   * records it when its turn ends. */
  message: { id: string; text: string } | null;
  /** The stream has been lost once, as `stream=gap` asks. */
  lost: boolean;
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
  const runsOf: Record<string, FixtureRun[]> = empty
    ? {}
    : structuredClone(FIXTURE_RUNS);
  const listeners = new Map<string, Set<(event: AgentStreamEvent) => void>>();
  // The replies still going, by run.
  const replies = new Map<string, Reply>();
  // What each reply waits on, by request id.
  const waiting = new Map<string, Waiting>();
  let next = 0;
  const id = (prefix: string) => `${prefix}-${++next}`;

  const runsIn = (conversationId: string) => (runsOf[conversationId] ??= []);
  const reply = (one: FixtureRun, conversationId: string): Reply => {
    const held = replies.get(one.id);
    if (held) return held;
    const made: Reply = {
      conversationId,
      run: one,
      timers: [],
      frames: [],
      sequence: 0,
      message: null,
      lost: false,
    };
    replies.set(one.id, made);
    return made;
  };
  // A run that was going when the profile was read has a reply to stop.
  for (const [conversationId, runs] of Object.entries(runsOf))
    for (const one of runs)
      if (isLiveStatus(one.status)) reply(one, conversationId);

  /** Hands `event` to those watching the conversation, and retains it. */
  const emit = (held: Reply, event: AgentStreamEvent) => {
    held.frames.push(event);
    for (const listener of listeners.get(held.conversationId) ?? [])
      listener(event);
  };
  const check = async () => {
    await wait();
    if (!readable()) throw refused();
  };
  const status = (): AgentServiceStatus =>
    readable()
      ? { state: "ready", agent_version: "0.0.0-fixture", lane: "development" }
      : { state: "refused", code: "agent_signed_out", lane: "development" };

  /** Runs `steps` one after another from now, as the reply's stream. */
  const schedule = (held: Reply, steps: (() => void)[]) => {
    held.timers = steps.map((step, index) =>
      window.setTimeout(step, STEP_MS * (index + 1)),
    );
  };

  /** The turn the reply was writing ends: the agent records its message. */
  const endTurn = (held: Reply) => {
    if (!held.message) return;
    held.run.messages.push({
      id: held.message.id,
      role: "assistant",
      text: held.message.text,
    });
    held.message = null;
  };

  /** The steps that write `words` into the reply's message, `separator` first
   * where it already has text. A message begun here is a new turn's. */
  const write = (held: Reply, words: string) =>
    pieces(words).map((piece, index, all) => () => {
      const separated = held.message ? `\n\n${piece}` : piece;
      held.message ??= { id: id("m"), text: "" };
      const delta = index === 0 ? separated : piece;
      held.message.text += delta;
      const event: AgentStreamEvent = {
        type: "text",
        reply_id: held.run.id,
        message_id: held.message.id,
        sequence: ++held.sequence,
        delta,
      };
      held.frames.push(event);
      // One frame is lost, where the stream is, and the agent's replay is
      // asked for what was missed.
      if (stream === "gap" && !held.lost && index === 1 && all.length > 2) {
        held.lost = true;
        const watchers = listeners.get(held.conversationId) ?? new Set();
        for (const listener of [...watchers])
          listener({ type: "lost", reply_id: held.run.id });
        watchers.clear();
        return;
      }
      for (const listener of listeners.get(held.conversationId) ?? [])
        listener(event);
      // And one is sent twice, where the stream is steady.
      if (stream === "steady" && index === 1)
        for (const listener of listeners.get(held.conversationId) ?? [])
          listener(event);
    });

  /** The steps of a tool the agent calls, through `states`. */
  const tool = (
    held: Reply,
    title: string,
    tool_kind: AgentToolCall["tool_kind"],
    states: readonly AgentToolStatus[],
  ) => {
    const call: AgentToolCall = {
      id: id("t"),
      title,
      tool_kind,
      status: "pending",
    };
    return states.map((state) => () => {
      const now: AgentToolCall = { ...call, status: state };
      const at = held.run.tools.findIndex((held) => held.id === call.id);
      if (at < 0) held.run.tools.push(now);
      else held.run.tools[at] = now;
      held.sequence += 1;
      emit(held, { type: "tool", reply_id: held.run.id, tool: now });
    });
  };

  /** A step that parks the reply until the person decides `on`. */
  const park = (held: Reply, on: Waiting) => () => {
    endTurn(held);
    held.run.status = "input_required";
    const event: AgentStreamEvent =
      on.kind === "questions"
        ? {
            type: "questions",
            reply_id: held.run.id,
            questionnaire: on.questionnaire,
          }
        : { type: "approval", reply_id: held.run.id, approval: on.approval };
    const requestId =
      on.kind === "questions"
        ? on.questionnaire.request_id
        : on.approval.request_id;
    waiting.set(requestId, on);
    emit(held, event);
  };

  const finish = (held: Reply) => () => settle(held.run.id, "completed");

  const started = (held: Reply) => () =>
    emit(held, { type: "reply_started", reply_id: held.run.id });

  /** Plays one reply to `text`: some text, a tool, and more text, or a
   * stop for what this run asks of the person. */
  const play = (held: Reply, text: string) => {
    const goOn = (steps: (() => void)[]) => schedule(held, steps);
    if (FAILS_FIRST.test(text)) {
      // It fails before the agent wrote anything.
      schedule(held, [
        started(held),
        () =>
          settle(held.run.id, "failed", {
            provider_condition: "provider_overloaded",
            failure_reason: "The provider answered 529 overloaded_error.",
          }),
      ]);
      return;
    }
    if (asks === "questions") {
      const request_id = id("q");
      schedule(held, [
        started(held),
        ...write(held, "Necesito un par de datos antes de seguir."),
        park(held, {
          kind: "questions",
          questionnaire: asked({
            request_id,
            reply_id: held.run.id,
            questions: /cuatro preguntas/i.test(text)
              ? MOST_QUESTIONS
              : QUESTIONS,
          }),
          then: (answer) =>
            goOn([
              () => {
                held.run.status = "running";
              },
              ...write(
                held,
                answer.kind === "answers"
                  ? `Con eso me basta: ${Object.values(answer.answers).join(", ")}.`
                  : answer.kind === "message"
                    ? `Has respondido: «${answer.text}».`
                    : "De acuerdo, sigo sin esas respuestas.",
              ),
              finish(held),
            ]),
        }),
      ]);
      return;
    }
    if (asks === "approval" || asks === "review") {
      const review = asks === "review";
      const title = review
        ? "Registrar la factura 2026-031"
        : "Leer los apuntes del libro";
      // A message asks for the permission the agent gives least to go on,
      // or the most it can.
      const unnamed = !review && /sin nombres/i.test(text);
      const most = !review && /extremos/i.test(text);
      const remembered = !review && /solo recuerdos/i.test(text);
      // The agent says a tool's name and a line that repeats it, and serves
      // nothing of the call's input. A Cadrumo review words itself.
      const toolName = "ledger_list";
      schedule(held, [
        started(held),
        ...write(held, "Para eso necesito tu permiso."),
        park(held, {
          kind: "approval",
          approval: requested({
            request_id: id("p"),
            reply_id: held.run.id,
            source: review ? "cadrumo_review" : "agent_tool",
            tool_call: review
              ? title
              : unnamed
                ? null
                : most
                  ? MOST_TOOL_CALL
                  : toolName,
            tool_kind: review || unnamed ? null : "read",
            description: review
              ? "Añade la factura al libro de ingresos del tercer trimestre."
              : unnamed
                ? null
                : most
                  ? MOST_DESCRIPTION
                  : `Permission required: ${toolName}`,
            options: review
              ? REVIEW_OPTIONS
              : unnamed
                ? UNNAMED_OPTIONS
                : most
                  ? MOST_OPTIONS
                  : remembered
                    ? REMEMBERED_OPTIONS
                    : TOOL_OPTIONS,
          }),
          then: (option) =>
            goOn(
              option.kind.startsWith("allow")
                ? [
                    () => {
                      held.run.status = "running";
                    },
                    ...tool(held, title, review ? "edit" : "read", [
                      "pending",
                      "in_progress",
                      "completed",
                    ]),
                    ...write(held, "Hecho."),
                    finish(held),
                  ]
                : [
                    () => {
                      held.run.status = "running";
                    },
                    ...write(held, "Sin ese permiso no sigo."),
                    finish(held),
                  ],
            ),
        }),
      ]);
      return;
    }
    schedule(held, [
      started(held),
      ...write(held, "Lo miro en tus apuntes."),
      ...tool(
        held,
        "ledger_list",
        "read",
        TOOL_FAILS.test(text)
          ? ["pending", "in_progress", "failed"]
          : ["pending", "in_progress", "completed"],
      ),
      ...write(
        held,
        `Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`,
      ),
      finish(held),
    ]);
  };

  /** The reply ends as `end`: the agent records what it wrote, the run takes
   * its final status, and the stream says so. */
  const settle = (
    replyId: string,
    end: "completed" | "failed" | "cancelled",
    why: {
      provider_condition?: NonNullable<FixtureRun["provider_condition"]>;
      failure_reason?: string;
    } = {},
  ) => {
    const held = replies.get(replyId);
    if (!held) return;
    replies.delete(replyId);
    for (const timer of held.timers) window.clearTimeout(timer);
    for (const [requestId, on] of waiting) {
      const owner =
        on.kind === "questions"
          ? on.questionnaire.reply_id
          : on.approval.reply_id;
      if (owner !== replyId) continue;
      waiting.delete(requestId);
      emit(held, {
        type: "resolved",
        reply_id: replyId,
        request_id: requestId,
      });
    }
    endTurn(held);
    const { run: ended } = held;
    ended.status = end;
    if (why.provider_condition)
      ended.provider_condition = why.provider_condition;
    if (why.failure_reason) ended.failure_reason = why.failure_reason;
    // Tokens as the provider would count them: the fixture's are made up.
    const written = ended.messages.reduce(
      (sum, message) => sum + message.text.length,
      0,
    );
    ended.usage = {
      input_tokens: 1_000 + written,
      output_tokens: Math.ceil(written / 4),
    };
    emit(held, {
      type: "settled",
      reply_id: replyId,
      status: end,
      ...(why.provider_condition
        ? { provider_condition: why.provider_condition }
        : {}),
      ...(why.failure_reason ? { failure_reason: why.failure_reason } : {}),
    });
  };

  /** The request `requestId` of reply `replyId`, taken off what waits. */
  const take = (replyId: string, requestId: string) => {
    const on = waiting.get(requestId);
    const owner =
      on?.kind === "questions"
        ? on.questionnaire.reply_id
        : on?.approval.reply_id;
    const held = replies.get(replyId);
    // The run has no such request pending: the agent's 404.
    if (!on || !held || owner !== replyId)
      throw refusedWith(
        404,
        "Clarification request is not pending for this run",
      );
    return { on, held };
  };
  const resolve = (replyId: string, requestId: string, held: Reply) => {
    waiting.delete(requestId);
    emit(held, { type: "resolved", reply_id: replyId, request_id: requestId });
  };

  /** What a run ran with, by the display names its lane's catalog gives. */
  const ranWith = (request: AgentSendRequest): AgentRanWith => {
    const { provider, transport, model, effort } = request.selection;
    const lane = (FIXTURE_CATALOG.providers ?? []).find(
      (held) => held.provider_id === provider && held.transport === transport,
    );
    const entry = lane?.catalog.models?.find((held) => held.model === model);
    return {
      provider,
      transport,
      provider_display_name: lane?.display_name ?? null,
      model,
      model_display_name: entry?.display_name ?? null,
      effort: effort ?? null,
    };
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
      return structuredClone(conversationRecords(runsIn(conversationId)));
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
    async providerCatalog() {
      say("agentProviderCatalog");
      await check();
      return FIXTURE_CATALOG;
    },
    async startConversation() {
      say("agentStartConversation");
      await check();
      // The id its first run will have. The agent knows no conversation until
      // that run exists, so none is listed before the first message is sent.
      return {
        id: id("r"),
        title: "",
        last_active_at: new Date().toISOString(),
        archived: false,
      };
    },
    async send(request) {
      window.__fixtureAgentSession = session;
      const { provider, transport } = request.selection;
      say(`agentSend ${request.conversation_id} ${provider}/${transport}`);
      await check();
      const conversationId = request.conversation_id;
      const { text } = request;
      const runs = runsIn(conversationId);
      const last = runs.at(-1);
      // The host checks a message before it asks the agent anything.
      if (text.trim() === "" || characters(text) > MESSAGE_MAX)
        throw coded("agent_invalid_request");
      // A reply still going takes no second message, and none is queued.
      if ((last && isLiveStatus(last.status)) || BUSY_ELSEWHERE.test(text))
        throw coded("agent_reply_in_progress");
      const sentAt = new Date().toISOString();
      const fresh: FixtureRun = {
        // The first run of a conversation has the conversation's id.
        id: last ? id("r") : conversationId,
        status: "running",
        messages: seeded(last?.messages ?? [], [
          { role: "user", text, sent_at: sentAt },
        ]),
        tools: [],
        selection: ranWith(request),
      };
      runs.push(fresh);
      const record = conversations.find((held) => held.id === conversationId);
      if (record) record.last_active_at = sentAt;
      else
        conversations.unshift({
          id: conversationId,
          title: text.slice(0, 48),
          last_active_at: sentAt,
          archived: false,
        });
      play(reply(fresh, conversationId), text);
      return { reply_id: fresh.id };
    },
    async cancel(replyId) {
      say(`agentCancel ${replyId}`);
      await check();
      const held = replies.get(replyId);
      if (
        !held ||
        !isLiveStatus(held.run.status) ||
        held.run.status === "cancelling"
      )
        throw refusedWith(409, "Run cannot be cancelled in its state");
      for (const timer of held.timers) window.clearTimeout(timer);
      held.timers = [];
      held.run.status = "cancelling";
      // It is cancelling until the agent has stopped it.
      window.setTimeout(() => settle(replyId, "cancelled"), STOPPING_MS);
    },
    async archive(conversationId) {
      say(`agentArchive ${conversationId}`);
      await check();
      const runs = runsIn(conversationId);
      if (runs.some((held) => isLiveStatus(held.status)))
        throw coded("agent_reply_in_progress");
      for (const held of runs) held.status = "archived";
      const record = conversations.find((held) => held.id === conversationId);
      if (record) record.archived = true;
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
      (window.__fixtureAgentAnswers ??= []).push(answer);
      say(`agentAnswerQuestions ${questionnaire.request_id} ${answer.kind}`);
      await check();
      const { on, held } = take(
        questionnaire.reply_id,
        questionnaire.request_id,
      );
      if (on.kind !== "questions")
        throw refusedWith(
          404,
          "Clarification request is not pending for this run",
        );
      // The agent takes exactly one of three resolutions, and holds only
      // answers to what was asked: a continuation is held to the message
      // limits, and a decline to nothing, as refusing is not an answer.
      if (answer.kind === "answers") {
        const faults = answerFaults(on.questionnaire.questions, answer.answers);
        if (faults.length > 0)
          throw refusedWith(422, faults.map(refusalProse).join("; "));
      } else if (answer.kind === "message") {
        const fault = continuationFault(answer.text);
        if (fault)
          throw refusedWith(
            422,
            fault === "blank"
              ? "prompt must not be blank"
              : "String should have at most 65536 characters",
          );
        // The continuation is a message of the run, recorded at once.
        held.run.messages.push({
          role: "user",
          text: answer.text,
          sent_at: new Date().toISOString(),
        });
      }
      resolve(questionnaire.reply_id, questionnaire.request_id, held);
      on.then(answer);
      return {};
    },
    async decideApproval(approval, optionId) {
      say(`agentDecideApproval ${approval.request_id} ${optionId}`);
      await check();
      const { on, held } = take(approval.reply_id, approval.request_id);
      if (on.kind !== "approval")
        throw refusedWith(404, "Permission request is no longer pending");
      // An answer names an option of one to 64 characters, which the host
      // checks before it asks, and one the request offered, which the agent
      // refuses as a conflict.
      if (optionId === "" || characters(optionId) > PERMISSION_OPTION_ID_MAX)
        throw coded("agent_invalid_request");
      const option = on.approval.options.find(
        (held) => held.option_id === optionId,
      );
      if (!option)
        throw refusedWith(409, "Unknown permission option for this request");
      resolve(approval.reply_id, approval.request_id, held);
      on.then(option);
    },
    observe(conversationId, listener) {
      window.__fixtureAgentSession = session;
      say(`agentObserve ${conversationId}`);
      const set = listeners.get(conversationId) ?? new Set();
      listeners.set(conversationId, set);
      set.add(listener);
      // The agent replays a run from its first retained frame to a new
      // watch, and the host passes it on as it comes.
      const live = runsIn(conversationId).at(-1);
      const held = live && replies.get(live.id);
      if (held) for (const frame of [...held.frames]) listener(frame);
      return Promise.resolve(() => {
        set.delete(listener);
      });
    },
  };

  return { agent, session };
}
