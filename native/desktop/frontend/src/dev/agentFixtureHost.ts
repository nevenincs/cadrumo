import {
  answerFaults,
  characters,
  continuationFault,
} from "../shell/agentClarification";
import type {
  AgentDropSignal,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
  AgentStreamToolCall,
  AgentToolRefusal,
} from "../shell/agentSession";
import {
  isLiveStatus,
  type AgentConversationRecord,
  type AgentDocumentRecord,
  type AgentViews,
} from "../shell/agentViews";
import type { ToolCallStatus } from "../shell/agentGatewayContract";
import type {
  LocalEngine,
  LocalModelListStatus,
} from "../shell/localModelsContract";
import { coded, fixtureModelHost } from "./agentFixtureModels";
import {
  FIXTURE_CATALOG,
  type FixtureCatalog,
  type FixtureEngineHealth,
  type FixtureModelPresence,
} from "./fixtures/agentCatalog";
import {
  FIXTURE_SKILLS,
  FIXTURE_SKILLS_REVISION,
  MANY_FIXTURE_SKILLS,
  fixtureSkillDetail,
  fixtureSkillVerification,
  type FixtureSkills,
} from "./fixtures/agentSkills";
import {
  FIXTURE_CONVERSATIONS,
  FIXTURE_ATTACHMENT_POLICY,
  pickedRefusal,
  FIXTURE_DOCUMENTS,
  FIXTURE_RUNS,
  conversationRecords,
  seeded,
  type FixtureRun,
} from "./fixtures/agent";
import type { BarredRead } from "../shell/attachmentRefusals";
import type { Reply, Waiting } from "./agentFixtureReply";
import type {
  FixtureAsks,
  FixtureDocuments,
  FixtureEngineChoices,
  FixtureLocalModels,
  FixtureStream,
} from "./agentFixtureOptions";
import {
  CANONICAL_OPTIONS,
  MOST_DESCRIPTION,
  MOST_OPTIONS,
  MOST_QUESTIONS,
  MOST_TOOL_CALL,
  PERMISSION_OPTION_ID_MAX,
  PERMISSION_TARGETS,
  QUESTIONS,
  TOOL_OPTIONS,
  UNNAMED_OPTIONS,
  asked,
  barredAsk,
  barredCard,
  refusalProse,
  refusedWith,
  requested,
} from "./agentFixtureAsks";
import { atState, toolCall, toolTitle } from "./agentFixtureTools";
import { fixtureMovementAttach } from "./agentFixtureMovement";
import {
  AUTHENTICATION_REQUIRED,
  BUSY_ELSEWHERE,
  FAILS_FIRST,
  LINK_REPLIES,
  LINK_TO,
  MODEL_DOES_NOT_FIT,
  PROVIDER_CREDENTIAL_MISSING,
  RICH,
  RICH_REPLY,
  RICH_THOUGHTS,
  RICH_TOOL_DETAILS,
  RUN_OUTGROWS_MODEL,
  TOOL_FAILS,
  TOOL_REFUSALS,
  UNEXPECTED_PROVIDER_CONDITION,
} from "./agentFixtureTriggers";
import {
  MODEL_UNAVAILABLE,
  MODEL_UNAVAILABLE_WHY,
  admitted,
} from "./fixtures/agentLanes";
import { pieces } from "./fixtures/textPieces";
import type {
  AgentApproval,
  AgentDocumentReference,
  AgentQuestionnaire,
  AgentRanWith,
} from "../shell/agentSnapshotContract";

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
/** How long a `busy-past-ready` service stays busy once it reports ready,
 * as work begun before it was ready ends: longer than reads asked back to
 * back take, shorter than the window's first pause. */
const BUSY_PAST_READY_MS = 1_000;

/** How many stored documents one listing page holds here: few enough that
 * the fixture's longest list is read in several. */
const DOCUMENT_PAGE = 100;

