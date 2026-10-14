import type {
  AgentConversationRecord,
  AgentProviderCondition,
  AgentToolCall,
} from "./agentViews";

// What a host offers for working with the agent, beside the reads in
// agentViews: the service's state, the providers and models it can run,
// sending a turn, the live stream of a conversation, and stopping a reply. A
// host that cannot serve these offers none of them, and the column shows
// sending as not available yet. Records are raw values on the wire,
// snake_case, worded by the column in the chrome locale.
//
// Sending a message is the person's own act and is never asked about again.
// What waits on the person's decision is what the agent would do: a tool
// call, or a Cadrumo operation's review, each an approval.
//
// A conversation is a chain of cadrumo-agent runs, and its id is the first
// run's. A reply is one run: its id is the reply's handle, and a message that
// continues a settled conversation starts a new run, so the next reply has a
// new handle.

/** Why the agent service is not serving, as a stable code. They are the
 * desktop launcher's own vocabulary, not cadrumo-agent's. */
export type AgentServiceRefusal =
  | "agent_service_absent"
  | "agent_service_incompatible"
  | "agent_signed_out"
  | "agent_runtime_unavailable"
  | "agent_provider_credential_missing"
  /** The agent's root is not marked as the development lane's. */
  | "agent_root_unmarked"
  | "agent_service_failed";

/** Where the agent service of the signed-in profile is. */
export type AgentServiceStatus = (
  | { state: "stopped" }
  | { state: "starting" }
  | {
      state: "ready";
      /** The agent's own version, as its package names it. */
      agent_version: string;
    }
  | { state: "refused"; code: AgentServiceRefusal }
) & {
  /** Present on a development live lane, whose conversations are kept
   * unencrypted on a disposable test root. The column says so in every
   * state while it is present. */
  lane?: "development";
};

// The providers, models and what each can do are cadrumo-agent's own
// provider catalog, field for field as its `/v1/provider-catalog` serves it:
// the host relays the answer and the column deduces every choice from it.
// Nothing here names a provider, a model, an effort a model takes or what it
// can do. Each record is one lane: one provider reached over its API or its
// command-line app.

/** One axis of a lane's health. */
export type AgentHealthState = "available" | "unavailable" | "unknown";

export type AgentAuthenticationState =
  "authenticated" | "unauthenticated" | "unknown" | "not_applicable";

export type AgentCatalogStatus =
  "available" | "unavailable" | "stale" | "unknown";

export type AgentAdmissionState =
  "admitted" | "unproven" | "not_admitted" | "unknown";

/** How much reasoning a run asks its model for, lowest first. Which of these
 * a model accepts is the model's own, in its catalog entry. */
export type AgentEffort = "low" | "medium" | "high" | "xhigh" | "max" | "ultra";

/** A capability a lane has, or has not, been proven to have. */
export type AgentLaneCapability =
  "tool_access" | "writing" | "web_retrieval" | "image_reading" | "pdf_reading";

export type AgentLaneVerification =
  "proven" | "unproven_version" | "unproven" | "not_applicable";

/** One model a lane offers, as its catalog lists it. */
export type AgentCatalogEntry = {
  entry_id: string;
  /** The model's id, as a run names it. */
  model: string;
  display_name: string;
  description?: string | null;
  capabilities?: string[];
  /** The lane's native controls this model takes. */
  native_control_ids?: string[];
  /** The efforts this model accepts; none when it takes no effort. */
  efforts?: AgentEffort[];
  default_effort?: AgentEffort | null;
};

export type AgentNativeControlOption = {
  option_id: string;
  display_name: string;
  description?: string | null;
};

/** A setting of the lane's own, such as a model configuration or a
 * service tier, that some of its models take. */
export type AgentNativeControl = {
  control_id: string;
  kind: "model_config" | "thought_level" | "service_tier" | "other";
  display_name: string;
  options?: AgentNativeControlOption[];
  default_option_id?: string | null;
  description?: string | null;
};

/** How a lane reaches its provider: the provider's web API, or its own
 * command-line app on this computer. */
export type AgentTransport = "api" | "cli";

