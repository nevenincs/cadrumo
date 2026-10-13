// What the agent column shows, as view models. They describe presentation
// only and follow no wire format: whatever serves the column maps its own
// answers onto these shapes.

/** A model provider the person can choose, or see and not choose. */
export type ProviderOption = {
  id: string;
  name: string;
  selectable: boolean;
  /** Why it cannot be chosen, shown beside it when `selectable` is false. */
  unavailableReason?: string;
};

/** A model one provider offers, with the efforts it can work at. */
export type ModelOption = {
  id: string;
  name: string;
  /** One line saying what the model is for, where the provider says. */
  description?: string;
  /** The efforts it accepts, as shown to the person, in the order shown.
   * Empty when the model takes no effort setting. */
  efforts: readonly string[];
  defaultEffort?: string;
};

/** The provider, model and effort a conversation runs with. */
export type AgentSelection = {
  providerId: string;
  modelId: string;
  effort?: string;
};

/** What a file is, as far as how it is drawn goes. */
export type FileKind = "image" | "sheet" | "text" | "archive" | "document";

/** Where a file staged for the next message is on its way to being sent. */
export type AttachmentState = "queued" | "uploading" | "ready" | "refused";

/** A file staged in the composer, not yet part of the conversation. */
export type StagedAttachment = {
  id: string;
  name: string;
  /** The extension without its dot, as the file is named. */
  extension: string;
  sizeBytes: number;
  kind: FileKind;
  state: AttachmentState;
  /** How much has been sent, 0 to 1, while `state` is `uploading`. */
  progress?: number;
  /** Why the file was not accepted, when `state` is `refused`. */
  refusalReason?: string;
  /** A preview of an image, already safe to show. */
  thumbnailUrl?: string;
  /** How many files an archive holds, where that is known. */
  memberCount?: number;
};

/** One conversation in the history. */
export type ConversationSummary = {
  id: string;
  title: string;
  /** When it was last active, already worded, e.g. "3 days ago". */
  lastActivityLabel: string;
  documentCount: number;
  archived: boolean;
  /** The conversation the column is showing now. */
  current?: boolean;
};

/** Conversations under one date heading, both worded by the caller. */
export type ConversationGroup = {
  heading: string;
  conversations: readonly ConversationSummary[];
};

/** How a document is used in the conversation. */
export type DocumentRole = "context" | "information" | "ledger";

/** Where a document is on its way to being usable in the conversation. */
export type DocumentStatus =
  "uploading" | "ready" | "extracting" | "needsReview" | "failed" | "skipped";

/** A document that is part of the conversation. */
export type ConversationDocument = {
  id: string;
  name: string;
  /** The extension without its dot, as the file is named. */
  extension: string;
  sizeBytes: number;
  role: DocumentRole;
  status: DocumentStatus;
  /** What the file is, for its icon; without it the generic page is drawn. */
  kind?: FileKind;
  /** A preview of an image, already safe to show. */
  thumbnailUrl?: string;
  /** The files inside an archive. */
  members?: readonly ConversationDocument[];
};

/** A file that went with a message the person sent, as the transcript shows
 * it: named and typed, no longer staged. */
export type SentFile = {
  id: string;
  name: string;
  /** The extension without its dot, as the file is named. */
  extension: string;
  kind: FileKind;
};

/** Where an agent's reply is: finished, still being written, stopped by
 * the person, or ended by a failure. */
export type AgentReplyState = "complete" | "working" | "stopped" | "failed";

/** One turn of the conversation, the person's or the agent's. */
export type TranscriptMessage =
  | {
      kind: "person";
      id: string;
      text: string;
      /** The files sent with the message, in the order they were sent. */
      files?: readonly SentFile[];
      /** When it was sent, already worded, e.g. "10:42". */
      sentAtLabel?: string;
    }
  | {
      kind: "agent";
      id: string;
      /** The reply so far; while `state` is `working` it may still grow. */
      text: string;
      state: AgentReplyState;
      /** Why the reply failed, when `state` is `failed`. */
      failureReason?: string;
    };

/** Where a Cadrumo tool the agent called is: still running, finished, or
 * refused. */
export type ToolActivityState = "running" | "done" | "refused";

/** A Cadrumo tool the agent called, such as reading ledger entries. */
export type TranscriptToolActivity = {
  kind: "tool";
  id: string;
  /** What the tool does, worded by the caller, e.g. "Read ledger entries". */
  label: string;
  state: ToolActivityState;
  /** More about the call, such as why it was refused. */
  detail?: string;
};

/** Anything the transcript lists, in conversation order. */
export type TranscriptItem = TranscriptMessage | TranscriptToolActivity;
