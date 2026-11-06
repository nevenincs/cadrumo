import { Badge } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import type {
  ModeloFormElection,
  PublicModeloFormElectionFigure,
  PublicModeloFormElectionQuestion,
  ModeloFormElectionReason,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";

// How the result is settled, as the export offer served it: each election the
// declaration asks, with its answers and, where the answer states amounts,
// those amounts. A question that cannot be answered says why in the
// application's words, and the reasons are told apart by their mark: a result
// not yet known, a settlement Cadrumo does not compute and a period or amount
// that rules the answer out are not the same thing. A figure the
// application worked out where no official rule fixes it is marked advisory
// and says why. The window words only its own frame and sends the answers it
// was given choices for.

/** The mark of each reason a question is unavailable, so an unknown result,
 * an unsupported settlement and a ruled-out answer do not look alike. */
const REASON_MARK: Record<ModeloFormElectionReason, IconName> = {
  nothing_to_pay: "info",
  nothing_to_refund: "info",
  result_unknown: "unknown",
  amendment: "info",
  past_filing_window: "clock",
  filing_window_unknown: "unknown",
  no_open_account: "info",
  no_spanish_account: "info",
  settlement_unsupported: "refused",
  second_instalment_nothing: "info",
};

function Figure({ figure }: { figure: PublicModeloFormElectionFigure }) {
  const t = useStrings();
  return (
    <li
      data-figure={figure.instalment}
      data-amount={figure.amount}
      data-advisory={figure.advisory}
      className="flex flex-col gap-1 py-2"
    >
      <span className="flex flex-wrap items-center gap-2 text-sm">
        <span className="tabular-nums">{figure.words}</span>
        {figure.advisory && (
          <Badge variant="warning">
            {t("desktop.modelo.settlement.advisory")}
          </Badge>
        )}
      </span>
      {figure.advisory_words && (
        <span className="text-xs text-muted-foreground">
          {figure.advisory_words}
        </span>
      )}
    </li>
  );
}

function Question({
  question,
  answer,
  onAnswer,
  disabled,
}: {
  question: PublicModeloFormElectionQuestion;
  /** The answer the filer chose; none leaves the question's default. */
  answer: string | undefined;
  onAnswer(value: string): void;
  disabled: boolean;
}) {
  const id = `election-${question.election}`;
  return (
    <div
      data-election={question.election}
      data-state={question.state}
      data-reason={question.reason ?? undefined}
      className="flex flex-col gap-1"
    >
      <label htmlFor={id} className="text-sm text-muted-foreground">
        {question.words}
      </label>
      {question.state === "available" ? (
        <>
          <NativeSelect
            id={id}
            controlSize="sm"
            disabled={disabled}
            value={answer ?? question.default ?? ""}
            onChange={(event) => onAnswer(event.target.value)}
          >
            {question.default === null && answer === undefined && (
              <option value="" disabled />
            )}
            {question.choices.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.words}
              </option>
            ))}
          </NativeSelect>
          {question.help && (
            <p className="text-xs text-muted-foreground">{question.help}</p>
          )}
          {question.figures.length > 0 && (
            <ul
              aria-label={question.words}
              className="flex flex-col divide-y divide-border rounded-md border border-border bg-card px-3"
            >
              {question.figures.map((figure) => (
                <Figure key={figure.instalment} figure={figure} />
              ))}
            </ul>
          )}
        </>
      ) : (
        <p
          id={id}
          className="flex items-start gap-2 text-sm"
          data-unavailable=""
        >
          <Icon
            name={question.reason ? REASON_MARK[question.reason] : "info"}
            size="xs"
            className="mt-0.5 shrink-0 text-muted-foreground"
          />
          <span>{question.state_words}</span>
        </p>
      )}
    </div>
  );
}

/**
 * The settlement questions of an export offer. A question the result makes
 * meaningless is not asked; one that applies but cannot be answered now says
 * why. Answers are the filer's own and live with the caller, which sends them
 * in the request field each question names.
 */
export function Settlement({
  questions,
  answers,
  onAnswer,
  disabled = false,
}: {
  questions: readonly PublicModeloFormElectionQuestion[];
  answers: Partial<Record<ModeloFormElection, string>>;
  onAnswer(election: ModeloFormElection, value: string): void;
  disabled?: boolean;
}) {
  const t = useStrings();
  const asked = questions.filter(
    (question) => question.state !== "not_applicable",
  );
  if (asked.length === 0) return null;
  return (
    <section
      aria-label={t("desktop.modelo.settlement.title")}
      data-settlement=""
      className="flex flex-col gap-3"
    >
      <h3 className="text-sm font-medium">
        {t("desktop.modelo.settlement.title")}
      </h3>
      <div className="grid grid-cols-1 gap-3 @3xl:grid-cols-2">
        {asked.map((question) => (
          <Question
            key={question.election}
            question={question}
            answer={answers[question.election]}
            onAnswer={(value) => onAnswer(question.election, value)}
            disabled={disabled}
          />
        ))}
      </div>
    </section>
  );
}
