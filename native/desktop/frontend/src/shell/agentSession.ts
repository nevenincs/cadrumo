import type {
  Effort,
  EngineDoor,
  EngineDownReason,
  LocalEngine,
  ProviderTransport,
  ServedCatalogAnswer,
  ServedProviderLane,
} from "./agentCatalogContract";
import type {
  AttachmentPolicyResponse,
  ModelLicenceResponse,
  Provider,
  ProviderCondition,
  SkillDetailRecord,
  SkillListResponse,
  SkillVerificationRecord,
} from "./agentGatewayContract";
import type {
  AttachmentCardAnswer,
  AttachmentGrantRevokeAnswer,
  AttachmentGrantsAnswer,
  AttachmentReleaseAnswer,
  ReleaseScope,
} from "./attachmentAdminContract";
import type { CallPlan } from "./hostCall";
import type {
  LocalEngineChoices,
  LocalEngineStatus,
  LocalModelListStatus,
  LocalPlacement,
} from "./localModelsContract";
import type {
  AgentApproval,
  AgentPending,
  AgentQuestionnaire,
  AgentToolRecord,
} from "./agentSnapshotContract";
import type {
  AgentConversationRecord,
  AgentDocumentRecord,
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
// call, an approval.
//
// A conversation is a chain of cadrumo-agent runs, and its id is the first
// run's. A reply is one run: its id is the reply's handle, and a message that
// continues a settled conversation starts a new run, so the next reply has a
// new handle.

/** Why the agent service is not serving, as a stable code. They are the
 * desktop launcher's own vocabulary, not cadrumo-agent's. */
export type AgentServiceRefusal =
  | "agent_platform_unsupported"
  | "agent_service_absent"
  | "agent_service_incompatible"
  | "agent_signed_out"
  | "agent_runtime_unavailable"
  | "agent_provider_credential_missing"
  | "agent_timeout"
  /** The agent's root is not marked as the development lane's. */
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
// provider catalog, as the agent service relays it after checking it against
// the agent's pinned schema: its types are generated in agentCatalogContract.
// The column deduces every choice from it and names no provider, model,
// effort a model takes or what it can do.

/** Whether a keyless local lane's engine answers. A running engine names no
 * reason and no door; one that does not run names both. The schema leaves
 * these pairings open, so `parseEngineHealth` is what reads them. */
export type AgentEngineHealth =
  | {
      engine: LocalEngine;
      state: "running";
      reason: null;
      door: null;
    }
  | {
      engine: LocalEngine;
      state: "not_running";
      reason: EngineDownReason;
      door: EngineDoor;
    };

/**
 * The engine health of `lane`: the measured state, null where the service
 * measured none (the lane has no local engine, or it was not measured), or
 * `"malformed"` for an answer outside the contract. The contract: only the
 * API lane of an engine states one, naming that engine; a running engine has
 * no reason or door and one that does not run has a reason and a door.
 */
export function parseEngineHealth(
  lane: Pick<ServedProviderLane, "provider_id" | "transport" | "health">,
): AgentEngineHealth | null | "malformed" {
  const served = lane.health.engine;
  if (served === undefined || served === null) return null;
  const { engine, state } = served;
  // An absent reason or door is the schema's default, null.
  const reason = served.reason ?? null;
  const door = served.door ?? null;
  if (engine !== lane.provider_id || lane.transport !== "api")
    return "malformed";
  if (state === "running")
    return reason === null && door === null
      ? { engine, state, reason, door }
      : "malformed";
  return reason !== null && door !== null
    ? { engine, state, reason, door }
    : "malformed";
}

/** What a turn runs with, field for field what cadrumo-agent's run start
 * takes of an agent (`AgentSpec`): the provider and the way into it, the model
 * as the catalog names it for a run, and the effort. It takes nothing else:
 * not the lane's execution mode or a catalog entry, which the service resolves
 * itself, and not a model's native controls. */
export type AgentSelectionRecord = {
  provider: string;
  transport: ProviderTransport;
  model: string;
  effort?: Effort;
};

/** One message the person sends, of one to 65536 characters that say
 * something (cadrumo-agent's `message`, `content` and `prompt`), with the
 * stored documents it names. */
export type AgentSendRequest = {
  conversation_id: string;
  text: string;
  selection: AgentSelectionRecord;
  /** At most 32 documents already stored for the conversation, each by
   * its name and the digest it was listed with, uniquely named. The agent
   * reads each where it is stored and refuses one that changed since; no
   * bytes go with the message. */
  attachments?: AgentDocumentRef[];
  /** The skills the message names, which the run loads before it answers:
   * at most 8 unique names of the agent's inventory. Absent when none is
   * named. */
  skills?: string[];
};

/** A file picked for a conversation's storage, as the host stages it. */
export type AgentUploadPick = {
  /** The host's handle for this upload; its events name it. */
  id: string;
  /** The file's own name; never its path. */
  name: string;
  size_bytes: number;
  state: "queued" | "refused";
  /** Why the file was refused before anything was sent. */
  code: string | null;
};

/** Where one upload is: how far it has been sent, stored, or refused. */
export type AgentUploadEvent =
  | { kind: "progress"; id: string; sent: number }
  | { kind: "stored"; id: string; document: AgentDocumentRecord }
  | { kind: "refused"; id: string; code: string };

/** A native drag in webview coordinates. Paths and file bytes stay in the
 * host; a drop can be claimed once using its opaque handle. */
export type AgentDropSignal =
  | { kind: "left" }
  | {
      kind: "over";
      x: number;
      y: number;
      count: number;
      shift: boolean | null;
    }
  | {
      kind: "dropped";
      x: number;
      y: number;
      count: number;
      shift: boolean | null;
      drop_id: string;
    };

/** A stored document a send names. */
export type AgentDocumentRef = { name: string; sha256: string };

/** What a send started. cadrumo-agent names no id for the person's message,
 * so the column shows it as sent until history has it. */
export type AgentSendResult = {
  /** The run the message started: the handle of the reply the stream reports
   * on. It is the id history gives the reply's records as `reply_id`. */
  reply_id: string;
};

// A questionnaire and an approval are cadrumo-agent's own, as the host maps
// them from a run's `pending_clarification` and its `permission_request`
// frame: their types are generated in agentSnapshotContract. Their bounds are
// the agent's (see agentClarification), and the column holds to them. A
// questionnaire's `reply_id` is the run an answer is addressed to.

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

/** One change to a conversation while it is watched, per reply (a run of
 * cadrumo-agent). A reply's text and tool calls are listed by the same ids
 * history() lists them under. A reply's text is one message, however many tool
 * calls come between its parts: text after a tool is more of the same message.
 *
 * The host takes a run's frames in order and tells what its stream cannot:
 * `reply_started` and `resolved` are its own (the agent sends no such frames),
 * and `lost` is sent only when a stream could not be resumed. */
/** Why the product refused a tool call that failed, as cadrumo-agent read it
 * from the tool's result and the host checked it again: the refusal's closed
 * token, and the operator action that recovers from it where the refusal
 * names one, such as `operator.provision.browser`. Identifiers for routing,
 * never shown. */
export type AgentToolRefusal = {
  code: string;
  recovery_action_id?: string;
};

/** History can omit these values. Every stream tool call supplies them as
 * strings, with the kind and status still constrained by the contract. */
export type AgentStreamToolCall = Pick<
  AgentToolRecord,
  "id" | "title" | "tool_kind" | "status"
> &
  Record<"id" | "title" | "tool_kind" | "status", string>;

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
  /** The agent's own reasoning, numbered in the same sequence as its text.
   * Only the stream has it: the history keeps no thought. */
  | {
      type: "thought";
      reply_id: string;
      message_id: string;
      sequence: number;
      /** Reasoning to append to the reply's thoughts. */
      delta: string;
    }
  | {
      type: "tool";
      reply_id: string;
      /** The tool call, whole, each time it changes; `refusal` only on a
       * call that has failed because the product refused it. */
      tool: AgentStreamToolCall & { refusal?: AgentToolRefusal };
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
      provider_condition?: ProviderCondition | null;
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
  /** cadrumo-agent's provider catalog, as it serves it, or its declared
   * catalog while no agent is ready. */
  providerCatalog(retry?: CallPlan): Promise<ServedCatalogAnswer>;
  /** The models the person added to the local lanes' lists and the model
   * documents are read with. Absent where the host offers none. */
  localModels?(): Promise<LocalModelListStatus>;
  /** Adds `model` to `lane`'s list at the revision read; answers every added
   * model after it. A refusal carries the service's reason as
   * `agent_local_models_<reason>`. */
  addLocalModel?(
    lane: string,
    model: string,
    expectedRevision: string,
  ): Promise<LocalModelListStatus>;
  /** Takes the added `model` off `lane`'s list at the revision read. */
  removeLocalModel?(
    lane: string,
    model: string,
    expectedRevision: string,
  ): Promise<LocalModelListStatus>;
  /** Removes the list record, readable or not, at the revision read. */
  resetLocalModels?(expectedRevision: string): Promise<LocalModelListStatus>;
  /** The local engine and placement, stored in the record that holds the
   * lists, so a change to either moves the other's revision. */
  localEngine?(): Promise<LocalEngineStatus>;
  /** Stores the local engine and placement at the revision read; the
   * service restarts the assistant when either changes. A refusal carries
   * the service's reason as `agent_local_models_<reason>`. */
  chooseLocalEngine?(
    engine: LocalEngineChoices["engine"][number],
    placement: LocalPlacement,
    expectedRevision: string,
  ): Promise<LocalEngineStatus>;
  /** Stores `model` on `lane` as the model documents are read with, at the
   * revision read: the one the person selected in the model picker. */
  chooseReadingModel?(
    lane: string,
    model: string,
    expectedRevision: string,
  ): Promise<LocalModelListStatus>;
  /** The licence text of one model a lane lists; only a ready agent has it. */
  modelLicence?(
    provider: Provider,
    transport: ProviderTransport,
    model: string,
  ): Promise<ModelLicenceResponse>;
  /** cadrumo-agent's own skills, every one, by name. Absent where the host
   * serves none. */
  skills?(): Promise<SkillListResponse>;
  /** One skill in full, for the person to review. An unknown name is
   * refused with `agent_gateway_skill_not_found`. */
  skill?(name: string): Promise<SkillDetailRecord>;
  /** The agent's checks of one skill. */
  verifySkill?(name: string): Promise<SkillVerificationRecord>;
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
  /** Opens the host's own file picker for the kinds of file the
   * conversation's storage takes, and stores each file picked in that
   * storage, streamed by the host: the page never has a file's path or its
   * bytes. It answers with what was picked, each queued or refused already,
   * and reports each upload to `onEvent` until it is stored or refused. A
   * picker closed without a pick answers with none. `filterLabel` names the
   * kinds of file in the picker. */
  attach?(
    conversationId: string,
    filterLabel: string,
    onEvent: (event: AgentUploadEvent) => void,
    dropId?: string,
  ): Promise<AgentUploadPick[]>;
  /** Watches native drops while the agent column accepts attachments.
   * Cleanup cannot remove a newer observer. */
  observeDrops?(
    listener: (signal: AgentDropSignal) => void,
  ): Promise<() => void>;
  /** Deletes one stored file, or all of this conversation's stored files.
   * Removing a staged reference alone does not call this. */
  removeDocuments?(conversationId: string, name?: string): Promise<void>;
  /** The storage's admitted formats and its per-file and per-conversation
   * bounds, as the agent serves them. */
  attachmentPolicy?(): Promise<AttachmentPolicyResponse>;
  /** Stops a reply that is still working. The run is `cancelling` until it
   * is `cancelled`. */
  cancel(replyId: string): Promise<void>;
  /**
   * Archives the conversation: every run of its chain, which cadrumo-agent
   * archives together and only once every run has settled. It cannot be undone:
   * the agent has no way to unarchive. A conversation with a live reply is
   * refused with `agent_reply_in_progress`. Absent where the host offers no
   * archiving.
   */
  archive?(conversationId: string): Promise<void>;
  /** Deletes the conversation and its stored documents after the person's
   * confirmation. The agent ends live replies first. A partial removal is
   * reported as `agent_conversation_delete_incomplete`, never as success. */
  delete?(conversationId: string): Promise<void>;
  /**
   * Gives the conversation the person's title in place of the one its first
   * message gave it. One not sent yet takes it with its first run. A title
   * that is not one line of 1 to 200 characters is refused with
   * `agent_invalid_request`. Absent where the host offers no renaming.
   */
  rename?(conversationId: string, title: string): Promise<void>;
  /** What the conversation's unfinished reply waits on, so a reload shows
   * the same questions and approvals the stream raised. */
  pending(conversationId: string): Promise<AgentPending>;
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
  /** What the service says the card shows for a parked attachment read. */
  attachmentCard(
    approval: Pick<AgentApproval, "reply_id" | "request_id">,
  ): Promise<AttachmentCardAnswer>;
  /** Puts the person's answer to the service; `null` asks it to release under a
   * grant it already holds. The request is answered only once released. */
  attachmentRelease(
    approval: Pick<AgentApproval, "reply_id" | "request_id">,
    optionId: string,
    scope: ReleaseScope | null,
  ): Promise<AttachmentReleaseAnswer>;
  attachmentGrants(): Promise<AttachmentGrantsAnswer>;
  attachmentGrantRevoke(grantId: string): Promise<AttachmentGrantRevokeAnswer>;
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
