import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import { Spinner } from "@/components/ui/spinner";
import type {
  ElectionAnswer,
  ElectionQuestion,
  ImputationElection as Election,
  ProfileCompanionPort,
} from "../../../shell/profileHousehold";
import { useStrings } from "../../../shell/strings";
import type { ProfileChange } from "../../../shell/userProfile";

/** How the window draws what the profile states for the year: the state's
 * icon, tone and words. The states are the application's closed three. */
const STATE: Record<
  ElectionAnswer["state"],
  { icon: IconName; tone: string; words: string }
> = {
  declared: {
    icon: "check",
    tone: "text-success",
    words: "workspace.modelo.election.state.declared",
  },
  undeclared: {
    icon: "pending",
    tone: "text-faint",
    words: "workspace.modelo.election.state.undeclared",
  },
  contradictory: {
    icon: "alert",
    tone: "text-warning",
    words: "workspace.modelo.election.state.contradictory",
  },
};

/** How a rejected read or write is worded, from the host's code alone; the
 * profile pages map nothing else. */
const FAILURE_WORDS: Record<string, string> = {
  not_signed_in: "desktop.profile.signed_out",
  refused: "desktop.profile.refused",
  conflict: "desktop.profile.conflict",
  unknown: "desktop.profile.unknown",
  saved_unread: "desktop.profile.saved_unread",
};

type Failure = {
  code: string;
  /** The finished sentence the application served for a refusal, when the
   * rejection carries one. The window shows it as served. */
  words: string | null;
};

function failureOf(error: unknown): Failure {
  const found = error as { code?: unknown; refusal_words?: unknown } | null;
  const words = found?.refusal_words;
  return {
    code: typeof found?.code === "string" ? found.code : "unavailable",
    words: typeof words === "string" && words.trim() !== "" ? words : null,
  };
}

type Read =
  | { phase: "reading" }
  | { phase: "failed"; failure: Failure }
  | { phase: "ready"; election: Election };

/** What the person chose and has not saved; null leaves what is stated. */
type Draft = { criterion: string | null; accounting: string | null };
const NO_DRAFT: Draft = { criterion: null, accounting: null };

type Notice = { kind: "saved" } | { kind: "failed"; failure: Failure } | null;

/** The token a question's answer states, or null when it states none. */
function stated(answer: ElectionAnswer): string | null {
  return answer.state === "declared" ? answer.value : null;
}

function Choices({
  question,
  value,
  disabled,
  onChange,
}: {
  question: ElectionQuestion;
  value: string | null;
  disabled: boolean;
  onChange(value: string): void;
}) {
  const prompt = useId();
  return (
    <div className="flex flex-col gap-2">
      <p id={prompt} className="text-base font-medium text-foreground">
        {question.prompt}
      </p>
      {question.help && (
        <p className="text-sm text-muted-foreground">{question.help}</p>
      )}
      <RadioGroup
        aria-labelledby={prompt}
        // No choice is selected until the person makes one: an unstated
        // year is not read as any of them.
        value={value ?? ""}
        onValueChange={onChange}
        disabled={disabled}
      >
        {question.choices.map((choice) => (
          <label
            key={choice.value}
            className="flex cursor-pointer items-start gap-2 text-base"
          >
            <RadioGroupItem value={choice.value} className="mt-1" />
            <span className="flex flex-col">
              <span className="text-foreground">{choice.label}</span>
              {choice.description && (
                <span className="text-sm text-muted-foreground">
                  {choice.description}
                </span>
              )}
            </span>
          </label>
        ))}
      </RadioGroup>
    </div>
  );
}

/**
 * The income imputation election of one tax year, in the setup wizard's own
 * questions and words: what the profile states for the year (declared,
 * undeclared or contradictory), what the other years state, and the questions
 * with their served choices. The accounting question is drawn only while the
 * application says it is asked for the criterion chosen. A year the profile
 * does not state stays undeclared and no choice is preselected. A write
 * carries the revision the election was read at, and the election is read
 * again after it, whatever it came to.
 */
