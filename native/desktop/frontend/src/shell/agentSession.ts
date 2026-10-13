import type { AgentConversationRecord, AgentTurnRecord } from "./agentViews";

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

/** Why the agent service is not serving, as a stable code. */
export type AgentServiceRefusal =
  | "agent_service_absent"
  | "agent_service_incompatible"
  | "agent_signed_out"
  | "agent_runtime_unavailable"
  | "agent_provider_credential_missing"
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
// can do.

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

/** One way of running one provider, its health and its models. */
export type AgentProviderLane = {
  provider_id: string;
  display_name: string;
  execution_mode: string;
  executable: boolean;
  model_source: "catalog" | "declared";
  aliases?: string[];
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
    /** The model entry the proof is for; none for the whole lane. */
    entry?: string | null;
    state: AgentLaneVerification;
  }[];
};

/** cadrumo-agent's provider catalog: every lane it knows, runnable or not. */
export type AgentProviderCatalog = {
  api_version?: string;
  providers?: AgentProviderLane[];
};

/** What a turn runs with: a lane and one of its models, as the catalog
 * names them. `provider`, `model` and `effort` are what a run takes. */
export type AgentSelectionRecord = {
  provider: string;
  execution_mode: string;
  entry_id: string;
  model: string;
  effort?: AgentEffort;
  /** The native controls chosen, by control id. */
  controls?: { control_id: string; option_id: string }[];
};

/** One message the person sends. */
export type AgentSendRequest = {
  conversation_id: string;
  text: string;
  selection: AgentSelectionRecord;
  /** Documents of the conversation this message refers to. */
  document_ids?: string[];
};

/** What a send started: the person's turn as history will keep it, and
 * the handle of the reply the stream reports on. */
export type AgentSendResult = {
  person_turn: Extract<AgentTurnRecord, { kind: "person" }>;
  /** A handle for the whole reply, which may span several agent and tool
   * turns. It is no turn's id. */
  reply_id: string;
};

/** One question the agent asks the person: a choice among its options, or
 * free text. */
export type AgentQuestion = {
  id: string;
  prompt: string;
  kind: "choice" | "text";
  /** The options of a choice, answered with exactly one of them verbatim. */
  options?: string[];
  required: boolean;
};

/** Up to four questions the agent asks together; the reply waits until the
 * person answers them, sends a new message instead, or declines. */
export type AgentQuestionnaire = {
  request_id: string;
  reply_id: string;
  questions: AgentQuestion[];
};

/** How the person answers a questionnaire. */
export type AgentQuestionnaireAnswer =
  | { kind: "answers"; answers: Record<string, string> }
  | { kind: "message"; text: string }
  | { kind: "decline" };

/** What answering a questionnaire added to the conversation: the person's
 * message, when they answered with one, as history will keep it. */
export type AgentAnswerResult = {
  person_turn?: Extract<AgentTurnRecord, { kind: "person" }>;
};

/** What an approval would let happen, as its source states it. */
export type AgentApprovalOption = {
  option_id: string;
  /** The option's name as the source words it. */
  name: string;
  kind: "allow_once" | "allow_always" | "reject_once" | "reject_always";
};

/** Something the reply cannot do until the person decides: a tool the agent
 * wants to call, or a Cadrumo operation's review before it commits. Only a
 * deliberate gesture of the person answers it; no tool the model can call
 * does. */
export type AgentApproval = {
  request_id: string;
  reply_id: string;
  source: "agent_tool" | "cadrumo_review";
  /** What would run, as its source names it. */
  title: string;
  description: string;
  options: AgentApprovalOption[];
};

/** One change to a conversation while it is watched. A reply is a run of
 * turns in order: agent text, a tool, more agent text. Every turn id and
 * tool id streamed here is the id history() returns for that record, so a
 * reload replaces nothing. */
export type AgentStreamEvent =
  | { type: "reply_started"; reply_id: string }
  | {
      type: "text";
      reply_id: string;
      /** The agent turn this text belongs to. Text after a tool arrives
       * under a new turn id, which starts a new agent turn. */
      turn_id: string;
      /** Where in that turn's text the delta begins, in UTF-16 code units.
       * A delta whose offset is not the length already held is a
       * duplicate (smaller) or a gap (larger); a gap means read the
       * history again. */
      offset: number;
      /** Text to append to the turn. */
      delta: string;
    }
  | {
      type: "tool";
      reply_id: string;
      /** The tool turn, whole, each time its state changes. */
      tool: Extract<AgentTurnRecord, { kind: "tool" }>;
    }
  | { type: "questions"; reply_id: string; questionnaire: AgentQuestionnaire }
  | { type: "approval"; reply_id: string; approval: AgentApproval }
  /** A questionnaire or approval is answered, here or elsewhere, and is no
   * longer pending. */
  | { type: "resolved"; reply_id: string; request_id: string }
  | {
      type: "settled";
      reply_id: string;
      state: "complete" | "stopped" | "failed";
      failure_reason?: string;
    }
  /** The stream cannot go on; the column reads the history again. */
  | { type: "lost"; reply_id?: string };

/** The agent actions a host offers. Every call is refused while nobody is
 * signed in; failures carry a stable code. */
export interface AgentSession {
  status(): Promise<AgentServiceStatus>;
  /** Cleanup cannot remove a newer subscriber. */
  observeStatus(
    listener: (status: AgentServiceStatus) => void,
  ): Promise<() => void>;
  /** cadrumo-agent's provider catalog, as it serves it. */
  providerCatalog(): Promise<AgentProviderCatalog>;
  /** A new, empty conversation of the signed-in profile. */
  startConversation(): Promise<AgentConversationRecord>;
  /** Sends the person's message: pressing Send is their decision, and
   * nothing asks them again. */
  send(request: AgentSendRequest): Promise<AgentSendResult>;
  /** Stops a reply that is still working; it settles as `stopped`. */
  cancel(replyId: string): Promise<void>;
  /** What the conversation's unfinished reply waits on, so a reload shows
   * the same questions and approvals the stream raised. */
  pending(conversationId: string): Promise<{
    questionnaires: AgentQuestionnaire[];
    approvals: AgentApproval[];
  }>;
  answerQuestions(
    questionnaire: Pick<AgentQuestionnaire, "reply_id" | "request_id">,
    answer: AgentQuestionnaireAnswer,
  ): Promise<AgentAnswerResult>;
  decideApproval(
    approval: Pick<AgentApproval, "reply_id" | "request_id">,
    optionId: string,
  ): Promise<void>;
  /** Watches one conversation. Read history() first: it holds the newest
   * agent turn of an unfinished reply as `working`, with its text so far,
   * and every earlier turn of that reply as settled; the offsets of later
   * text events continue from it. Cleanup cannot remove a newer
   * subscriber. */
  observe(
    conversationId: string,
    listener: (event: AgentStreamEvent) => void,
  ): Promise<() => void>;
}
