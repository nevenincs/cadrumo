import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { useId, useState } from "react";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/** The most text one answer holds, as the agent accepts it. */
export const ANSWER_MAX = 2048;

/** One question the agent asks: a choice of its options, or text. */
export type Question = {
  id: string;
  prompt: string;
  kind: "choice" | "text";
  /** A choice's options, one of which is the answer, as written. */
  options?: readonly string[];
  required: boolean;
};

/**
 * The questions a reply waits on. The person answers them, writes a message
 * below instead, or declines; nothing is answered for them. A choice takes
 * one of its options as written, a text answer up to its limit, and Answer
 * waits until every required question has one. Answers left empty are not
 * sent.
 */
export function QuestionsPrompt({
  questions,
  onAnswer,
  onDecline,
}: {
  questions: readonly Question[];
  /** The answers by question id, empty ones left out. Without it, Answer
   * says it is not available. */
  onAnswer?: (answers: Record<string, string>) => void;
  onDecline?: () => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const given = Object.fromEntries(
    Object.entries(answers).filter(([, answer]) => answer.trim() !== ""),
  );
  const missing = questions.some(
    (question) => question.required && !(question.id in given),
  );
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
          value={answers[question.id] ?? ""}
          onChange={(answer) =>
            setAnswers((held) => ({ ...held, [question.id]: answer }))
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
          heldBy={missing ? t("desktop.agent.questions_missing") : undefined}
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
  onChange,
}: {
  question: Question;
  value: string;
  onChange: (answer: string) => void;
}) {
  const t = useStrings();
  const labelId = useId();
  const fieldId = useId();
  const label = (
    <FieldLabel id={labelId} htmlFor={fieldId} className="font-medium">
      {question.prompt}
      {!question.required && (
        <span className="ml-1.5 font-normal text-muted-foreground">
          {t("desktop.agent.questions_optional")}
        </span>
      )}
    </FieldLabel>
  );
  if (question.kind === "choice")
    return (
      <Field>
        {label}
        <RadioGroupPrimitive.Root
          id={fieldId}
          aria-labelledby={labelId}
          aria-required={question.required}
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
              <span className="min-w-0 flex-1 wrap-anywhere">{option}</span>
              <span className="flex size-icon-md shrink-0 items-center justify-center pt-0.5">
                <RadioGroupPrimitive.Indicator>
                  <Icon name="check" className="text-foreground" />
                </RadioGroupPrimitive.Indicator>
              </span>
            </RadioGroupPrimitive.Item>
          ))}
        </RadioGroupPrimitive.Root>
      </Field>
    );
  return (
    <Field>
      {label}
      <textarea
        id={fieldId}
        rows={2}
        value={value}
        maxLength={ANSWER_MAX}
        aria-required={question.required}
        onChange={(event) => onChange(event.target.value)}
        className="block w-full resize-y rounded-md border bg-background px-2.5 py-1.5 text-base text-foreground focus-visible:outline-(length:--focus-ring) focus-visible:outline-offset-(length:--focus-ring) focus-visible:outline-solid"
      />
    </Field>
  );
}
