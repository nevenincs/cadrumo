import type {
  AgentApproval,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSession,
} from "../../shell/agentSession";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { AttachmentReadPrompt } from "./AttachmentReadPrompt";
import { QuestionsPrompt } from "./QuestionsPrompt";

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
}) {
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
