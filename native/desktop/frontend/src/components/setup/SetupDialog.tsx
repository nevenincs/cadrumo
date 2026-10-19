import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type {
  SetupItemId,
  SetupItemProgress,
  SetupReview,
  SetupRow,
  SetupRun,
  SetupSnapshot,
} from "../../ipc/contract";
import { needsSetup, type SetupControl } from "../../shell/setup";
import { useStrings, type Translate } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { SetupRowItem } from "./SetupRowItem";
import {
  outcomeWords,
  overallShare,
  refusalWords,
  stepWords,
} from "./setupWords";

// The setup flow: one summary and one primary action. Cadrumo's components
// are set up in order by one setup, whose overall progress is the summary
// while it runs; what each component is, the plan's detail per component and
// each one's progress stay in a "Details" disclosure, closed until opened.
// The dialog never holds the window: closing it leaves a running setup
// running, and Settings keeps saying so.

/** The items a start asks for: the one the dialog was opened on, or every
 * item not ready. */
function startItems(focus: SetupItemId | null): SetupItemId[] | null {
  return focus === null ? null : [focus];
}

/** The per-component detail, closed until the person opens it. */
function Details({ children }: { children: ReactNode }) {
  const t = useStrings();
  return (
    <details data-setup-details className="group/details grid gap-2">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <Icon
          name="forward"
          className="transition-transform group-open/details:rotate-90"
        />
        {t("desktop.setup.details")}
      </summary>
      <div className="mt-2 grid gap-2">{children}</div>
    </details>
  );
}

/** What the plan downloads in all, said once above the detail. */
function planSize(t: Translate, review: SetupReview, locale: string): string {
  const size = formatSize(locale, review.known_download_bytes);
  if (review.has_unknown_size)
    return t("desktop.setup.plan_size_at_least", { size });
  return review.known_download_bytes > 0
    ? t("desktop.setup.plan_size", { size })
    : t("desktop.setup.plan_nothing");
}

function PlanSummary({
  review,
  locale,
}: {
  review: SetupReview;
  locale: string;
}) {
  const t = useStrings();
  const size = (bytes: number) => formatSize(locale, bytes);
  // What an approval also agrees to is said here, never only in the detail.
  const notices = [
    ...new Set(
      review.entries
        .map((entry) => entry.licence_notice)
        .filter((notice): notice is string => notice !== null),
    ),
  ];
  return (
    <div className="grid gap-2 text-sm text-foreground">
      <p data-setup-plan-size>{planSize(t, review, locale)}</p>
      <p>
        {review.free_bytes === null
          ? t("desktop.setup.space_unread", {
              required: size(review.required_bytes),
            })
          : t("desktop.setup.space", {
              required: size(review.required_bytes),
              free: size(review.free_bytes),
            })}
      </p>
      {review.installs_outside_program && (
        <p>{t("desktop.setup.plan_outside_program")}</p>
      )}
      {notices.map((notice) => (
        <p key={notice} data-setup-licence className="text-muted-foreground">
          {notice}
        </p>
      ))}
      {!review.space_sufficient && (
        <Alert role="alert">{t("desktop.setup.space_short")}</Alert>
      )}
    </div>
  );
}

