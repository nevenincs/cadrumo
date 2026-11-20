import { useCallback, useState } from "react";
import {
  groupBarredReads,
  type BarredRead,
} from "../../shell/attachmentRefusals";
import type {
  AgentQuestionnaireAnswer,
  AgentSession,
} from "../../shell/agentSession";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { AttachmentReadPrompt } from "./AttachmentReadPrompt";
import { AttachmentRefusalGroup } from "./AttachmentRefusalGroup";
import { QuestionsPrompt } from "./QuestionsPrompt";
import type {
  AgentApproval,
  AgentQuestionnaire,
} from "../../shell/agentSnapshotContract";

/**
 * What a reply waits on: each approval it asks for, a request to read an
 * attachment drawn with what it would read, and its questions. Each is
 * answerable only while nothing else is on its way.
 */
export function RunPrompts({
  session,
  approvals,
  questionnaire,
  answering,
  onDecide,
  onAnswer,
  onResolved,
  onOpenProfile,
}: {
  session: AgentSession | undefined;
  approvals: readonly AgentApproval[];
  questionnaire: AgentQuestionnaire | undefined;
  answering: boolean;
  /** Settles once the decision is answered; the column takes one at a time. */
  onDecide: (approval: AgentApproval, optionId: string) => void | Promise<void>;
  onAnswer: (
    asked: AgentQuestionnaire,
    reply: AgentQuestionnaireAnswer,
  ) => void;
  /** The reply no longer waits on the request. */
  onResolved: (requestId: string) => void;
  /** Opens the profile page; absent where the window cannot. */
  onOpenProfile?: () => void;
}) {
  // The reads the service refused for a bar on every off-host read, by the
  // agent's request: one refusal is worded for all of them.
  const [barred, setBarred] = useState<
    Readonly<Record<string, Omit<BarredRead, "requestId">>>
  >({});
  const onBarred = useCallback(
    (requestId: string, one: Omit<BarredRead, "requestId"> | null) =>
      setBarred((held) => {
        if (one === null) {
          if (!(requestId in held)) return held;
          return Object.fromEntries(
            Object.entries(held).filter(([key]) => key !== requestId),
          );
        }
        return { ...held, [requestId]: one };
      }),
    [],
  );
  const refusal = (approval: AgentApproval) =>
    approval.options.find((option) => option.kind === "reject_once")?.option_id;
  // The column answers one request at a time, so the reads of a group are
  // declined one after another.
  const declineAll = async (reads: readonly AgentApproval[]) => {
    for (const approval of reads) {
      const refuse = refusal(approval);
      if (refuse) await onDecide(approval, refuse);
    }
  };
  const groups = groupBarredReads(
    approvals.flatMap((approval) => {
      const one = barred[approval.request_id];
      return one ? [{ requestId: approval.request_id, ...one }] : [];
    }),
  );
  return (
    <>
      {approvals.map((approval) => {
        const prompt = (
          <ApprovalPrompt
            key={approval.request_id}
            source={approval.source}
            toolCall={approval.tool_call}
            toolServer={approval.tool_server}
            toolKind={approval.tool_kind}
            description={approval.description}
            options={approval.options}
            onDecide={
              answering ? (optionId) => onDecide(approval, optionId) : undefined
            }
          />
        );
        if (
          !session ||
          approval.tool_call !== "read_attachment" ||
          approval.tool_server
        )
          return prompt;
        const refuse = refusal(approval);
        return (
          <AttachmentReadPrompt
            key={approval.request_id}
            session={session}
            approval={approval}
            disabled={!answering}
            onSettled={() => onResolved(approval.request_id)}
            onDecline={
              answering && refuse ? () => onDecide(approval, refuse) : undefined
            }
            onBarred={onBarred}
            plain={prompt}
          />
        );
      })}
      {groups.map((group) => (
        <AttachmentRefusalGroup
          key={group.code}
          group={group}
          onOpenProfile={onOpenProfile}
          onDecline={
            answering
              ? () =>
                  void declineAll(
                    approvals.filter((approval) =>
                      group.requestIds.includes(approval.request_id),
                    ),
                  )
              : undefined
          }
        />
      ))}
      {questionnaire && (
        <QuestionsPrompt
          key={questionnaire.request_id}
          questions={questionnaire.questions}
          onAnswer={
            answering
              ? (answers) =>
                  onAnswer(questionnaire, { kind: "answers", answers })
              : undefined
          }
          onDecline={
            answering
              ? () => onAnswer(questionnaire, { kind: "decline" })
              : undefined
          }
        />
      )}
    </>
  );
}
