import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { formatDay } from "../../shared/dateFormats";
import {
  CONSENT_CAUSES,
  failureGroups,
  isActiveJob,
  jobProgress,
  useBackgroundTasks,
  type JobNotice,
} from "../../shell/backgroundTasks";
import type {
  ClassificationConsentScope,
  ClassificationJobStatus,
  LedgerClassifyJobChangeResult,
  LedgerClassifyJobProjection,
} from "../../shell/ledgerClassificationJobContract";
import type { LedgerFailureCode } from "../../shell/ledger";
import { countWords, useStrings, type Translate } from "../../shell/strings";
import { ConsentRemedies } from "../ledger/inspector/ConsentRemedies";
import { FAILURE_WORDS } from "./backgroundTaskWords";
import type { ConsentStep } from "../ledger/inspector/modelRefusal";

/** The words of each status a shown job can have. */
const STATUS_WORDS: Record<
  Exclude<ClassificationJobStatus, "dismissed">,
  string
> = {
  queued: "desktop.background_tasks.status.queued",
  running: "desktop.background_tasks.status.running",
  cancelling: "desktop.background_tasks.status.cancelling",
  interrupted: "desktop.background_tasks.status.interrupted",
  settled: "desktop.background_tasks.status.settled",
  cancelled: "desktop.background_tasks.status.cancelled",
};

/** The words of what each change to a job came to. */
const OUTCOME_WORDS: Record<LedgerClassifyJobChangeResult["outcome"], string> =
  {
    enqueued: "desktop.background_tasks.outcome.enqueued",
    cancelled: "desktop.background_tasks.outcome.cancelled",
    cancelling: "desktop.background_tasks.outcome.cancelling",
    retried: "desktop.background_tasks.outcome.retried",
    dismissed: "desktop.background_tasks.outcome.dismissed",
    authorised: "desktop.background_tasks.outcome.authorised",
    consent_revoked: "desktop.background_tasks.outcome.consent_revoked",
  };

const SCOPE_WORDS: Record<ClassificationConsentScope, string> = {
  once: "desktop.background_tasks.consent_scope.once",
  agent_session: "desktop.background_tasks.consent_scope.agent_session",
  remembered: "desktop.background_tasks.consent_scope.remembered",
};

const SCOPES: readonly ClassificationConsentScope[] = [
  "once",
  "agent_session",
  "remembered",
];

const callFailure = (t: Translate, code: LedgerFailureCode) =>
  t(
    code === "unknown"
      ? "desktop.background_tasks.call_unknown"
      : "desktop.background_tasks.call_failed",
  );

/** What a job is over: one movement, a selection, or a period. */
function scopeWords(
  t: Translate,
  locale: string,
  job: LedgerClassifyJobProjection,
): string {
  if (job.scope === "period" && job.period_start && job.period_end)
    return t("desktop.background_tasks.scope_period", {
      start: formatDay(locale, job.period_start),
      end: formatDay(locale, job.period_end),
    });
  return job.scope === "single"
    ? t("desktop.background_tasks.scope_single")
    : t("desktop.background_tasks.scope_selection", {
        count: job.items.length,
      });
}

/** The step a consent failure of `job` offers: authorise its lane, or
 * read with a model on this computer instead. */
function consentStep(
  t: Translate,
  cause: keyof typeof FAILURE_WORDS,
): ConsentStep {
  return {
    kind: "resolve_off_host_consent",
    words: t(FAILURE_WORDS[cause]),
    remedies: [
      {
        kind: "authorise_off_host",
        words: t("desktop.background_tasks.authorise"),
        unavailable_words: t("desktop.background_tasks.authorise"),
      },
      {
        kind: "switch_to_local_lane",
        words: t("desktop.background_tasks.switch_local"),
        unavailable_words: t("desktop.background_tasks.switch_local_elsewhere"),
      },
    ],
  };
}

/** How long the person lets the job's lane read off this computer: the
 * choice that records the grant. */