/** One way of running one provider, its health and its models. */
export type AgentProviderLane = {
  /** The provider, as cadrumo-agent names it: one for every lane that
   * reaches it, whichever way. */
  provider_id: string;
  transport: AgentTransport;
  /** The provider's product name, the same on each of its lanes. */
  display_name: string;
  execution_mode: string;
  executable: boolean;
  /** `catalog`: the lane lists its models and a run names one of them.
   * `declared`: it lists none and a run's model id is passed on as given. */
  model_source: "catalog" | "declared";
  health: {
    configured: AgentHealthState;
    transport: AgentHealthState;
    authentication: AgentAuthenticationState;
    catalog: AgentCatalogStatus;
    admission: AgentAdmissionState;
    selectable: boolean;
    reasons?: string[];
    checked_at: string;
  };
  catalog: {
    schema_version?: number;
    state: {
      status: AgentCatalogStatus;
      checked_at: string;
      revision?: string | null;
      expires_at?: string | null;
      reason?: string | null;
    };
    recommended_entry_id?: string | null;
    models?: AgentCatalogEntry[];
    native_controls?: AgentNativeControl[];
  };
  capability_proofs?: {
    capability: AgentLaneCapability;
    /** The tool server the proof is for: given for tool access and for
     * writing, and for no other capability. It is not a model. */
    entry?: string | null;
    state: AgentLaneVerification;
  }[];
};

/** cadrumo-agent's provider catalog: every lane it knows, runnable or not. */
export type AgentProviderCatalog = {
  api_version?: string;
  providers?: AgentProviderLane[];
};

/** What a turn runs with, field for field what cadrumo-agent's run start
 * takes of an agent (`AgentSpec`): the provider and the way into it, the model
 * as the catalog names it for a run, and the effort. It takes nothing else:
 * not the lane's execution mode or a catalog entry, which the service resolves
 * itself, and not a model's native controls. */
export type AgentSelectionRecord = {
  provider: string;
  transport: AgentTransport;
  model: string;
  effort?: AgentEffort;
};

/** One message the person sends, of one to 65536 characters that say
 * something (cadrumo-agent's `message`, `content` and `prompt`). No document
 * goes with it: Cadrumo serves none to the agent yet. */
export type AgentSendRequest = {
  conversation_id: string;
  text: string;
  selection: AgentSelectionRecord;
};

/** What a send started. cadrumo-agent names no id for the person's message,
 * so the column shows it as sent until history has it. */
export type AgentSendResult = {
  /** The run the message started: the handle of the reply the stream reports
   * on. It is the id history gives the reply's records as `reply_id`. */
  reply_id: string;
};

// A questionnaire and an approval are cadrumo-agent's own, field for field as
// it serves them: a run's `pending_clarification`, and its `permission_request`
// frame. Their bounds are the agent's (see agentClarification); the host maps
// what the agent serves onto these, and the column holds to them.

/** One question the agent asks the person: a choice among its options, or
 * free text. cadrumo-agent's `ClarificationQuestion`. */
export type AgentQuestion = {
  /** One to 64 of `A-Z a-z 0-9 _ . -`, not starting with a dot or a hyphen.
   * The answers are keyed by it. */
  id: string;
  /** One to 512 characters, on one line. */
  prompt: string;
  kind: "choice" | "text";
  /** A choice's one to four distinct options of one to 128 characters each,
   * answered with exactly one of them as written. A text question has none. */
  options?: string[] | null;
  /** Whether it must be answered; it must be when this is absent. */
  required?: boolean;
};

/** One to four questions the agent asks together; the reply waits until the
 * person answers them, sends a new message instead, or declines.
 * `request_id` is cadrumo-agent's `ClarificationRequest.request_id`;
 * `reply_id` is the run it belongs to, which an answer is addressed to. */
export type AgentQuestionnaire = {
  request_id: string;
  reply_id: string;
  questions: AgentQuestion[];
};

/** How the person resolves a questionnaire: one of cadrumo-agent's three
 * resolutions. */
