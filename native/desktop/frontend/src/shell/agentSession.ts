import type { AgentConversationRecord, AgentTurnRecord } from "./agentViews";

// What a host offers for working with the agent, beside the reads in
// agentViews: the service's state, the providers and models it can run,
// consent, sending a turn, the live stream of a conversation, and stopping a
// reply. A host that cannot serve these offers none of them, and the column
// shows sending as not available yet. Records are raw values on the wire,
// snake_case, worded by the column in the chrome locale.

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

/** One model a provider offers, as the provider's own model list names it.
 * Ids and names come from the provider at run time, never from the desktop. */
export type AgentModelRecord = {
  id: string;
  display_name: string;
  /** When the provider published it, as an ISO instant. */
  created_at: string;
  max_input_tokens?: number;
  max_output_tokens?: number;
  /** The efforts it accepts, in the order shown; empty when it takes none. */
  efforts: string[];
  default_effort?: string;
};

/** One provider the agent can run, chosen or not. */
export type AgentProviderRecord = {
  id: string;
  name: string;
  selectable: boolean;
  /** Why it cannot be chosen, as a stable code, when `selectable` is false. */
  unavailable_reason?: string;
  models: AgentModelRecord[];
};

/** The provider, model and effort a turn runs with. */
export type AgentSelectionRecord = {
  provider_id: string;
  model_id: string;
  effort?: string;
};

/** One thing a send would share with the provider. */
export type AgentConsentItem =
  | { kind: "messages" }
  | { kind: "document"; id: string; name: string; digest: string }
  | { kind: "tool_results" };

/** What the person is asked to allow before a send: this provider and
 * model receiving these items. The column shows it and the person confirms
 * it; nothing grants it as a side effect of sending. */
export type AgentConsentRequest = {
  conversation_id: string;
  provider_id: string;
  model_id: string;
  items: AgentConsentItem[];
};

/** A consent the person gave, as Cadrumo records it. */
export type AgentConsentGrant = AgentConsentRequest & {
  grant_id: string;
  /** When it was given, as an ISO instant. */
  granted_at: string;
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
  /** The providers and models the agent can run now. */
  providers(): Promise<AgentProviderRecord[]>;
  /** A new, empty conversation of the signed-in profile. */
  startConversation(): Promise<AgentConversationRecord>;
  /** What `request` would share that no grant covers, or null when a grant
   * covers all of it. */
  consentNeeded(request: AgentSendRequest): Promise<AgentConsentRequest | null>;
  /** Records the person's consent. Only the person can give it. */
  grantConsent(request: AgentConsentRequest): Promise<AgentConsentGrant>;
  withdrawConsent(grantId: string): Promise<void>;
  /** The conversation's grants in force. */
  consents(conversationId: string): Promise<AgentConsentGrant[]>;
  /** Refused with `agent_consent_required` when a grant is missing. */
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
