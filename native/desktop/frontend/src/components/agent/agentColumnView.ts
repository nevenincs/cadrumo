import type { AgentSession } from "../../shell/agentSession";
import type { AgentDocumentReference } from "../../shell/agentViews";
import type { AgentSelection } from "./types";

/** What the agent column shows beside its conversation. */
export type Panel = "none" | "history" | "settings" | "documents";

/** A message sent and not yet in the conversation's history. */
export type PendingSend = {
  id: string;
  conversationId: string | null;
  replyId: string | null;
  text: string;
  attachments: AgentDocumentReference[];
  skills: string[];
  previousReplies: string[];
};

/** What the agent column is showing, which belongs to the profile it was
 * shown for. */
export type AgentColumnView = {
  reader: string | null;
  panel: Panel;
  archived: boolean;
  conversationId: string | null;
  chosen: AgentSelection | null;
  sending: boolean;
  interactionId: string | null;
  pending: PendingSend | null;
  sendFailure: string | null;
  // Why the history's last action was refused.
  archiveFailure: string | null;
  historyBusy: boolean;
  // The composer is drawn anew with this draft when a send is given back.
  draft: { key: number; text: string };
  // Counts the messages sent and the replies finished, each a reason to
  // read the conversations again.
  revision: number;
};

/** Whose a prompt's answer is: the profile, the conversation and the
 * session it was asked in. */
export type PromptOwner = {
  reader: string | null;
  conversationId: string | null;
  session: AgentSession | undefined;
};
