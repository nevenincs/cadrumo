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
import {
  liveRuns,
  needsSetup,
  runOf,
  type SetupControl,
} from "../../shell/setup";
import { useStrings, type Translate } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { SetupRowItem } from "./SetupRowItem";
import {
  failureWords,
  itemName,
  outcomeWords,
  overallShare,
  partName,
  refusalWords,
  retryWords,
  rowTone,
  stepWords,
} from "./setupWords";

// The setup flow: one summary and one primary action. Each component has a
// setup of its own; the dialog shows one of them, whose overall progress is
// the summary while it runs; what each component is, the plan's detail per
// component and each one's progress stay in a "Details" disclosure, closed
// until opened. The dialog never holds the window: closing it leaves a
// running setup running, and Settings keeps saying so. Opened on the browser,
// it is the browser's own flow: its rows, its plan and its progress only.

/** The setup the dialog shows: the focused item's, else one awaiting an
 * answer, else one running, else the first. */
function shownRun(
  snapshot: SetupSnapshot | null,
  focus: SetupItemId | null,
): SetupRun | null {
  if (focus !== null) return runOf(snapshot, focus);
  const runs = snapshot?.runs ?? [];
  return (
    runs.find((run) => run.stage === "review") ??
    liveRuns(snapshot)[0] ??
    runs[0] ??
    null
  );
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

export function PlanSummary({
  review,
  locale,
}: {
  review: SetupReview;
  locale: string;
}) {
  const t = useStrings();
  const size = (bytes: number) => formatSize(locale, bytes);
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
      {!review.space_sufficient && (
        <Alert role="alert">{t("desktop.setup.space_short")}</Alert>
      )}
    </div>
  );
}

export function PlanDetail({
  review,
  locale,
}: {
  review: SetupReview;
  locale: string;
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
          className="grid gap-0.5 rounded-lg bg-accent p-3 text-sm"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="font-medium text-foreground">
              {itemName(t, entry.item)}
            </span>
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
                  <span>
                    {partName(t, part.part)}
                    {part.model && <>: {part.model}</>}
                  </span>
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
                name: itemName(t, entry.shares_download_with),
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
      className="grid gap-1.5 rounded-lg bg-accent p-3 text-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <span className="font-medium text-foreground">
          {itemName(t, progress.item)}
        </span>
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
              name: itemName(t, progress.item),
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
          {retryWords(t, retry)}
        </p>
      )}
      {result?.failure && (
        <p role="alert" className="text-foreground">
          {failureWords(t, result.failure)}
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
              name: itemName(t, current.item),
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
          {retryWords(t, current.retry)}
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

export function approveLabel(
  t: Translate,
  review: SetupReview,
  locale: string,
) {
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
  onLocalAi,
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
  onLocalAi?: () => void;
}) {
  const t = useStrings();
  const snapshot: SetupSnapshot | null = control.snapshot;
  const rows = (snapshot?.rows ?? []).filter(
    (row) => focus === null || row.item === focus,
  );
  // An item's id is its kind, so the flow is known before its row is read.
  const browserFlow =
    focus !== null &&
    (rows.find((row) => row.item === focus)?.kind ?? focus) === "browser";
  const run = shownRun(snapshot, focus);
  const stage = run?.stage ?? null;
  const main = snapshot ? mainAction(t, run, rows) : null;
  const usable =
    rows.length > 0 && rows.every((row) => rowTone(row) === "ready");
  // A check the engine refused under a category of its own, such as a setting
  // it cannot use, or that was refused because the person's selection of local
  // models could not be admitted: it reports no row, so its sentence is the
  // only thing to say.
  const checkFailure =
    snapshot?.check?.stage === "failed" ? snapshot.check.failure : null;
  // Only the local AI's selection of models is refused this way.
  const checkRefusal =
    snapshot?.check?.stage === "failed" && !browserFlow
      ? snapshot.check.refusal
      : null;
  const description =
    stage === "review"
      ? t("desktop.setup.lead_review")
      : stage === "running" || stage === "planning"
        ? t("desktop.setup.lead_running")
        : browserFlow
          ? t("desktop.setup.browser_lead")
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
          <DialogTitle>
            {browserFlow
              ? t("desktop.setup.browser_title")
              : t("desktop.setup.title")}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {checkFailure !== null && (
          <Alert role="alert">{failureWords(t, checkFailure)}</Alert>
        )}
        {checkRefusal !== null && (
          <Alert role="alert">{refusalWords(t, checkRefusal)}</Alert>
        )}

        {control.read.kind === "loading" ||
        (snapshot !== null &&
          snapshot.rows.length === 0 &&
          checkFailure === null &&
          checkRefusal === null) ? (
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
              <PlanDetail review={run.review} locale={locale} />
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
                {outcomeWords(t, run.outcome, run.failure)}
              </Alert>
            ) : (
              !browserFlow && (
                <p data-setup-summary className="text-sm text-foreground">
                  {summaryWords(t, snapshot)}
                </p>
              )
            )}
            {/* The browser's one row is its summary, said once. */}
            {browserFlow && rowList}
            {(!browserFlow ||
              (stage === "settled" && run && run.items.length > 0)) && (
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
                {!browserFlow && rowList}
              </Details>
            )}
          </>
        )}

        {control.refusal && (
          <Alert role="alert">{refusalWords(t, control.refusal)}</Alert>
        )}

        <DialogFooter>
          {onLocalAi &&
            rows.some((row) => row.kind === "local_ai") &&
            (stage === null || stage === "settled") && (
              <Button variant="outline" size="sm" onClick={onLocalAi}>
                {t("desktop.providers.local_models_title")}
              </Button>
            )}
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
                onClick={() => run && control.answer(run.item, "reject")}
              >
                {t("desktop.setup.reject")}
              </Button>
              {run?.review && (
                <Button
                  size="sm"
                  disabled={control.pending || !run.review.space_sufficient}
                  onClick={() => control.answer(run.item, "apply")}
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
                  onClick={() => control.cancel(run.item)}
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
                  : (browserFlow ? usable : snapshot?.complete)
                    ? t("desktop.setup.close")
                    : t("desktop.setup.not_now")}
              </Button>
              {/* A browser row with no button of its own is checked again
                  from the flow's footer. */}
              {browserFlow &&
                !main &&
                stage !== "running" &&
                stage !== "planning" &&
                rows.length > 0 &&
                rows.every((row) => row.recovery === null) && (
                  <Button
                    size="sm"
                    disabled={control.pending}
                    onClick={() => {
                      control.clearRefusal();
                      control.verify(rows.map((row) => row.item));
                    }}
                  >
                    {t("desktop.setup.action.check_again")}
                  </Button>
                )}
              {main && (
                <Button
                  size="sm"
                  disabled={control.pending}
                  onClick={() => {
                    control.clearRefusal();
                    // Each item is set up on its own: the one the dialog was
                    // opened on, or every one that can be set up.
                    const wanted =
                      focus === null
                        ? rows.filter(needsSetup).map((row) => row.item)
                        : [focus];
                    for (const item of wanted)
                      control.start(item, { resume: main.resume });
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
