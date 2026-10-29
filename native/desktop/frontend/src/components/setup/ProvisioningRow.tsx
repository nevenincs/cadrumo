import { useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type {
  SetupItemResult,
  SetupOutcome,
  SetupRetry,
  SetupRow,
  SetupRun,
  SetupStep,
} from "../../ipc/contract";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { approveLabel, PlanEntry, PlanSummary } from "./SetupPlan";
import {
  actionWords,
  failureWords,
  itemName,
  outcomeWords,
  retryWords,
  rowSentence,
  rowSizeWords,
  rowTone,
  stepWords,
} from "./setupWords";

// One element of the provisioning panel: its name, then its status said
// once -- the row's sentence, or in its place what its own setup is doing
// now -- its size, and its own controls. Each row's setup runs on its own,
// beside any other row's, and goes on after the panel closes.

/** Settled outcomes the row's sentence does not already tell: the row
 * still reads as it did before the setup, so the outcome says why. */
const TOLD_OUTCOMES: ReadonlySet<SetupOutcome> = new Set([
  "rejected",
  "cancelled",
  "plan_changed",
  "not_enough_space",
]);

/** Whether `run` failed in a way `row` does not say: a setup refused before
 * it changed anything, by its network check for one, leaves the row as it
 * was, so the setup's own category says why it did not set anything up. */
function failedUntold(run: SetupRun | null, row: SetupRow): boolean {
  return (
    run?.stage === "settled" &&
    run.outcome === "failed" &&
    row.state !== "failed" &&
    row.state !== "blocked"
  );
}

/** A setup's progress on one item or one of its parts. */
export type StepProgress = {
  step: SetupStep | null;
  completed: number | null;
  total: number | null;
  result: SetupItemResult | null;
  retry?: SetupRetry | null;
};

/** A row's state said once: its sentence, marked by a glyph that repeats
 * nothing. */
export function RowState({ row }: { row: SetupRow }) {
  const t = useStrings();
  const tone = rowTone(row);
  return (
    <p className="flex items-start gap-2 text-sm text-foreground">
      {tone === "working" ? (
        <Spinner className="mt-0.5" />
      ) : (
        <Icon
          name={tone === "ready" ? "check" : "info"}
          className={
            tone === "ready" ? "mt-0.5 text-success" : "mt-0.5 text-faint"
          }
        />
      )}
      <span data-setup-sentence>{rowSentence(t, row)}</span>
    </p>
  );
}

/** Where a setup is with one item or part: its step, its bytes where they
 * are known, its retry notice, and once it ends, how it ended. */
export function StepFigure({
  progress,
  name,
  locale,
}: {
  progress: StepProgress;
  name: string;
  locale: string;
}) {
  const t = useStrings();
  const { completed, total, result, retry } = progress;
  if (result)
    return (
      <p
        data-setup-sentence
        role={result.failure ? "alert" : undefined}
        className="flex items-start gap-2 text-sm text-foreground"
      >
        <Icon
          name={result.failure ? "alert" : "check"}
          className={cn(
            "mt-0.5",
            result.failure ? "text-destructive" : "text-success",
          )}
        />
        <span>
          {result.failure
            ? failureWords(t, result.failure)
            : result.changed
              ? t("desktop.setup.result_done")
              : t("desktop.setup.result_already")}
        </span>
      </p>
    );
  const determinate = completed !== null && total !== null && total > 0;
  return (
    <div data-setup-progress className="grid gap-1.5 text-sm">
      <p className="flex items-center gap-2 text-foreground">
        <Spinner />
        <span data-setup-sentence>{stepWords(t, progress.step)}</span>
        {/* Before its first byte the bar alone says the download began;
            a count of none would read as a size. */}
        {determinate && completed > 0 && (
          <span className="ml-auto text-muted-foreground">
            {t("desktop.setup.progress_bytes", {
              done: formatSize(locale, completed),
              total: formatSize(locale, total),
            })}
          </span>
        )}
      </p>
      {determinate && (
        <Progress
          value={completed}
          max={total}
          aria-label={t("desktop.setup.progress_label", { name })}
        />
      )}
      {retry && (
        <p role="status" className="text-foreground">
          {retryWords(t, retry)}
        </p>
      )}
    </div>
  );
}

/** The plan `run` awaits an answer on, inside its row: what it downloads,
 * the space it needs, its parts and where they come from, and the row's
 * own approve and reject. */
function RowReview({ run, locale }: { run: SetupRun; locale: string }) {
  const t = useStrings();
  const store = useProvisioning();
  const review = run.review;
  if (!review) return null;
  return (
    <div data-setup-review className="grid gap-2">
      <p data-setup-sentence className="text-sm text-foreground">
        {t("desktop.setup.lead_review")}
      </p>
      <PlanSummary review={review} locale={locale} />
      <ul className="setup-plan grid gap-2">
        {review.entries.map((entry) => (
          <PlanEntry
            key={entry.item}
            entry={entry}
            locale={locale}
            named={entry.item !== run.item}
          />
        ))}
      </ul>
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={store.control.busy(run.item)}
          onClick={() => store.control.answer(run.item, "reject")}
        >
          {t("desktop.setup.reject")}
        </Button>
        <Button
          size="sm"
          disabled={store.control.busy(run.item) || !review.space_sufficient}
          onClick={() => store.control.answer(run.item, "apply")}
        >
          {approveLabel(t, review, locale)}
        </Button>
      </div>
    </div>
  );
}

/**
 * One row of the panel, for any row the engine reports. `progress` is what
 * the row's running setup reports for it: the item's own, by default, or
 * one part's where the row stands for a part of a larger item. `heading`
 * names it where the item's name is said elsewhere; `children` follow its
 * controls.
 */
export function ProvisioningRow({
  row,
  locale,
  heading,
  progress,
  className,
  children,
}: {
  row: SetupRow;
  locale: string;
  heading?: string;
  /** Null where the running setup has nothing of this row's to show: the
   * row then says its sentence. Absent for the item's own progress. */
  progress?: StepProgress | null;
  className?: string;
  children?: ReactNode;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const headingId = useId();
  const run = store.runOf(row.item);
  const live = run !== null && run.stage !== "settled";
  const shown = progress === undefined ? store.progressOf(row.item) : progress;
  const name = heading ?? itemName(t, row.item);
  const action = actionWords(t, row.recovery);
  let status: ReactNode;
  if (run?.stage === "planning")
    status = (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span data-setup-sentence>{t("desktop.setup.planning")}</span>
      </p>
    );
  else if (run?.stage === "review")
    status = <RowReview run={run} locale={locale} />;
  else if (run?.stage === "running" && shown)
    status = <StepFigure progress={shown} name={name} locale={locale} />;
  else if (run && failedUntold(run, row))
    status = (
      <p
        data-setup-sentence
        role="alert"
        className="flex items-start gap-2 text-sm text-foreground"
      >
        <Icon name="alert" className="mt-0.5 text-destructive" />
        <span>{outcomeWords(t, "failed", run.failure)}</span>
      </p>
    );
  else if (
    run?.stage === "settled" &&
    run.outcome &&
    TOLD_OUTCOMES.has(run.outcome)
  )
    status = (
      <p data-setup-sentence className="text-sm text-foreground">
        {outcomeWords(t, run.outcome, run.failure)}
      </p>
    );
  else status = <RowState row={row} />;
  return (
    <li
      data-setup-row={row.item}
      data-setup-tone={rowTone(row)}
      aria-labelledby={headingId}
      className={cn("grid gap-1.5 rounded-lg bg-accent p-3", className)}
    >
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-x-2">
        <h4
          id={headingId}
          className="min-w-0 font-medium wrap-anywhere text-foreground"
        >
          {name}
        </h4>
        {/* A ready row needs nothing, and an unknown one is checked again,
            not set up: neither states a download. */}
        {!live && row.state !== "ready" && row.state !== "unknown" && (
          <span data-setup-size className="text-sm text-muted-foreground">
            {rowSizeWords(t, row.size_bytes, (bytes) =>
              formatSize(locale, bytes),
            )}
          </span>
        )}
      </div>
      {status}
      {run?.cancel_requested && live && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.setup.cancelling")}
        </p>
      )}
      {/* A setup can be cancelled while its own start waits on its plan:
          only the setup itself says whether it still can be. */}
      {(run?.stage === "running" || run?.stage === "planning") && (
        <Button
          variant="outline"
          size="xs"
          className="justify-self-start"
          disabled={!run.cancellable || run.cancel_requested}
          onClick={() => store.control.cancel(run.item)}
        >
          {t("desktop.setup.cancel")}
        </Button>
      )}
      {!live && action && (
        <Button
          variant="outline"
          size="xs"
          className="justify-self-start"
          disabled={store.control.busy(row.item)}
          onClick={() => store.act(row)}
        >
          {action}
        </Button>
      )}
      {children}
    </li>
  );
}
