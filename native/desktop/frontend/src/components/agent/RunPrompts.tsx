import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentQuestionnaireAnswer,
  AgentSession,
} from "../../shell/agentSession";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { AttachmentBarNotice, type BarredRead } from "./AttachmentBarNotice";
import { AttachmentReadPrompt } from "./AttachmentReadPrompt";
import { QuestionsPrompt } from "./QuestionsPrompt";
import type {
  AgentApproval,
  AgentQuestionnaire,
} from "../../shell/agentSnapshotContract";

/**
 * What a reply waits on: each approval it asks for, a request to read an
 * attachment drawn with what it would read, and its questions. Each is
 * answerable only while nothing else is on its way.
 *
 * A read the installation or profile keeps on this computer has no answer of
 * the person's to wait for: the service says so on its card, the request is
 * declined here one at a time, and one notice names every file of the run.
 */
export function RunPrompts({
  session,
  approvals,
  questionnaire,
  answering,
  onDecide,
  onAnswer,
  onResolved,
  run,
  onChooseModel,
}: {
  session: AgentSession | undefined;
  approvals: readonly AgentApproval[];
  questionnaire: AgentQuestionnaire | undefined;
  answering: boolean;
  onDecide: (approval: AgentApproval, optionId: string) => void;
  onAnswer: (
    asked: AgentQuestionnaire,
    reply: AgentQuestionnaireAnswer,
  ) => void;
  /** The reply no longer waits on the request. */
  onResolved: (requestId: string) => void;
  /** The reply now open, or null when none is. */
  run: string | null;
  /** Opens the model picker, where the column offers it. */
  onChooseModel?: () => void;
}) {
  const [barred, setBarred] = useState<readonly BarredRead[]>([]);
  const [declined, setDeclined] = useState<ReadonlySet<string>>(new Set());
  const tried = useRef(new Set<string>());
  const noteBarred = useCallback(
    (read: BarredRead) =>
      setBarred((held) =>
        held.some((known) => known.requestId === read.requestId)
          ? held
          : [...held, read],
      ),
    [],
  );
  // A newer reply says nothing of an older one's files.
  useEffect(() => {
    if (run !== null && barred.some((read) => read.replyId !== run))
      setBarred((held) => held.filter((read) => read.replyId === run));
  }, [run, barred]);
  // One decline at a time: the column takes a single answer in flight, and
  // each decline settles before the next read is declined.
  useEffect(() => {
    if (!answering) return;
    for (const approval of approvals) {
      if (
        !barred.some((read) => read.requestId === approval.request_id) ||
        tried.current.has(approval.request_id)
      )
        continue;
      const refuse = approval.options.find(
        (option) => option.kind === "reject_once",
      )?.option_id;
      if (!refuse) continue;
      tried.current.add(approval.request_id);
      setDeclined((held) => new Set(held).add(approval.request_id));
      onDecide(approval, refuse);
      return;
    }
  }, [answering, approvals, barred, onDecide]);
  const reply = barred.at(-1)?.replyId;
  const notice = barred.filter((read) => read.replyId === reply);
  return (
    <>
      <AttachmentBarNotice reads={notice} onChooseModel={onChooseModel} />
      {approvals.map((approval) => {
        const prompt = (
          <ApprovalPrompt
            key={approval.request_id}
            source={approval.source}
            toolCall={approval.tool_call}
            toolServer={approval.tool_server}
            toolName={approval.tool_name}
            toolReach={approval.tool_reach}
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
        const refuse = approval.options.find(
          (option) => option.kind === "reject_once",
        )?.option_id;
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
            onBarred={noteBarred}
            quiet={
              barred.some((read) => read.requestId === approval.request_id) &&
              !declined.has(approval.request_id)
            }
            plain={prompt}
          />
        );
      })}
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