function PlanDetail({
  review,
  locale,
  names,
}: {
  review: SetupReview;
  locale: string;
  names: Map<SetupItemId, string>;
}) {
  const t = useStrings();
  const size = (bytes: number | null) =>
    bytes === null
      ? t("desktop.setup.size_unknown")
      : formatSize(locale, bytes);
  return (
    <ul className="setup-plan grid gap-2">
      {review.entries.map((entry) => (
        <li
          key={entry.item}
          data-setup-plan={entry.item}
          className="grid gap-0.5 rounded-lg border bg-card p-3 text-sm"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="font-medium text-foreground">{entry.name}</span>
            <span className="text-muted-foreground">
              {size(entry.download_bytes)}
            </span>
          </div>
          {entry.parts.length > 0 && (
            <ul className="grid gap-0.5 text-muted-foreground">
              {entry.parts.map((part) => (
                <li
                  key={part.part}
                  data-setup-part={part.part}
                  className="flex flex-wrap justify-between gap-x-2"
                >
                  <span>{part.name}</span>
                  {part.download_bytes !== 0 && (
                    <span>{size(part.download_bytes)}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {entry.source_hosts.length > 0 && (
            <p className="text-muted-foreground wrap-anywhere">
              {t("desktop.setup.plan_from", {
                hosts: entry.source_hosts.join(", "),
              })}
            </p>
          )}
          {entry.destination !== null && (
            <p className="text-muted-foreground wrap-anywhere">
              {t("desktop.setup.plan_destination", {
                folder: entry.destination,
              })}
            </p>
          )}
          {entry.shares_download_with !== null && (
            <p className="text-muted-foreground">
              {t("desktop.setup.plan_shared", {
                name:
                  names.get(entry.shares_download_with) ??
                  entry.shares_download_with,
              })}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function ItemProgress({
  progress,
  locale,
}: {
  progress: SetupItemProgress;
  locale: string;
}) {
  const t = useStrings();
  const { completed, total, result, retry } = progress;
  const determinate = completed !== null && total !== null && total > 0;
  return (
    <li
      data-setup-progress={progress.item}
      className="grid gap-1.5 rounded-lg border bg-card p-3 text-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <span className="font-medium text-foreground">{progress.name}</span>
        <span className="text-muted-foreground">
          {result
            ? result.failure
              ? t("desktop.setup.result_not_finished")
              : result.changed
                ? t("desktop.setup.result_done")
                : t("desktop.setup.result_already")
            : stepWords(t, progress.step)}
        </span>
      </div>
      {!result && determinate && (
        <>
          <Progress
            value={completed}
            max={total}
            aria-label={t("desktop.setup.progress_label", {
              name: progress.name,
            })}
          />
          <span className="text-muted-foreground">
            {t("desktop.setup.progress_bytes", {
              done: formatSize(locale, completed),
              total: formatSize(locale, total),
            })}
          </span>
        </>
      )}
      {retry && !result && (
        <p role="status" className="text-foreground">
          {retry.sentence}
        </p>
      )}
      {result?.sentence && (
        <p role="alert" className="text-foreground">
          {result.sentence}
        </p>
      )}
    </li>
  );
}

/** The running setup as one figure: where it is, and how far over every
 * component it planned. */
function Overall({ run }: { run: SetupRun }) {
  const t = useStrings();
  const index = run.items.findIndex((item) => item.result === null);
  const current = index >= 0 ? run.items[index] : undefined;
  const share = overallShare(run);
  return (
    <div data-setup-overall className="grid gap-2 text-sm">
      <p className="flex items-center gap-2 text-foreground">
        <Spinner />
        {current
          ? t("desktop.setup.progress_item", {
              index: index + 1,
              count: run.items.length,
              name: current.name,
              step: stepWords(t, current.step),
            })
          : t("desktop.setup.summary_running")}
      </p>
      <Progress
        value={Math.round(share * 100)}
        max={100}
        aria-label={t("desktop.setup.overall_progress")}
      />
      {current?.retry && (
        <p role="status" className="text-foreground">
          {current.retry.sentence}
        </p>
      )}
    </div>
  );
}

/** What the footer's main button does now, and what it says. */
function mainAction(
  t: Translate,
  run: SetupRun | null,
  rows: SetupRow[],
): { label: string; resume: boolean } | null {
  if (run && run.stage !== "settled") return null;
  switch (run?.outcome) {
    case "interrupted":
      return { label: t("desktop.setup.resume"), resume: true };
    case "plan_changed":
      return { label: t("desktop.setup.show_new_plan"), resume: false };
    case "failed":
    case "cancelled":
    case "not_enough_space":
      return { label: t("desktop.setup.try_again"), resume: false };
    default:
      return rows.some(needsSetup)
        ? {
            label: rows.some((row) => row.recovery === "resume")
              ? t("desktop.setup.resume")
              : t("desktop.setup.start"),
            resume: rows.some((row) => row.recovery === "resume"),
          }
        : null;
  }
}

function approveLabel(t: Translate, review: SetupReview, locale: string) {
  if (review.known_download_bytes <= 0) return t("desktop.setup.approve");
  const size = formatSize(locale, review.known_download_bytes);
  return review.has_unknown_size
    ? t("desktop.setup.approve_at_least", { size })
    : t("desktop.setup.approve_size", { size });
}

function summaryWords(t: Translate, snapshot: SetupSnapshot): string {
  return snapshot.complete
    ? t("desktop.setup.summary_complete")
    : snapshot.hardware_limited
      ? t("desktop.setup.summary_hardware")
      : t("desktop.setup.summary_incomplete");
}

export function SetupDialog({
  open,
  onOpenChange,
  control,
  focus,
  locale,
  onAct,
  onCopyDetails,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  control: SetupControl;
  /** The item the dialog was opened for; null for every item. */
  focus: SetupItemId | null;
  locale: string;
  /** A row's own button, for what the main button does not do: checking
   * again. */
  onAct: (row: SetupRow) => void;
  onCopyDetails: (details: string) => void;
}) {
  const t = useStrings();
  const snapshot: SetupSnapshot | null = control.snapshot;
  const run = snapshot?.setup ?? null;
  const stage = run?.stage ?? null;
  const rows = (snapshot?.rows ?? []).filter(
    (row) => focus === null || row.item === focus,
  );
  const names = new Map(
    (snapshot?.rows ?? []).map((row) => [row.item, row.name] as const),
  );
  const main = snapshot ? mainAction(t, run, rows) : null;
  const description =
    stage === "review"
      ? t("desktop.setup.lead_review")
      : stage === "running" || stage === "planning"
        ? t("desktop.setup.lead_running")
        : t("desktop.setup.lead");
  const rowList = (
    <ul className="grid gap-2">
      {rows.map((row) => (
        <SetupRowItem
          key={row.item}
          row={row}
          locale={locale}
          disabled={control.pending}
          onAct={needsSetup(row) ? undefined : onAct}
        />
      ))}
    </ul>
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        placement="top"
        closeLabel={t("desktop.setup.close")}
        className="setup-dialog overflow-y-auto"
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.setup.title")}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {control.read.kind === "loading" ||
        (snapshot !== null && snapshot.rows.length === 0) ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            {t("desktop.setup.checking")}
          </p>
        ) : control.read.kind === "failed" ? (
          <Alert role="alert">{refusalWords(t, control.read.code)}</Alert>
        ) : snapshot === null ? (
          <p className="text-sm text-foreground">
            {t("desktop.setup.unavailable")}
          </p>
        ) : stage === "planning" ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner />
            {t("desktop.setup.planning")}
          </p>
        ) : stage === "review" && run?.review ? (
          <>
            <PlanSummary review={run.review} locale={locale} />
            <Details>
              <PlanDetail review={run.review} locale={locale} names={names} />
            </Details>
          </>
        ) : stage === "running" && run ? (
          <>
            <Overall run={run} />
            {run.cancel_requested && (
              <p role="status" className="text-sm text-muted-foreground">
                {t("desktop.setup.cancelling")}
              </p>
            )}
            <Details>
              <ul className="grid gap-2">
                {run.items.map((progress) => (
                  <ItemProgress
                    key={progress.item}
                    progress={progress}
                    locale={locale}
                  />
                ))}
              </ul>
            </Details>
          </>
        ) : (
          <>
            {stage === "settled" && run?.outcome ? (
              <Alert role={run.outcome === "completed" ? "status" : "alert"}>
                {outcomeWords(t, run.outcome, run.failure_sentence)}
              </Alert>
            ) : (
              <p data-setup-summary className="text-sm text-foreground">
                {summaryWords(t, snapshot)}
              </p>
            )}
            <Details>
              {stage === "settled" && run && run.items.length > 0 && (
                <ul className="grid gap-2">
                  {run.items.map((progress) => (
                    <ItemProgress
                      key={progress.item}
                      progress={progress}
                      locale={locale}
                    />
                  ))}
                </ul>
              )}
              {rowList}
            </Details>
          </>
        )}

        {control.refusal && (
          <Alert role="alert">{refusalWords(t, control.refusal)}</Alert>
        )}

        <DialogFooter>
          {snapshot?.details && (
            <Button
              variant="ghost"
              size="sm"
              className="mr-auto"
              onClick={() => onCopyDetails(snapshot.details)}
            >
              {t("desktop.setup.copy_details")}
            </Button>
          )}
          {stage === "review" ? (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={control.pending}
                onClick={() => control.answer("reject")}
              >
                {t("desktop.setup.reject")}
              </Button>
              {run?.review && (
                <Button
                  size="sm"
                  disabled={control.pending || !run.review.space_sufficient}
                  onClick={() => control.answer("apply")}
                >
                  {approveLabel(t, run.review, locale)}
                </Button>
              )}
            </>
          ) : (
            <>
              {(stage === "running" || stage === "planning") && run && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={
                    control.pending || !run.cancellable || run.cancel_requested
                  }
                  onClick={() => control.cancel()}
                >
                  {t("desktop.setup.cancel")}
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                {stage === "running" || stage === "planning"
                  ? t("desktop.setup.hide")
                  : snapshot?.complete
                    ? t("desktop.setup.close")
                    : t("desktop.setup.not_now")}
              </Button>
              {main && (
                <Button
                  size="sm"
                  disabled={control.pending}
                  onClick={() => {
                    control.clearRefusal();
                    control.start(startItems(focus), {
                      resume: main.resume,
                    });
                  }}
                >
                  {main.label}
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