function ScopeChoice({
  onChoose,
  disabled,
}: {
  onChoose: (scope: ClassificationConsentScope) => void;
  disabled: boolean;
}) {
  const t = useStrings();
  return (
    <div
      role="group"
      aria-label={t("desktop.background_tasks.consent_scope_prompt")}
      className="background-task-scopes grid gap-1.5"
    >
      <span className="text-xs text-muted-foreground">
        {t("desktop.background_tasks.consent_scope_prompt")}
      </span>
      <span className="flex flex-wrap gap-1.5">
        {SCOPES.map((scope) => (
          <Button
            key={scope}
            size="xs"
            variant="outline"
            data-scope={scope}
            disabled={disabled}
            onClick={() => onChoose(scope)}
          >
            {t(SCOPE_WORDS[scope])}
          </Button>
        ))}
      </span>
    </div>
  );
}

function NoticeLine({
  notice,
  onAuthorise,
}: {
  notice: JobNotice;
  onAuthorise: () => void;
}) {
  const t = useStrings();
  if (notice.kind === "refused") {
    const step =
      notice.step?.kind === "resolve_off_host_consent" ? notice.step : null;
    return (
      <div className="grid gap-1.5" data-notice="refused">
        <span role="status" className="text-sm">
          {notice.words ??
            notice.step?.words ??
            t("desktop.background_tasks.refused")}
        </span>
        {step && <ConsentRemedies step={step} onAuthorise={onAuthorise} />}
      </div>
    );
  }
  return (
    <span
      role="status"
      data-notice={notice.kind}
      className="text-sm text-muted-foreground"
    >
      {notice.kind === "resuming"
        ? t("desktop.background_tasks.resuming")
        : notice.kind === "waiting"
          ? t("desktop.background_tasks.waiting")
          : notice.kind === "changed"
            ? t(OUTCOME_WORDS[notice.outcome])
            : callFailure(t, notice.code)}
    </span>
  );
}

function JobEntry({ job }: { job: LedgerClassifyJobProjection }) {
  const t = useStrings();
  const tasks = useBackgroundTasks();
  const [choosing, setChoosing] = useState(false);
  const busy = tasks.busy.get(job.job_id) ?? null;
  const notice = tasks.notices.get(job.job_id) ?? null;
  const { done, total } = jobProgress(job);
  const failures = failureGroups(job);
  const consent = failures.find((group) => CONSENT_CAUSES.has(group.cause));
  const active = isActiveJob(job);
  const retryable = failures.length > 0 && !active;
  const status = job.status === "dismissed" ? null : STATUS_WORDS[job.status];
  return (
    <li
      className="background-task grid gap-2 border-b border-border px-3 py-2.5 last:border-b-0"
      data-job={job.job_id}
      data-status={job.status}
      aria-busy={busy !== null || undefined}
    >
      <div className="flex min-w-0 items-baseline justify-between gap-2">
        <strong className="min-w-0 truncate text-sm">
          {t("desktop.background_tasks.job_title")}
        </strong>
        {status && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {t(status)}
          </span>
        )}
      </div>
      <span className="text-xs text-muted-foreground">
        {scopeWords(t, t.locale ?? "en", job)}
        {job.lane.reads_off_host &&
          ` · ${t("desktop.background_tasks.off_host", { model: job.lane.model })}`}
      </span>
      <Progress
        value={done}
        max={Math.max(total, 1)}
        aria-label={t("desktop.background_tasks.progress", { done, total })}
      />
      <span className="background-task-counts flex flex-wrap gap-x-3 text-xs">
        <span data-count="progress">
          {t("desktop.background_tasks.progress", { done, total })}
        </span>
        {job.counts.proposed > 0 && (
          <span data-count="proposed">
            {countWords(
              t,
              job.counts.proposed,
              {
                one: "desktop.background_tasks.proposed_one",
                other: "desktop.background_tasks.proposed",
              },
              { count: job.counts.proposed },
            )}
          </span>
        )}
        {failures.length > 0 && (
          <span data-count="failed" className="text-warning">
            {countWords(
              t,
              job.counts.failed + job.counts.unknown,
              {
                one: "desktop.background_tasks.failed_one",
                other: "desktop.background_tasks.failed",
              },
              { count: job.counts.failed + job.counts.unknown },
            )}
          </span>
        )}
      </span>
      {failures.length > 0 && (
        <ul
          className="background-task-failures grid gap-0.5 text-xs"
          aria-label={t("desktop.background_tasks.failures")}
        >
          {failures.map((group) => (
            <li key={group.cause} data-cause={group.cause}>
              {t("desktop.background_tasks.failure_group", {
                cause: t(FAILURE_WORDS[group.cause]),
                count: group.count,
              })}
            </li>
          ))}
        </ul>
      )}
      {consent && !active && (
        <ConsentRemedies
          step={consentStep(t, consent.cause)}
          onAuthorise={() => setChoosing(true)}
        />
      )}
      {choosing && (
        <ScopeChoice
          disabled={busy !== null}
          onChoose={(scope) => {
            setChoosing(false);
            tasks.authorise(job, scope);
          }}
        />
      )}
      {notice && (
        <NoticeLine notice={notice} onAuthorise={() => setChoosing(true)} />
      )}
      <span className="flex flex-wrap items-center gap-1.5">
        {busy !== null && <Spinner className="size-icon-xs" />}
        {active && job.status !== "cancelling" && (
          <Button
            size="xs"
            variant="outline"
            data-action="cancel"
            disabled={busy !== null}
            onClick={() => tasks.act(job, "cancel")}
          >
            {t("desktop.background_tasks.cancel")}
          </Button>
        )}
        {retryable && (
          <Button
            size="xs"
            variant="outline"
            data-action="retry"
            disabled={busy !== null}
            onClick={() => tasks.act(job, "retry")}
          >
            {t("desktop.background_tasks.retry")}
          </Button>
        )}
        {!active && (
          <Button
            size="xs"
            variant="ghost"
            data-action="dismiss"
            disabled={busy !== null}
            onClick={() => tasks.act(job, "dismiss")}
          >
            {t("desktop.background_tasks.dismiss")}
          </Button>
        )}
      </span>
    </li>
  );
}