/** How long each step of a fixture upload takes. */
const UPLOAD_STEP_MS = 150;

/** Between one streamed event and the next, in milliseconds. */
const STEP_MS = 40;

declare global {
  interface Window {
    /** The agent session the page is using, for the specs that check what the
     * agent refuses where the column would not let anything through. A run
     * may make more than one session; this is the one that has been called. */
    __fixtureAgentSession?: AgentSession;
    /** The same session's read projections, for controlled transport delays. */
    __fixtureAgentViews?: AgentViews;
    /** Intercepts list reads inside the method, including bound host copies;
     * a record it returns is answered in place of the stored one. */
    __fixtureLocalModelsRead?: () => Promise<LocalModelListStatus | void>;
    /** Intercepts catalogue and engine reads; a refusal thrown answers them. */
    __fixtureProviderCatalogRead?: () => Promise<void>;
    __fixtureLocalEngineRead?: () => Promise<void>;
    /** Holds an engine or placement change inside the method, after the
     * revision is checked and before the record is written. */
    __fixtureLocalEngineChange?: () => Promise<void>;
    __fixtureAgentDrop?: (signal: AgentDropSignal) => void;
    /** Every resolution of a questionnaire the page has handed the host, in
     * order, whether the agent took it or not. */
    __fixtureAgentAnswers?: AgentQuestionnaireAnswer[];
  }
}

/** How long a reply takes to stop, once the person asks, in milliseconds. */
const STOPPING_MS = 600;
/** What a message can be: the agent's own bound. */
const MESSAGE_MAX = 65_536;