export function ImputationElection({
  profile,
  taxYear,
  language,
  reads,
  change,
}: {
  profile: string;
  taxYear: number;
  language: string;
  reads: Pick<ProfileCompanionPort, "imputationElection">;
  change(change: ProfileChange): Promise<void>;
}) {
  const t = useStrings();
  const heading = useId();
  const [read, setRead] = useState<Read>({ phase: "reading" });
  const [draft, setDraft] = useState<Draft>(NO_DRAFT);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const latest = useRef(0);
  const shown = useRef(false);
  const alive = useRef(true);

  const load = useCallback(async (): Promise<boolean> => {
    const ticket = ++latest.current;
    try {
      const election = await reads.imputationElection(
        profile,
        taxYear,
        language,
      );
      if (ticket !== latest.current) return false;
      shown.current = true;
      setRead({ phase: "ready", election });
      return true;
    } catch (error) {
      // A read that fails while an election is shown keeps it.
      if (ticket === latest.current && !shown.current)
        setRead({ phase: "failed", failure: failureOf(error) });
      return false;
    }
  }, [reads, profile, taxYear, language]);

  useEffect(() => {
    alive.current = true;
    shown.current = false;
    setRead({ phase: "reading" });
    setDraft(NO_DRAFT);
    setNotice(null);
    void load();
    return () => {
      alive.current = false;
      latest.current += 1;
    };
  }, [load]);

  const write = async (election: Election, edit: ChangeEdit) => {
    if (saving) return;
    setSaving(true);
    setNotice(null);
    let outcome: Notice;
    let keepDraft = false;
    try {
      await change({
        profile_id: election.profile_id,
        expected_revision: election.record_revision,
        expected_content_digest: election.content_digest,
        edit,
      });
      outcome = { kind: "saved" };
    } catch (error) {
      const failure = failureOf(error);
      outcome = { kind: "failed", failure };
      // Nothing was written after a refusal or a conflict, so what the
      // person chose can be sent again against the revision read next.
      keepDraft = failure.code === "refused" || failure.code === "conflict";
    }
    // Whatever it came to, what the profile states is read again.
    const reread = await load();
    if (!alive.current) return;
    if (!keepDraft) setDraft(NO_DRAFT);
    setNotice(
      outcome.kind === "saved" && !reread
        ? { kind: "failed", failure: { code: "saved_unread", words: null } }
        : outcome,
    );
    setSaving(false);
  };

  const title = t("workspace.modelo.election.title", { year: taxYear });
  const body = (() => {
    if (read.phase === "reading")
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          {t("workspace.modelo.election.reading")}
        </div>
      );
    if (read.phase === "failed")
      return (
        <div className="flex flex-col items-start gap-2">
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {read.failure.code === "not_signed_in"
              ? t("desktop.profile.signed_out")
              : t("desktop.profile.unavailable")}
          </Alert>
          <Button size="sm" variant="outline" onClick={() => void load()}>
            {t("workspace.modelo.election.retry")}
          </Button>
        </div>
      );
    const { election } = read;
    const storedCriterion = stated(election.criterion);
    const storedAccounting = stated(election.codigo_comercio_accounting);
    const chosen = draft.criterion ?? storedCriterion;
    // The application says for which criteria the question is asked.
    const asksAccounting =
      chosen !== null &&
      election.accounting_asked_for_criteria.includes(chosen);
    const criterionChanged =
      draft.criterion !== null && draft.criterion !== storedCriterion;
    const accountingChanged =
      asksAccounting &&
      draft.accounting !== null &&
      draft.accounting !== storedAccounting;
    const others = election.criterion_statements.filter(
      (statement) => statement.ejercicio !== election.tax_year,
    );
    const clearsCriterion = election.criterion.state !== "undeclared";
    const clearsAccounting =
      election.codigo_comercio_accounting.state !== "undeclared";
    const failure = notice?.kind === "failed" ? notice.failure : null;
    const mark = STATE[election.criterion.state];
    return (
      <>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Icon name={mark.icon} size="xs" className={mark.tone} />
          <span
            data-election-state={election.criterion.state}
            className="font-medium text-foreground"
          >
            {t(mark.words, { year: election.tax_year })}
          </span>
        </div>
        {election.criterion.state === "contradictory" && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {t("workspace.modelo.election.contradictory", {
              year: election.tax_year,
            })}
          </Alert>
        )}
        <Choices
          question={election.criterion_question}
          value={chosen}
          disabled={saving}
          onChange={(criterion) => setDraft((was) => ({ ...was, criterion }))}
        />
        {asksAccounting && (
          <Choices
            question={election.accounting_question}
            value={draft.accounting ?? storedAccounting}
            disabled={saving}
            onChange={(accounting) =>
              setDraft((was) => ({ ...was, accounting }))
            }
          />
        )}
        {others.length > 0 && (
          <div className="flex flex-col gap-1">
            <p className="text-sm font-medium text-foreground">
              {t("workspace.modelo.election.other_years")}
            </p>
            <ul className="flex flex-col text-sm text-muted-foreground">
              {others.map((statement) => (
                <li key={`${statement.ejercicio}-${statement.value}`}>
                  <span className="tabular-nums">{statement.ejercicio}</span>
                  {": "}
                  {election.criterion_question.choices.find(
                    (choice) => choice.value === statement.value,
                  )?.label ?? statement.value}
                </li>
              ))}
            </ul>
          </div>
        )}
        {notice?.kind === "saved" && (
          <Alert tone="success" icon={<Icon name="check" />}>
            {t("workspace.modelo.election.saved", { year: election.tax_year })}
          </Alert>
        )}
        {failure && (
          <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
            <span>
              {failure.words ??
                t(FAILURE_WORDS[failure.code] ?? "desktop.profile.unavailable")}
            </span>
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            disabled={saving || !(criterionChanged || accountingChanged)}
            aria-busy={saving}
            onClick={() =>
              void write(election, {
                kind: "imputation_election",
                tax_year: election.tax_year,
                criterion: criterionChanged ? draft.criterion : null,
                codigo_comercio_accounting: accountingChanged
                  ? draft.accounting
                  : null,
              })
            }
          >
            {saving && <Icon name="loader" size="xs" />}
            {t("workspace.modelo.election.save", { year: election.tax_year })}
          </Button>
          {(clearsCriterion || clearsAccounting) && (
            <Button
              size="sm"
              variant="ghost"
              disabled={saving}
              onClick={() =>
                void write(election, {
                  kind: "imputation_election",
                  tax_year: election.tax_year,
                  // An empty token clears the year; a question that states
                  // nothing is left as it is.
                  criterion: clearsCriterion ? "" : null,
                  codigo_comercio_accounting: clearsAccounting ? "" : null,
                })
              }
            >
              {t("workspace.modelo.election.clear", {
                year: election.tax_year,
              })}
            </Button>
          )}
        </div>
      </>
    );
  })();

  return (
    <section
      aria-labelledby={heading}
      className="flex flex-col gap-3 rounded-lg border border-border bg-background p-4"
    >
      <h4 id={heading} className="text-base font-medium text-foreground">
        {title}
      </h4>
      {body}
    </section>
  );
}

type ChangeEdit = Extract<
  ProfileChange["edit"],
  { kind: "imputation_election" }
>;