export type AgentQuestionnaireAnswer =
  /** `clarification_response`: the answers by question id, at most four, each
   * of at most 2048 characters on one line. A question left unanswered is
   * left out; only a required one must be answered. */
  | { kind: "answers"; answers: Record<string, string> }
  /** `clarification_continuation`: a new message that continues the same run
   * in place of the answers, sent as the continuation's `prompt`. It says
   * something, and is at most 65536 characters. */
  | { kind: "message"; text: string }
  /** `clarification_decline`: no answer, and the run goes on on its own
   * judgement. Nothing else is sent. */
  | { kind: "decline" };

/** What answering a questionnaire gives back: nothing. The run goes on under
 * the reply it already has, and an answer in words is shown as sent until
 * history has it, as a send is. */
export type AgentAnswerResult = Record<string, never>;

/** One way of deciding an approval, as the agent offers it: cadrumo-agent's
 * permission option. */
export type AgentApprovalOption = {
  /** What a decision names; at most 64 characters. */
  option_id: string;
  /** The option's own name, at most 128 characters. It may be empty. */
  name?: string | null;
  /** What choosing the option does, which decides its place and emphasis:
   * allowing or refusing, this call or later ones too. The agent offers an
   * option it would remember only when it offers nothing else; the column
   * leaves such an option out beside any that answers this call alone. */
  kind: "allow_once" | "allow_always" | "reject_once" | "reject_always";
};

/** What a tool does, as cadrumo-agent classes it. */
export type AgentToolKind =
  | "read"
  | "edit"
  | "delete"
  | "move"
  | "search"
  | "execute"
  | "think"
  | "fetch"
  | "switch_mode"
  | "other";

/** Something the reply cannot do until the person decides: a tool the agent
 * wants to call, or a Cadrumo operation's review before it commits. Only a
 * deliberate gesture of the person answers it; no tool the model can call
 * does. `source` is Cadrumo's own; the rest is cadrumo-agent's
 * `permission_request`. */
export type AgentApproval = {
  request_id: string;
  reply_id: string;
  source: "agent_tool" | "cadrumo_review";
  /** The tool the agent wants to call, as the agent names it, or the
   * operation under review. Absent when its source names none. */
  tool_call?: string | null;
  /** What kind of tool it is, one of cadrumo-agent's ten. The card words it. */
  tool_kind?: AgentToolKind | null;
  /** Up to 4096 characters. The agent's is a fixed line naming the tool, and
   * it serves no input of the call: the person decides on the tool's name
   * alone, and nothing here may suggest otherwise. */
  description?: string | null;
  /** What the person can decide, one to sixteen options. A decision is the id
   * of one of them. */
  options: AgentApprovalOption[];
};

/** One change to a conversation while it is watched, per reply (a run of
 * cadrumo-agent). A reply's text and tool calls are listed by the same ids
 * history() lists them under. A reply's text is one message, however many tool
 * calls come between its parts: text after a tool is more of the same message.
 *
 * The host takes a run's frames in order and tells what its stream cannot:
 * `reply_started` and `resolved` are its own (the agent sends no such frames),
 * and `lost` is sent only when a stream could not be resumed. */
export type AgentStreamEvent =
  /** The host's, before the first frame it maps of a run. */
  | { type: "reply_started"; reply_id: string }
  | {
      type: "text";
      reply_id: string;
      /** cadrumo-agent's `message_id` of the chunk: the message the text
       * belongs to. */
      message_id: string;
      /** The frame's `sequence` in the run's stream. Text is applied in the
       * order of its sequence, and one whose sequence is no greater than the
       * last applied is a duplicate and is dropped. */
      sequence: number;
      /** Text to append to the message. */
      delta: string;
    }
  | {
      type: "tool";
      reply_id: string;
      /** The tool call, whole, each time it changes. */
      tool: AgentToolCall;
    }
  /** The agent's own frame (`clarification_pending`) is only a nudge that
   * names the request; the host reads the questionnaire from the run's
   * status (`pending_clarification`) and raises it here whole. */
  | { type: "questions"; reply_id: string; questionnaire: AgentQuestionnaire }
  /** From the agent's `permission_request` frame. */
  | { type: "approval"; reply_id: string; approval: AgentApproval }
  /** A questionnaire or approval is answered, here or elsewhere, and is no
   * longer pending. The agent sends no such frame: the host raises it on
   * its own successful answer, or when the run settles with it pending. */
  | { type: "resolved"; reply_id: string; request_id: string }
  /** The agent's `thread_terminal` frame: the run's final status, and for a
   * failed run its provider condition and reason. It is not sent between a
   * turn and a message queued behind it. */
  | {
      type: "settled";
      reply_id: string;
      status: "completed" | "failed" | "cancelled";
      provider_condition?: AgentProviderCondition | null;
      failure_reason?: string | null;
    }
  /** The host resumed the stream after its last frame and the agent could not
   * replay what was missed, or the stream was refused. The column reads the
   * history and what is pending again, and watches the conversation anew. */
  | { type: "lost"; reply_id?: string };