export function fixtureAgent({
  say,
  wait,
  signedIn,
  readable,
  empty,
  stream,
  asks,
  refused,
  turnedOff = () => new Set<string>(),
  documents = "stored",
  skills = "bundled",
  catalog = "served",
  models,
  localModels,
  engineHealth,
  engineChoices,
  localEngine,
  readingDefault,
  readMovement,
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in, independently of whether a read succeeds. */
  signedIn: () => boolean;
  /** The profile's read requests succeed. */
  readable: () => boolean;
  /** The profile has no conversations yet. */
  empty: boolean;
  stream: FixtureStream;
  asks: FixtureAsks | null;
  /** Thrown when a read cannot be served. */
  refused: () => unknown;
  /** The lanes the profile turned off, as `<provider>_<transport>`. */
  turnedOff?: () => ReadonlySet<string>;
  documents?: FixtureDocuments;
  /** How the agent serves its skills to `/`. */
  skills?: FixtureSkills;
  catalog?: FixtureCatalog;
  /** Which models this computer holds, as the served catalog reports them. */
  models?: FixtureModelPresence;
  /** The local lanes hold none of their models yet, as before any setup, or
   * all of them, as after every download; where left out, as written. */
  localModels?: FixtureLocalModels;
  /** What the service states of each local engine, where not as the fixture
   * catalog writes it: every engine running. */
  engineHealth?: FixtureEngineHealth;
  /** The engines and placements the service offers, where not all it knows. */
  engineChoices?: FixtureEngineChoices;
  /** The engine the stored record names at the start; where left out, the
   * bundled llama.cpp. */
  localEngine?: LocalEngine;
  /** The installed model the service serves as the one documents are read
   * with while no choice is stored; where left out, none stands in. */
  readingDefault?: { lane: string; model: string };
  /** The ledger's movement read, where a movement can be handed over. */
  readMovement?: (transactionId: string) => Promise<object>;
}): {
  agent: AgentViews;
  session: AgentSession;
  /** Publishes the agent's status, as the service does once it is ready. */
  publishStatus: (status?: AgentServiceStatus) => void;
  /** Sends the status the window holds again, unchanged, as the host does
   * when the service says a read it answered busy or pending for settled. */
  republishStatus: () => void;
  /** Changes the stored model list from elsewhere. */
  changeListElsewhere: () => void;
  /** The local engine the stored record selects now. */
  selectedEngine: () => string;
} {
  let publishedStatus: AgentServiceStatus | null =
    catalog === "unsupported"
      ? { state: "refused", code: "agent_platform_unsupported" }
      : catalog === "declared" || catalog === "busy-past-ready"
        ? { state: "starting", lane: "development" }
        : null;
  // The host keeps one status listener: a new subscription replaces the
  // earlier one, which hears nothing more, and a subscription ends only the
  // listener it made.
  let statusListener: ((status: AgentServiceStatus) => void) | null = null;
  const inventory = skills === "many" ? MANY_FIXTURE_SKILLS : FIXTURE_SKILLS;
  const knownSkill = (name: string) => {
    const held = inventory.find((one) => one.name === name);
    if (!held) throw coded("agent_gateway_skill_not_found");
    return held;
  };
  // What each conversation has stored, which an attach adds to.
  const storage = new Map<string, AgentDocumentRecord[]>(
    documents === "stored" && !empty
      ? Object.entries(FIXTURE_DOCUMENTS).map(([id, held]) => [id, [...held]])
      : [],
  );
  const stored = (conversationId: string) => storage.get(conversationId) ?? [];
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
  // The reads the service refuses for a bar, by request.
  const barredReads = new Map<string, BarredRead>();
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
  const modelHost = fixtureModelHost({
    say,
    check,
    catalog,
    turnedOff,
    models,
    localModels,
    engineHealth,
    engineChoices,
    localEngine,
    readingDefault,
  });
  const status = (): AgentServiceStatus =>
    signedIn()
      ? (publishedStatus ?? {
          state: "ready",
          agent_version: "0.0.0-fixture",
          lane: "development",
        })
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

  /** The steps of a tool the agent calls, through `states`. What it took and
   * gave, `details`, only the history serves, as the agent records it. */
  const tool = (
    held: Reply,
    title: string,
    tool_kind: AgentStreamToolCall["tool_kind"],
    states: readonly ToolCallStatus[],
    refusal?: AgentToolRefusal,
    details?: string[],
  ) => {
    const call = toolCall(id("t"), title, tool_kind);
    return states.map((state) => () => {
      const now = atState(call, state);
      const at = held.run.tools.findIndex((held) => held.id === call.id);
      const recorded = details ? { ...now, details } : now;
      if (at < 0) held.run.tools.push(recorded);
      else held.run.tools[at] = recorded;
      held.sequence += 1;
      emit(held, {
        type: "tool",
        reply_id: held.run.id,
        // Only the update that ends the call failed carries the refusal.
        tool: refusal && state === "failed" ? { ...now, refusal } : now,
      });
    });
  };

  /** The step of a thought the agent shares on the way: only the stream
   * carries it, and the history keeps none. */
  const think = (held: Reply, words: string) => () =>
    emit(held, {
      type: "thought",
      reply_id: held.run.id,
      message_id: `${held.run.id}:thought`,
      sequence: ++held.sequence,
      delta: words,
    });

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
    if (MODEL_UNAVAILABLE.test(text)) {
      schedule(held, [
        started(held),
        () => settle(held.run.id, "failed", MODEL_UNAVAILABLE_WHY),
      ]);
      return;
    }
    if (
      FAILS_FIRST.test(text) ||
      AUTHENTICATION_REQUIRED.test(text) ||
      RUN_OUTGROWS_MODEL.test(text) ||
      UNEXPECTED_PROVIDER_CONDITION.test(text)
    ) {
      // It fails before the agent wrote anything.
      const why = AUTHENTICATION_REQUIRED.test(text)
        ? {
            provider_condition: "unauthenticated" as const,
            failure_reason: "Internal provider error: auth_required.",
          }
        : RUN_OUTGROWS_MODEL.test(text)
          ? {
              provider_condition: "model_does_not_fit" as const,
              failure_reason:
                "Internal provider error: context exceeds memory.",
            }
          : UNEXPECTED_PROVIDER_CONDITION.test(text)
            ? {
                // The fixture deliberately sends a value outside the declared
                // union to prove unknown conditions stay safe at the UI edge.
                provider_condition:
                  "unexpected_internal_condition" as NonNullable<
                    FixtureRun["provider_condition"]
                  >,
                failure_reason:
                  "Internal provider error: permission_requests.subagent_id missing.",
              }
            : {
                provider_condition: "provider_overloaded" as const,
                failure_reason: "The provider answered 529 overloaded_error.",
              };
      schedule(held, [started(held), () => settle(held.run.id, "failed", why)]);
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
    const barred =
      asks === "approval"
        ? barredAsk(text, held.run.id, id, barredReads)
        : null;
    if (barred) {
      let open = barred.length;
      schedule(held, [
        started(held),
        ...write(held, "Voy a leer los archivos adjuntos."),
        ...barred.map((approval) =>
          park(held, {
            kind: "approval",
            approval,
            then: () => {
              open -= 1;
              if (open > 0) return;
              goOn([
                () => {
                  held.run.status = "running";
                },
                ...write(held, "No he podido leer los archivos."),
                finish(held),
              ]);
            },
          }),
        ),
      ]);
      return;
    }
    if (asks === "approval") {
      const title = "Leer los apuntes del libro";
      // A message asks for the permission the agent gives least to go on,
      // or the most it can.
      const unnamed = /sin nombres/i.test(text);
      const most = /extremos/i.test(text);
      // The agent says a tool's name and a line that repeats it, and serves
      // nothing of the call's input.
      const canonical =
        /permission (status|file|attachment|operation|web)/.exec(text);
      const target = canonical ? PERMISSION_TARGETS[canonical[1]!] : undefined;
      const toolName = target?.tool ?? "ledger_list";
      schedule(held, [
        started(held),
        ...write(held, "Para eso necesito tu permiso."),
        park(held, {
          kind: "approval",
          approval: requested({
            request_id: id("p"),
            reply_id: held.run.id,
            source: "agent_tool",
            tool_call: unnamed ? null : most ? MOST_TOOL_CALL : toolName,
            tool_kind: unnamed ? null : target ? "other" : "read",
            tool_server: unnamed ? null : target ? target.server : "cadrumo",
            description: unnamed
              ? null
              : most
                ? MOST_DESCRIPTION
                : (target?.description ?? `Permission required: ${toolName}`),
            options: unnamed
              ? UNNAMED_OPTIONS
              : most
                ? MOST_OPTIONS
                : target
                  ? CANONICAL_OPTIONS
                  : TOOL_OPTIONS,
          }),
          then: (option) =>
            goOn(
              option.kind.startsWith("allow")
                ? [
                    () => {
                      held.run.status = "running";
                    },
                    ...tool(held, title, "read", [
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
    const refused = TOOL_REFUSALS.find(([asked]) => asked.test(text));
    if (refused) {
      const [, title, refusal] = refused;
      schedule(held, [
        started(held),
        ...write(held, "Lo intento con la herramienta."),
        ...tool(
          held,
          title,
          "fetch",
          ["pending", "in_progress", "failed"],
          refusal,
        ),
        ...write(held, "La herramienta no ha podido seguir."),
        finish(held),
      ]);
      return;
    }
    const linked = LINK_TO.exec(text.trim());
    if (linked) {
      schedule(held, [
        started(held),
        ...write(held, `[el enlace](${linked[1]})`),
        finish(held),
      ]);
      return;
    }
    const links = LINK_REPLIES.find(([asked]) => asked.test(text));
    if (links) {
      schedule(held, [started(held), ...write(held, links[1]), finish(held)]);
      return;
    }
    if (RICH.test(text)) {
      schedule(held, [
        started(held),
        think(held, RICH_THOUGHTS[0] ?? ""),
        ...write(held, "Lo miro en tus apuntes."),
        ...tool(
          held,
          "ledger_list",
          "read",
          ["pending", "in_progress", "completed"],
          undefined,
          RICH_TOOL_DETAILS,
        ),
        think(held, ` ${RICH_THOUGHTS[1] ?? ""}`),
        ...write(held, RICH_REPLY),
        finish(held),
      ]);
      return;
    }
    schedule(held, [
      started(held),
      ...write(held, "Lo miro en tus apuntes."),
      ...tool(
        held,
        toolTitle(text),
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

  /** Whether the catalog served now says this computer lacks the model a
   * run names, as cadrumo-agent's run start refuses it. */
  const notHeld = (request: AgentSendRequest): boolean => {
    const { provider, transport, model } = request.selection;
    const served = models ? models.report(FIXTURE_CATALOG) : FIXTURE_CATALOG;
    return (served.providers ?? []).some(
      (held) =>
        held.provider_id === provider &&
        held.transport === transport &&
        held.catalog.models?.some(
          (entry) => entry.model === model && entry.installed === false,
        ),
    );
  };

  /** What a run ran with, by the display names its lane's catalog gives. */
  const ranWith = (request: AgentSendRequest): AgentRanWith => {
    const { provider, transport, model, effort } = request.selection;
    const lane = (FIXTURE_CATALOG.providers ?? []).find(
      (held) => held.provider_id === provider && held.transport === transport,
    );
    const entry = lane?.catalog.models?.find((held) => held.model === model);
    return {
      provider: lane?.provider_id ?? null,
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
    ...(documents === "unavailable"
      ? {}
      : {
          async documents(query) {
            say(
              `agentDocuments ${query.conversation_id}${query.after ? ` after ${query.after}` : ""}`,
            );
            await check();
            if (documents === "failed")
              throw coded("agent_gateway_attachments_unavailable");
            const q = query.q?.toLowerCase() ?? "";
            const after = query.after;
            const matching = stored(query.conversation_id).filter(
              (document) =>
                (after === undefined || document.name > after) &&
                document.name.toLowerCase().includes(q),
            );
            const page = matching.slice(0, DOCUMENT_PAGE);
            return {
              documents: structuredClone(page),
              next_after:
                matching.length > DOCUMENT_PAGE
                  ? (page.at(-1)?.name ?? null)
                  : null,
            };
          },
        }),
  };

  const session: AgentSession = {
    async retry() {
      say("agentRetry");
      await wait();
    },
    async status() {
      window.__fixtureAgentSession = session;
      window.__fixtureAgentViews = agent;
      say("agentStatus");
      await wait();
      const answer = status();
      say("agentStatusResolved");
      return answer;
    },
    async observeStatus(listener) {
      say("agentObserveStatus");
      // Like every host call it takes the host's time. The host then takes
      // over as the one listener and sends the current status before the
      // subscription resolves.
      await wait();
      statusListener = listener;
      listener(status());
      return () => {
        if (statusListener === listener) statusListener = null;
      };
    },
    ...modelHost.methods,
    ...(skills === "unavailable"
      ? {}
      : {
          async skills() {
            say("agentSkills");
            await check();
            if (skills === "failed")
              throw coded("agent_gateway_skills_unavailable");
            return {
              revision: FIXTURE_SKILLS_REVISION,
              skills: structuredClone([...inventory]),
            };
          },
          async skill(name: string) {
            say(`agentSkill ${name}`);
            await check();
            return fixtureSkillDetail(knownSkill(name));
          },
          async verifySkill(name: string) {
            say(`agentSkillVerify ${name}`);
            await check();
            return fixtureSkillVerification(knownSkill(name));
          },
        }),
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
    ...(documents === "unavailable"
      ? {}
      : {
          // The picker always picks the same three files: one the storage
          // takes, one the host refuses before sending anything, and one the
          // storage refuses once it is sent.
          async observeDrops(listener) {
            say("agentObserveDrops");
            await check();
            window.__fixtureAgentDrop = listener;
            return () => {
              if (window.__fixtureAgentDrop === listener)
                delete window.__fixtureAgentDrop;
            };
          },
          async removeDocuments(conversationId, name) {
            say(`agentRemoveDocuments ${conversationId} ${name ?? "all"}`);
            await check();
            if (name === undefined) storage.delete(conversationId);
            else {
              if (
                !stored(conversationId).some(
                  (document) => document.name === name,
                )
              )
                throw coded("agent_gateway_attachment_not_found");
              storage.set(
                conversationId,
                stored(conversationId).filter(
                  (document) => document.name !== name,
                ),
              );
            }
          },
          async attachmentPolicy() {
            await check();
            return FIXTURE_ATTACHMENT_POLICY;
          },
          ...fixtureMovementAttach(say, check, storage, readMovement),
          async attach(conversationId, filterLabel, onEvent, dropId) {
            say(`agentAttach ${conversationId} ${filterLabel}`);
            if (dropId) say(`agentAttachDrop ${conversationId} ${dropId}`);
            await check();
            const ids = [id("upload"), id("upload"), id("upload")] as const;
            const timer = (ms: number, then: () => void) =>
              window.setTimeout(then, ms);
            timer(UPLOAD_STEP_MS, () =>
              onEvent({ kind: "progress", id: ids[0], sent: 60_000 }),
            );
            timer(UPLOAD_STEP_MS * 2, () => {
              const document: AgentDocumentRecord = {
                name: "recibo-luz.pdf",
                size_bytes: 120_000,
                modified_at: new Date().toISOString(),
                sha256: "a".repeat(64),
                media_type: "application/pdf",
              };
              const held = stored(conversationId).filter(
                (kept) => kept.name !== document.name,
              );
              storage.set(
                conversationId,
                [...held, document].sort((a, b) =>
                  a.name < b.name ? -1 : a.name > b.name ? 1 : 0,
                ),
              );
              onEvent({ kind: "stored", id: ids[0], document });
            });
            timer(UPLOAD_STEP_MS * 3, () =>
              onEvent({
                kind: "refused",
                id: ids[2],
                code: "agent_gateway_attachment_quota_exceeded",
              }),
            );
            return [
              {
                id: ids[0],
                name: "recibo-luz.pdf",
                size_bytes: 120_000,
                state: "queued",
                code: null,
              },
              {
                id: ids[1],
                ...pickedRefusal(),
                state: "refused",
              },
              {
                id: ids[2],
                name: "escaneo-anual.pdf",
                size_bytes: 3_400_000,
                state: "queued",
                code: null,
              },
            ];
          },
        }),
    async send(request) {
      window.__fixtureAgentSession = session;
      const { provider, transport } = request.selection;
      say(
        `agentSend ${request.conversation_id} ${provider}/${transport}${
          request.attachments?.length
            ? ` attachments ${request.attachments.map((named) => named.name).join("|")}`
            : ""
        }`,
      );
      await check();
      const conversationId = request.conversation_id;
      const { text } = request;
      if (request.skills) {
        say(`agentSendSkills ${request.skills.join(",")}`);
        for (const name of request.skills) knownSkill(name);
      }
      const runs = runsIn(conversationId);
      const last = runs.at(-1);
      // The host checks a message before it asks the agent anything.
      if (text.trim() === "" || characters(text) > MESSAGE_MAX)
        throw coded("agent_invalid_request");
      // A reply still going takes no second message, and none is queued.
      if ((last && isLiveStatus(last.status)) || BUSY_ELSEWHERE.test(text))
        throw coded("agent_reply_in_progress");
      const carried = admitted(say, runsOf, request);
      // A model this computer does not hold is refused before a run starts.
      if (notHeld(request)) throw coded("agent_gateway_model_not_installed");
      // A model this computer cannot run is refused the same way.
      if (MODEL_DOES_NOT_FIT.test(text))
        throw coded("agent_gateway_model_does_not_fit");
      // A lane whose provider lost its key is refused before a run starts.
      if (PROVIDER_CREDENTIAL_MISSING.test(text))
        throw coded("agent_provider_credential_missing");
      // Each named document is read where the conversation stored it, as
      // it was when it was named.
      const named: AgentDocumentReference[] = [];
      for (const reference of request.attachments ?? []) {
        const held = stored(conversationId).find(
          (document) => document.name === reference.name,
        );
        if (!held) throw coded("agent_gateway_attachment_not_found");
        if (held.sha256 !== reference.sha256)
          throw coded("agent_gateway_attachment_changed");
        named.push({
          name: held.name,
          sha256: held.sha256,
          media_type: held.media_type,
        });
      }
      const sentAt = new Date().toISOString();
      const fresh: FixtureRun = {
        // The first run of a conversation has the conversation's id.
        id: last ? id("r") : conversationId,
        status: "running",
        messages: seeded(last?.messages ?? carried?.seeded ?? [], [
          {
            role: "user",
            text,
            sent_at: sentAt,
            ...(named.length > 0 ? { attachments: named } : {}),
            ...(request.skills?.length ? { skills: request.skills } : {}),
          },
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
      return {
        reply_id: fresh.id,
        ...(carried ? { carry: carried.carry } : {}),
      };
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
    async delete(conversationId) {
      say(`agentDelete ${conversationId}`);
      await check();
      const index = conversations.findIndex(
        (held) => held.id === conversationId,
      );
      if (index < 0) throw coded("agent_conversation_unknown");
      for (const held of [...replies.values()]) {
        if (held.conversationId === conversationId) {
          for (const timer of held.timers) window.clearTimeout(timer);
          settle(held.run.id, "cancelled");
        }
      }
      conversations.splice(index, 1);
      delete runsOf[conversationId];
      storage.delete(conversationId);
    },
    async rename(conversationId, title) {
      say(`agentRename ${conversationId}`);
      await check();
      const named = title.trim();
      if (!named || [...named].length > 200 || /\p{Cc}/u.test(named))
        throw coded("agent_invalid_request");
      const record = conversations.find((held) => held.id === conversationId);
      if (!record) throw coded("agent_conversation_unknown");
      record.title = named;
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
    // The fixture's lanes stay on this computer, so its reads need no grant.
    attachmentCard: ({ request_id }) =>
      Promise.resolve(barredCard(barredReads, request_id)),
    attachmentRelease: () => Promise.resolve({ kind: "not_required" as const }),
    attachmentGrants: () =>
      Promise.resolve({ kind: "grants" as const, grants: [] }),
    attachmentGrantRevoke: () =>
      Promise.resolve({
        kind: "refused" as const,
        code: "grant_revoked",
        name: null,
      }),
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

  const publishStatus = (next?: AgentServiceStatus) => {
    publishedStatus = next ?? null;
    const ready = next === undefined || next.state === "ready";
    if (catalog !== "busy-past-ready") modelHost.state.busy = false;
    else if (ready)
      window.setTimeout(() => {
        modelHost.state.busy = false;
      }, BUSY_PAST_READY_MS);
    // A declared catalog gives way to the served one once the agent is ready.
    if (ready) modelHost.state.declared = false;
    statusListener?.(status());
  };
  // Each status the host sends is a new object, as one read off its channel is.
  const republishStatus = () => statusListener?.({ ...status() });
  return {
    agent,
    session,
    publishStatus,
    republishStatus,
    changeListElsewhere: modelHost.changeListElsewhere,
    selectedEngine: modelHost.selectedEngine,
  };
}