/** The window's background tasks: a button that counts the jobs in
 * progress, and a panel of every job held with its progress, its failures
 * by cause and what can be done to it. */
export function BackgroundTasks() {
  const t = useStrings();
  const tasks = useBackgroundTasks();
  const [open, setOpen] = useState(false);
  if (!tasks.offered) return null;
  const active = tasks.jobs.filter(isActiveJob).length;
  // A job dismissed leaves the list: what dismissing came to stays said.
  const dismissed = [...tasks.notices].filter(
    ([job, notice]) =>
      notice.kind === "changed" &&
      notice.outcome === "dismissed" &&
      !tasks.jobs.some((held) => held.job_id === job),
  ).length;
  const failing = tasks.jobs.some(
    (job) => job.counts.failed + job.counts.unknown > 0,
  );
  const activeWords = countWords(
    t,
    active,
    {
      one: "desktop.background_tasks.active_one",
      other: "desktop.background_tasks.active",
    },
    { count: active },
  );
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="background-tasks-trigger relative text-foreground"
          data-active={active}
          aria-label={`${t("desktop.background_tasks.label")}: ${activeWords}`}
          title={t("desktop.background_tasks.label")}
        >
          {active > 0 ? (
            <Spinner className="size-icon-xs" />
          ) : (
            <Icon name="clock" />
          )}
          {active > 0 && (
            <Badge variant="count" aria-hidden="true">
              {active}
            </Badge>
          )}
          {failing && (
            <Icon
              name="alert"
              size="xs"
              className="text-warning"
              aria-hidden="true"
            />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        aria-label={t("desktop.background_tasks.label")}
        className="background-tasks-panel grid w-settings max-w-palette-max gap-0 p-0"
      >
        <div className="flex items-baseline justify-between gap-2 border-b border-border px-3 py-2">
          <strong className="text-sm">
            {t("desktop.background_tasks.label")}
          </strong>
          <span className="text-xs text-muted-foreground">{activeWords}</span>
        </div>
        {dismissed > 0 && (
          <span
            role="status"
            data-notice="dismissed"
            className="border-b border-border px-3 py-2 text-sm text-muted-foreground"
          >
            {t("desktop.background_tasks.outcome.dismissed")}
          </span>
        )}
        {tasks.readFailure !== null && (
          <span
            role="alert"
            data-read-failure={tasks.readFailure}
            className="px-3 py-2 text-sm text-warning"
          >
            {t("desktop.background_tasks.read_failed")}
          </span>
        )}
        {tasks.jobs.length === 0 ? (
          <p className="background-tasks-empty px-3 py-3 text-sm text-muted-foreground">
            {t("desktop.background_tasks.empty")}
          </p>
        ) : (
          <ul className="grid">
            {tasks.jobs.map((job) => (
              <JobEntry key={job.job_id} job={job} />
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
