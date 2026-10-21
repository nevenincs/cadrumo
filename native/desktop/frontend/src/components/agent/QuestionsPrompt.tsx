import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { useId, useState } from "react";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  answerFaults,
  characters,
  isBlank,
  MAX_ANSWER_CHARS,
  type AnswerFault,
} from "../../shell/agentClarification";
import type { AgentQuestion } from "../../shell/agentSession";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/** What the person has written for `id`, or nothing. */
const written = (answers: Readonly<Record<string, string>>, id: string) =>
  Object.hasOwn(answers, id) ? (answers[id] ?? "") : "";

/** Why an answer is not accepted, in words, or null where it is not the
 * answer's own fault. */
function faultWords(
  t: Translate,
  fault: AnswerFault | undefined,
  answer: string,
): string | null {
  switch (fault?.kind) {
    case "too_long":
      return t("desktop.agent.questions_too_long", {
        count: characters(answer),
        max: MAX_ANSWER_CHARS,
      });
    case "control_characters":
      return t("desktop.agent.questions_control");
    default:
      return null;
  }
}

/**
 * The questions a reply waits on. The person answers them, writes a message
 * below instead, or declines; nothing is answered for them. A choice takes
 * one of its options as written, a text answer is one line of at most 2048
 * characters, and Answer waits until every required question has an answer
 * the agent would take. Answers left empty are not sent. The questions are
 * shown as the agent wrote them.
 */
export function QuestionsPrompt({
  questions,
  onAnswer,
  onDecline,
}: {
  questions: readonly AgentQuestion[];
  /** The answers by question id, empty ones left out. Without it, Answer
   * says it is not available. */
  onAnswer?: (answers: Record<string, string>) => void;
  onDecline?: () => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // What would be sent: the questions answered with something to say, in the
  // order they were asked.
  const given = Object.fromEntries(
    questions.flatMap((question) => {
      const answer = written(answers, question.id);
      return isBlank(answer) ? [] : [[question.id, answer]];
    }),
  );
  const faults = answerFaults(questions, given);
  const held = faults.some((fault) => fault.kind !== "missing")
    ? t("desktop.agent.questions_invalid")
    : faults.length > 0
      ? t("desktop.agent.questions_missing")
      : undefined;
  return (
    <section
      aria-labelledby={titleId}
      className="agent-questions grid max-h-[60dvh] gap-3 overflow-y-auto rounded-xl border border-border-strong bg-card p-3.5 text-card-foreground shadow-raised"
    >
      <div className="flex items-start gap-2">
        <Icon name="agent" size="md" className="mt-0.5 text-muted-foreground" />
        <div className="grid gap-1">
          <h3 id={titleId} className="font-semibold text-foreground">
            {t("desktop.agent.questions_title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("desktop.agent.questions_lead")}
          </p>
        </div>
      </div>
      {questions.map((question) => (
        <QuestionField
          key={question.id}
          question={question}
          value={written(answers, question.id)}
          fault={faults.find((fault) => fault.id === question.id)}
          onChange={(answer) =>
            setAnswers((kept) => ({ ...kept, [question.id]: answer }))
          }
        />
      ))}
      <div className="flex flex-wrap justify-end gap-2">
        <AgentTextAction variant="outline" size="sm" onAction={onDecline}>
          {t("desktop.agent.questions_decline")}
        </AgentTextAction>
        <AgentTextAction
          variant="primary"
          size="sm"
          heldBy={held}
          onAction={onAnswer ? () => onAnswer(given) : undefined}
        >
          {t("desktop.agent.questions_answer")}
        </AgentTextAction>
      </div>
    </section>
  );
}

function QuestionField({
  question,
  value,
  fault,
  onChange,
}: {
  question: AgentQuestion;
  value: string;
  fault: AnswerFault | undefined;
  onChange: (answer: string) => void;
}) {
  const t = useStrings();
  const labelId = useId();
  const fieldId = useId();
  const errorId = useId();
  const required = question.required !== false;
  const label = (
    <FieldLabel id={labelId} htmlFor={fieldId} className="font-medium">
      <span className="min-w-0 whitespace-pre-wrap wrap-anywhere">
        {question.prompt}
        {!required && (
          <span className="ml-1.5 font-normal text-muted-foreground">
            {t("desktop.agent.questions_optional")}
          </span>
        )}
      </span>
    </FieldLabel>
  );
  if (question.kind === "choice")
    return (
      <Field>
        {label}
        <RadioGroupPrimitive.Root
          id={fieldId}
          aria-labelledby={labelId}
          aria-required={required}
          orientation="vertical"
          value={value}
          onValueChange={onChange}
          className="grid gap-0.5"
        >
          {(question.options ?? []).map((option) => (
            <RadioGroupPrimitive.Item
              key={option}
              value={option}
              className="flex w-full cursor-pointer items-start gap-2 rounded-md border px-2 py-1.5 text-left text-foreground transition-colors hover:bg-accent data-[state=checked]:border-border-strong data-[state=checked]:bg-selected forced-colors:data-[state=checked]:bg-[Highlight] forced-colors:data-[state=checked]:text-[HighlightText]"
            >
              <span className="min-w-0 flex-1 whitespace-pre-wrap wrap-anywhere">
                {option}
              </span>
              <span className="flex size-icon-md shrink-0 items-center justify-center pt-0.5">
                <RadioGroupPrimitive.Indicator>
                  <Icon name="check" className="text-foreground" />
                </RadioGroupPrimitive.Indicator>
              </span>
            </RadioGroupPrimitive.Item>
          ))}
        </RadioGroupPrimitive.Root>
        {/* A choice cannot be unmade by choosing again; a question the agent
            lets go unanswered can be left so. */}
        {!required && value !== "" && (
          <div className="flex justify-end">
            <AgentTextAction
              variant="ghost"
              size="xs"
              onAction={() => onChange("")}
            >
              {t("desktop.agent.questions_clear")}
            </AgentTextAction>
          </div>
        )}
      </Field>
    );
  const words = faultWords(t, fault, value);
  return (
    <Field data-invalid={words ? "true" : undefined}>
      {label}
      <textarea
        id={fieldId}
        rows={2}
        value={value}
        aria-required={required}
        aria-invalid={words ? true : undefined}
        aria-describedby={words ? errorId : undefined}
        onChange={(event) => onChange(event.target.value)}
        // An answer is one line: a line break would be refused, so it is not
        // made. Enter that composes a character is the input method's.
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.nativeEvent.isComposing)
            event.preventDefault();
        }}
        className="block w-full resize-y rounded-md border bg-background px-2.5 py-1.5 text-base text-foreground aria-invalid:border-destructive focus-visible:outline-(length:--focus-ring) focus-visible:outline-offset-(length:--focus-ring) focus-visible:outline-solid"
      />
      <FieldError id={errorId}>{words}</FieldError>
    </Field>
  );
}
