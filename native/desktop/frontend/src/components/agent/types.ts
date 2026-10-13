// What the agent column shows, as view models. They describe presentation
// only and follow no wire format: whatever serves the column maps its own
// answers onto these shapes.

/** One of a few things to choose among, as shown. */
export type Choice = {
  id: string;
  name: string;
  description?: string;
};

/** How a provider is reached: its web API, or its own command-line app on
 * this computer. */
export type ProviderTransport = "api" | "cli";

/** One way into a provider, with the models it offers. */
export type ProviderWay = {
  /** Keys the way's models. Nothing about the way is to be read from it. */
  id: string;
  transport: ProviderTransport;
  selectable: boolean;
  /** Why it cannot be chosen, shown beside it when `selectable` is false. */
  unavailableReason?: string;
  /** The model chosen with it, where its catalog recommends one. */
  defaultModelId?: string;
  /** What the way has been proven able to do on this computer, already
   * worded. A proof belongs to the way, never to one of its models. */
  capabilities?: readonly string[];
  /** Present where the way lists no models, so the person writes a model's
   * id; the efforts the way accepts with any model they write. */
  modelWritten?: { efforts: readonly Choice[] };
};

/** A model provider the person can choose, or see and not choose. It is one
 * provider however many ways reach it. */
export type ProviderOption = {
  /** The provider's id, which picks its mark. */
  id: string;
  name: string;
  /** Some way into it can be chosen. */
  selectable: boolean;
  /** Its ways, the API before the command-line app. */
  ways: readonly ProviderWay[];
};

/** A model one way into a provider offers, with the efforts it can work at,
 * each the model's own. */
export type ModelOption = {
  id: string;
  name: string;
  /** One line saying what the model is for, where the provider says. */
  description?: string;
  /** The efforts it accepts, in the order shown. Empty when the model takes
   * no effort setting. */
  efforts: readonly Choice[];
  defaultEffort?: string;
};

/** The provider, the way into it, the model and the effort a conversation
 * runs with. */
export type AgentSelection = {
  providerId: string;
  /** The way into the provider, by `ProviderWay.id`. */
  wayId: string;
  /** The model's id: chosen from the way's list, or written where the way
   * lists none. */
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
      /** While `state` is `working`: the reply is held until the person
       * answers questions or decides an approval, so it says it is waiting
       * for them rather than working. */
      waitingOnPerson?: boolean;
    };

/** Where a tool the agent called is, in cadrumo-agent's own four states. */
export type ToolActivityState =
  "pending" | "in_progress" | "completed" | "failed";

/** A tool the agent called, such as reading ledger entries. */
export type TranscriptToolActivity = {
  kind: "tool";
  id: string;
  /** The tool's title, as the agent names it. */
  label: string;
  state: ToolActivityState;
  /** More about the call, such as what kind of tool it is, already worded. */
  detail?: string;
};

/** Anything the transcript lists, in conversation order. */
export type TranscriptItem = TranscriptMessage | TranscriptToolActivity;