/** The agent actions a host offers. Every call is refused while nobody is
 * signed in; failures carry a stable code. */
export interface AgentSession {
  status(): Promise<AgentServiceStatus>;
  /** Retry service startup after correcting a failure. */
  retry?(): Promise<void>;
  /** Cleanup cannot remove a newer subscriber. */
  observeStatus(
    listener: (status: AgentServiceStatus) => void,
  ): Promise<() => void>;
  /** cadrumo-agent's provider catalog, as it serves it. */
  providerCatalog(): Promise<AgentProviderCatalog>;
  /** A new conversation of the signed-in profile: the id its first run will
   * have, reserved by the host. No run exists behind it until the first
   * message is sent. */
  startConversation(): Promise<AgentConversationRecord>;
  /** Sends the person's message: pressing Send is their decision, and
   * nothing asks them again. It starts a run, a new one when the
   * conversation's last run has settled. A send while a reply of the
   * conversation is still live is refused with `agent_reply_in_progress`:
   * nothing is queued. */
  send(request: AgentSendRequest): Promise<AgentSendResult>;
  /** Stops a reply that is still working. The run is `cancelling` until it
   * is `cancelled`. */
  cancel(replyId: string): Promise<void>;
  /**
   * Archives the conversation: every run of its chain, which cadrumo-agent
   * archives one at a time and only once it has settled. It cannot be undone:
   * the agent has no way to unarchive. A conversation with a live reply is
   * refused with `agent_reply_in_progress`. Absent where the host offers no
   * archiving.
   */
  archive?(conversationId: string): Promise<void>;
  /** What the conversation's unfinished reply waits on, so a reload shows
   * the same questions and approvals the stream raised. */
  pending(conversationId: string): Promise<{
    questionnaires: AgentQuestionnaire[];
    approvals: AgentApproval[];
  }>;
  /** Resolves a questionnaire. An answer the agent would not take is refused
   * with the status it answered with (`agent_gateway_422`), and a question
   * that is no longer pending with `agent_gateway_404`: the agent explains a
   * refusal in prose, never in a code, and the host passes on only its
   * status. */
  answerQuestions(
    questionnaire: Pick<AgentQuestionnaire, "reply_id" | "request_id">,
    answer: AgentQuestionnaireAnswer,
  ): Promise<AgentAnswerResult>;
  /** Decides an approval with the id of one of its options. An option it did
   * not offer is refused as a conflict (`agent_gateway_409`), and a request
   * that is no longer pending as `agent_gateway_404`. */
  decideApproval(
    approval: Pick<AgentApproval, "reply_id" | "request_id">,
    optionId: string,
  ): Promise<void>;
  /**
   * Watches one conversation: the stream of its live run, if it has one, and
   * of the run a later send starts. A reply in progress is not in history():
   * cadrumo-agent records a message when its turn ends. Its text so far is
   * what the stream replays from the run's first retained frame, so a new
   * watch gets it again, and the column applies it by sequence. Cleanup
   * cannot remove a newer subscriber.
   */
  observe(
    conversationId: string,
    listener: (event: AgentStreamEvent) => void,
  ): Promise<() => void>;
}
