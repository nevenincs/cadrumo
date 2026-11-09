import type { Dispatch, RefObject, SetStateAction } from "react";
import { failureCode } from "../../errors";
import { selectionRecord } from "../../shell/agentCatalog";
import { documentRefs } from "../../shell/agentDocuments";
import { sendRefusalStep } from "../../shell/agentSendRefusals";
import type { newestReply, useLiveConversation } from "../../shell/agentLive";
import type {
  AgentApproval,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentSession,
} from "../../shell/agentSession";
import type { useStagedDocuments } from "../../shell/agentStaging";
import { replyIdOf } from "../../shell/agentViews";
import type {
  AgentColumnView,
  PendingSend,
  PromptOwner,
} from "./agentColumnView";
import type { ComposerReferences } from "./Composer";
import type { AgentSelection } from "./types";
import type { useAgentCatalog } from "./useAgentCatalog";

/**
 * Sending a message, stopping a reply, and answering what a reply waits on:
 * its questions and its approvals. Pressing Send is the person's decision:
 * the message goes, and nothing asks them again. A send that does not go is
 * given back to the composer to try again.
 */
export function agentSending({
  session,
  reader,
  conversationId,
  catalog,
  selection,
  newest,
  ready,
  sending,
  live,
  staging,
  setView,
  currentReader,
  currentSend,
  promptOwner,
  currentPromptOwner,
  pendingPrompt,
  refreshCatalog,
}: {
  session: AgentSession | undefined;
  reader: string | null;
  conversationId: string | null;
  catalog: ReturnType<typeof useAgentCatalog>["catalog"];
  /** What the next message runs with. */
  selection: AgentSelection | null;
  /** The conversation's newest reply, where read. */
  newest: ReturnType<typeof newestReply> | undefined;
  /** The agent service serves. */
  ready: boolean;
  /** A message or an answer is on its way. */
  sending: boolean;
  live: ReturnType<typeof useLiveConversation>;
  staging: Pick<ReturnType<typeof useStagedDocuments>, "sent" | "namedFor">;
  setView: Dispatch<SetStateAction<AgentColumnView>>;
  currentReader: RefObject<string | null>;
  currentSend: RefObject<string | null>;
  promptOwner: PromptOwner;
  currentPromptOwner: RefObject<PromptOwner>;
  pendingPrompt: RefObject<{ owner: PromptOwner; id: string } | null>;
  /** Reads the catalog again: a send was refused for a choice it offered. */
  refreshCatalog: () => void;
}) {
  const change = (next: Partial<AgentColumnView>) =>
    setView((held) => ({ ...held, ...next }));
  const namedFor = staging.namedFor;
  // A send that did not go is given back to the composer to try again.
  const giveBack = (text: string, failure: string | null) =>
    setView((held) => ({
      ...held,
      sending: false,
      pending: null,
      sendFailure: failure,
      draft: { key: held.draft.key + 1, text },
    }));
  const deliver = async (
    request: AgentSendRequest,
    submission: PendingSend,
  ) => {
    if (!session) return;
    const current = () =>
      currentReader.current === reader && currentSend.current === submission.id;
    try {
      const { reply_id } = await session.send(request);
      if (!current()) return;
      // The agent returns no id for the message, so it is shown as sent until
      // the history has it.
      live.sent({
        reply_id,
        text: request.text,
        at: "start",
        attachments: submission.attachments,
        ...(request.skills ? { skills: request.skills } : {}),
      });
      // What the message named went with it.
      staging.sent(request.conversation_id);
      // A message sent may name the conversation, so it is read again.
      setView((held) => ({
        ...held,
        sending: false,
        pending:
          held.pending?.id === submission.id
            ? { ...held.pending, replyId: reply_id }
            : held.pending,
        revision: held.revision + 1,
      }));
    } catch (error) {
      const code = failureCode(error);
      // A choice refused as one this computer cannot run came from a
      // catalog older than the agent's answer: what is offered is read again.
      if (sendRefusalStep(code) !== null) refreshCatalog();
      if (current()) giveBack(request.text, code);
    }
  };
  // Pressing Send is the person's decision: the message goes, and nothing
  // asks them again.
  const submit = async (
    text: string,
    chosen: AgentSelection,
    references: ComposerReferences,
  ) => {
    if (!session || catalog.kind !== "ready") return;
    pendingPrompt.current = null;
    const runs = selectionRecord(catalog.value, chosen);
    if (!runs) {
      giveBack(text, "agent_selection_unavailable");
      return;
    }
    const submission: PendingSend = {
      id: crypto.randomUUID(),
      conversationId,
      replyId: null,
      text,
      attachments: conversationId
        ? namedFor(conversationId).map(({ name, sha256, media_type }) => ({
            name,
            sha256,
            media_type,
          }))
        : [],
      skills: references.skills,
      previousReplies:
        live.read.kind === "ready" ? live.read.value.map(replyIdOf) : [],
    };
    currentSend.current = submission.id;
    change({ pending: submission, interactionId: null });
    const current = () =>
      currentReader.current === reader && currentSend.current === submission.id;
    let request: AgentSendRequest;
    try {
      // A new conversation begins with its first message, never on its own.
      let id = conversationId;
      if (id === null) {
        id = (await session.startConversation()).id;
        if (!current()) return;
        setView((held) => ({
          ...held,
          conversationId: id,
          pending: held.pending
            ? { ...held.pending, conversationId: id }
            : null,
        }));
      }
      // Watched before anything is sent, so the reply is followed from its
      // first word.
      await live.watch(id);
      if (!current()) return;
      request = { conversation_id: id, text, selection: runs };
      if (references.skills.length > 0) request.skills = references.skills;
      const named = namedFor(id);
      if (named.length > 0) request.attachments = documentRefs(named);
    } catch (error) {
      if (current()) giveBack(text, failureCode(error));
      return;
    }
    // A send that fails is given back by `deliver` itself.
    await deliver(request, submission);
  };
  // What the reply waits on. While it asks questions, a message written
  // below answers them in the person's own words, and goes on with the
  // same reply.
  const questionnaire = live.questionnaires[0];
  const resolvePrompt = async (
    send: () => Promise<unknown>,
    accepted: () => void,
    returnedText?: string,
  ) => {
    if (!session || pendingPrompt.current?.owner === promptOwner) return;
    const ticket = { owner: promptOwner, id: crypto.randomUUID() };
    pendingPrompt.current = ticket;
    const current = () =>
      currentPromptOwner.current === ticket.owner &&
      pendingPrompt.current === ticket;
    change({ sending: true, sendFailure: null, interactionId: ticket.id });
    let failed = false;
    let failure: string | null = null;
    try {
      await send();
      if (current()) accepted();
    } catch (error) {
      failed = true;
      failure = failureCode(error);
    } finally {
      if (current())
        setView((held) =>
          held.interactionId === ticket.id
            ? {
                ...held,
                interactionId: null,
                sending: false,
                sendFailure: failure,
                ...(failed && returnedText !== undefined
                  ? { draft: { key: held.draft.key + 1, text: returnedText } }
                  : {}),
              }
            : held,
        );
      if (pendingPrompt.current === ticket) pendingPrompt.current = null;
    }
  };
  const answer = async (
    asked: AgentQuestionnaire,
    reply: AgentQuestionnaireAnswer,
  ) => {
    if (!session) return;
    await resolvePrompt(
      () => session.answerQuestions(asked, reply),
      () => {
        // An answer in words continues the run in place: shown as sent, as a
        // message is.
        if (reply.kind === "message")
          live.sent({ reply_id: asked.reply_id, text: reply.text, at: "end" });
        live.resolved(asked.request_id);
      },
      reply.kind === "message" ? reply.text : undefined,
    );
  };
  const decide = async (approval: AgentApproval, optionId: string) => {
    if (!session) return;
    await resolvePrompt(
      () => session.decideApproval(approval, optionId),
      () => {
        live.resolved(approval.request_id);
      },
    );
  };
  const answering = session && ready && !sending;
  // The agent takes no message while a run needs repair or is being
  // reconciled.
  const heldByRun =
    newest?.status === "repair_needed" ||
    newest?.status === "reconciling" ||
    newest?.status === "deleting";
  // A selection the catalog names in full: a model not yet chosen or written
  // cannot be run.
  const runnable =
    catalog.kind === "ready" &&
    selection !== null &&
    selectionRecord(catalog.value, selection) !== null;
  const send =
    answering && questionnaire
      ? (text: string) => void answer(questionnaire, { kind: "message", text })
      : answering && selection && runnable && !heldByRun
        ? (text: string, references: ComposerReferences) => {
            change({ sending: true, sendFailure: null });
            void submit(text, selection, references);
          }
        : undefined;
  const stop =
    session && live.open
      ? () => {
          const replyId = live.open;
          if (replyId)
            session.cancel(replyId).then(
              () => live.stopping(replyId),
              (error: unknown) => change({ sendFailure: failureCode(error) }),
            );
        }
      : undefined;
  return { questionnaire, answering, answer, decide, send, stop };
}
