// The background jobs of the signed-in profile, as the window shows them:
// read through each job family's registered read and held only in memory.
// The host cues the window when a job's stored revision rises; a cue is only
// a reason to read, and the window reads a job again only when the cue names
// a revision newer than the one it holds. It also reads every job's revision
// when it subscribes and whenever the window regains focus, so an update a
// cue did not carry is still read. Nothing is read on a timer.
//
// A job is the backend's: the window starts, cancels, retries, dismisses and
// authorises it through the registered operations and shows what each one
// answered. When the window subscribes, a job left with movements still to
// ask and no run is run again, and the window says so.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  BackgroundTaskCue,
  BackgroundTaskRevisions,
} from "./backgroundTasksContract";
import {
  ledgerFailure,
  servedNextStep,
  servedRefusalWords,
  type LedgerFailureCode,
  type LedgerOutcome,
  type LedgerPort,
} from "./ledger";
import type {
  ClassificationConsentScope,
  ClassificationItemFailureCause,
  ClassificationJobStatus,
  LedgerClassifyJobChangeResult,
  LedgerClassifyJobProjection,
} from "./ledgerClassificationJobContract";
import type { OperationNextStepV1 } from "./ledgerDocumentContract";

/** The host's cues and the jobs' stored revisions for the signed-in
 * profile. */
export type BackgroundTasksPort = {
  /** Calls `listener` with each cue the host sends, until the returned
   * function unsubscribes. A change before subscribing is not cued: read
   * the revisions after it. */
  observe(listener: (cue: BackgroundTaskCue) => void): Promise<() => void>;
  /** Every background job's stored revision, read now. */
  revisions(): Promise<BackgroundTaskRevisions>;
};

/** The most jobs one list read asks for: the bound of the host's own read. */
export const JOB_LIST_LIMIT = 50;

/** A job whose run goes on or is still to start. */
const ACTIVE: ReadonlySet<ClassificationJobStatus> = new Set([
  "queued",
  "running",
  "cancelling",
]);

/** Whether `job` is being worked or waits to be. */
export const isActiveJob = (job: LedgerClassifyJobProjection) =>
  ACTIVE.has(job.status);

/** Whether `job` holds movements still to ask with no run to ask them:
 * one the window runs again when it subscribes. */
export function isResumable(job: LedgerClassifyJobProjection): boolean {
  return (
    job.counts.pending > 0 &&
    (job.status === "queued" ||
      job.status === "running" ||
      job.status === "interrupted")
  );
}

/** How many of a job's movements are asked, out of how many it holds. */
export function jobProgress(job: LedgerClassifyJobProjection): {
  done: number;
  total: number;
} {
  const counts = job.counts;
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  return {
    done: total - counts.pending - counts.running,
    total,
  };
}

/** Why a movement of a job did not get its proposal: its served cause,
 * `unknown` where an interrupted run left its outcome unknown, or `failed`
 * where no cause was served. */
export type JobFailure = ClassificationItemFailureCause | "unknown" | "failed";

function failureOf(
  item: LedgerClassifyJobProjection["items"][number],
): JobFailure | null {
  if (item.state === "failed") return item.failure_cause ?? "failed";
  return item.state === "unknown" ? "unknown" : null;
}

/** The job's failed movements by their cause, in the order a cause first
 * appears. */
export function failureGroups(
  job: LedgerClassifyJobProjection,
): { cause: JobFailure; count: number }[] {
  const groups = new Map<JobFailure, number>();
  for (const item of job.items) {
    const cause = failureOf(item);
    if (cause !== null) groups.set(cause, (groups.get(cause) ?? 0) + 1);
  }
  return [...groups].map(([cause, count]) => ({ cause, count }));
}

/** The causes that ask the person for an off-host consent. */
export const CONSENT_CAUSES: ReadonlySet<JobFailure> = new Set([
  "consent_required",
  "consent_revoked",
  "consent_expired",
]);

/** What one movement shows of the jobs that hold it. */
export type RowJobState =
  | { kind: "classifying"; job: string }
  | { kind: "proposed"; job: string }
  | { kind: "failed"; job: string; cause: JobFailure };

/** What each movement shows of the jobs, the newest job deciding where
 * several hold it. A dismissed job is not held at all. */
export function rowJobStates(
  jobs: readonly LedgerClassifyJobProjection[],
): Map<string, RowJobState> {
  const rows = new Map<string, RowJobState>();
  const newestFirst = [...jobs].sort((left, right) =>
    right.created_at.localeCompare(left.created_at),
  );
  for (const job of newestFirst) {
    const active = isActiveJob(job);
    for (const item of job.items) {
      if (rows.has(item.movement_id)) continue;
      const cause = failureOf(item);
      const state: RowJobState | null =
        (item.state === "pending" && active) || item.state === "running"
          ? { kind: "classifying", job: job.job_id }
          : item.state === "proposed"
            ? { kind: "proposed", job: job.job_id }
            : cause !== null
              ? { kind: "failed", job: job.job_id, cause }
              : null;
      if (state) rows.set(item.movement_id, state);
    }
  }
  return rows;
}

/** What a person's action on a job, or its run, came to. */
export type JobNotice =
  /** The window ran a job it found left with movements to ask. */
  | { kind: "resuming" }
  /** Another job's run holds the profile: this one starts when it ends. */
  | { kind: "waiting" }
  /** The operation settled and changed the job. */
  | { kind: "changed"; outcome: LedgerClassifyJobChangeResult["outcome"] }
  /** The operation was refused, with what the backend served for it. */
  | {
      kind: "refused";
      words: string | null;
      step: OperationNextStepV1 | null;
    }
  /** The call did not answer. */
  | { kind: "failed"; code: LedgerFailureCode };

export type JobAction = "cancel" | "retry" | "dismiss" | "authorise";

/** The jobs as the window holds them, and what it is doing to each. */
export type BackgroundTasks = {
  /** Whether this window can show background jobs at all. */
  offered: boolean;
  /** The jobs held, newest first; dismissed jobs are left out. */
  jobs: LedgerClassifyJobProjection[];
  /** Why the last read of the jobs failed, until one succeeds. */
  readFailure: LedgerFailureCode | null;
  notices: ReadonlyMap<string, JobNotice>;
  /** The action on each job still in flight. */
  busy: ReadonlyMap<string, JobAction>;
  act(
    job: LedgerClassifyJobProjection,
    action: Exclude<JobAction, "authorise">,
  ): void;
  authorise(
    job: LedgerClassifyJobProjection,
    scope: ClassificationConsentScope,
  ): void;
  /** What each movement shows of the jobs. */
  rows: ReadonlyMap<string, RowJobState>;
};

const NOT_OFFERED: BackgroundTasks = {
  offered: false,
  jobs: [],
  readFailure: null,
  notices: new Map(),
  busy: new Map(),
  act: () => undefined,
  authorise: () => undefined,
  rows: new Map(),
};

export const BackgroundTasksContext =
  createContext<BackgroundTasks>(NOT_OFFERED);

/** The background jobs the window holds. */
export function useBackgroundTasks(): BackgroundTasks {
  return useContext(BackgroundTasksContext);
}

/** The runtime's refusal of a run while another run holds the profile. */
const BUSY = "subject_busy";

/** The notice of an outcome that is not settled. */
function unsettledNotice(outcome: LedgerOutcome<unknown>): JobNotice | null {
  if (outcome.kind === "refused")
    return {
      kind: "refused",
      words: servedRefusalWords(outcome.detail),
      step: servedNextStep(outcome.detail),
    };
  return null;
}

/** Which jobs a set of revisions asks to read: those newer than what is
 * held or already being read. */
export function dueReads(
  wanted: ReadonlyMap<string, number>,
  held: ReadonlyMap<string, number>,
  reading: ReadonlySet<string>,
): string[] {
  return [...wanted]
    .filter(
      ([job, revision]) => !reading.has(job) && revision > (held.get(job) ?? 0),
    )
    .map(([job]) => job);
}

/**
 * Holds the signed-in profile's background jobs while `reader` names a
 * profile: subscribes to the host's cues, reads the revisions on subscribing
 * and on focus, reads a job again only for a newer revision, and runs again
 * a job left with movements to ask when it subscribes.
 */
export function useBackgroundTaskSource(
  tasks: BackgroundTasksPort | undefined,
  ledger: LedgerPort | undefined,
  reader: string | null,
): BackgroundTasks {
  const [jobs, setJobs] = useState<
    ReadonlyMap<string, LedgerClassifyJobProjection>
  >(() => new Map());
  const [readFailure, setReadFailure] = useState<LedgerFailureCode | null>(
    null,
  );
  const [notices, setNotices] = useState<ReadonlyMap<string, JobNotice>>(
    () => new Map(),
  );
  const [busy, setBusy] = useState<ReadonlyMap<string, JobAction>>(
    () => new Map(),
  );
  // What the subscription of the current profile reads with; replaced
  // whole when the profile or the ports change.
  const session = useRef<{
    active: boolean;
    startRun: (job: string, announce: boolean) => void;
    adopt: (job: LedgerClassifyJobProjection) => void;
    /** Reads every job's revision again. */
    refresh: () => void;
  } | null>(null);

  const notify = useCallback((job: string, notice: JobNotice | null) => {
    setNotices((current) => {
      const next = new Map(current);
      if (notice) next.set(job, notice);
      else next.delete(job);
      return next;
    });
  }, []);

  useEffect(() => {
    setJobs(new Map());
    setNotices(new Map());
    setBusy(new Map());
    setReadFailure(null);
    if (!tasks || !ledger || reader === null) return;
    const held = new Map<string, number>();
    const wanted = new Map<string, number>();
    const reading = new Set<string>();
    const store = new Map<string, LedgerClassifyJobProjection>();
    let profile: string | null = null;
    // Cues that came before the first revisions read named the profile.
    const early: BackgroundTaskCue[] = [];
    // Jobs to run again, one at a time: runs of one profile do not overlap.
    const resumeQueue: string[] = [];
    let resuming: string | null = null;
    // Jobs whose run was refused because another run held the profile.
    const waiting: string[] = [];
    const state: NonNullable<typeof session.current> = {
      active: true,
      startRun: () => undefined,
      adopt: () => undefined,
      refresh: () => undefined,
    };
    session.current = state;
    const publish = () => {
      if (state.active) setJobs(new Map(store));
    };
    const resumeNext = () => {
      while (resuming === null && resumeQueue.length > 0) {
        const next = resumeQueue.shift()!;
        const job = store.get(next);
        if (job && isResumable(job)) {
          resuming = next;
          startRun(next, true);
        }
      }
    };
    const adopt = (job: LedgerClassifyJobProjection) => {
      if (job.revision <= (held.get(job.job_id) ?? 0)) return;
      const before = store.get(job.job_id);
      held.set(job.job_id, job.revision);
      if (job.status === "dismissed") store.delete(job.job_id);
      else store.set(job.job_id, job);
      // A job no longer worked is no longer resuming or waiting.
      if (!isActiveJob(job) && !waiting.includes(job.job_id))
        setNotices((current) => {
          const kind = current.get(job.job_id)?.kind;
          if (kind !== "resuming" && kind !== "waiting") return current;
          const next = new Map(current);
          next.delete(job.job_id);
          return next;
        });
      // A run ended: the job resumed, or the one a run waited behind.
      if (
        !isActiveJob(job) &&
        (resuming === job.job_id ||
          before?.status === "running" ||
          before?.status === "cancelling")
      ) {
        if (resuming === job.job_id) resuming = null;
        resumeQueue.unshift(...waiting.splice(0));
        resumeNext();
      }
    };
    /** The run of `job` did not start: one refused because another run
     * holds the profile waits for it to end; any other says why. */
    const notStarted = (job: string, notice: JobNotice, busy: boolean) => {
      if (resuming === job) resuming = null;
      if (busy) {
        if (!waiting.includes(job)) waiting.push(job);
        notify(job, { kind: "waiting" });
        return;
      }
      notify(job, notice);
      resumeNext();
    };
    const startRun = (job: string, announce: boolean) => {
      if (announce) notify(job, { kind: "resuming" });
      // The run goes on in the background: its progress comes as cues, so
      // nothing waits on it.
      void ledger.submit("ledger.classify.job.run", { job_id: job }).then(
        (outcome) => {
          if (!state.active) return;
          if (outcome.kind === "settled") {
            if (outcome.result.profile_id === profile) {
              adopt(outcome.result.job);
              publish();
            }
            return;
          }
          const notice = unsettledNotice(outcome);
          if (notice && outcome.kind === "refused")
            notStarted(job, notice, outcome.reason === BUSY);
        },
        (error: unknown) => {
          if (!state.active) return;
          const failure = ledgerFailure(error);
          notStarted(
            job,
            { kind: "failed", code: failure.code },
            failure.reason === BUSY,
          );
        },
      );
    };
    state.startRun = startRun;
    state.adopt = (job) => {
      adopt(job);
      publish();
    };
    const failed = (error: unknown) => {
      if (state.active) setReadFailure(ledgerFailure(error).code);
    };
    const readOne = async (job: string) => {
      const outcome = await ledger.submit("ledger.classify.job.read", {
        job_id: job,
      });
      if (outcome.kind !== "settled") throw new Error("unavailable");
      if (outcome.result.profile_id !== profile) return;
      adopt(outcome.result.job);
    };
    const readList = async (due: readonly string[]) => {
      const outcome = await ledger.submit("ledger.classify.job.list", {
        limit: JOB_LIST_LIMIT,
        include_dismissed: true,
      });
      if (outcome.kind !== "settled") throw new Error("unavailable");
      if (outcome.result.profile_id !== profile) return;
      for (const job of outcome.result.jobs) adopt(job);
      // A job the list no longer holds is past its bound: it is not shown,
      // and its revision is not read again until it rises.
      for (const job of due)
        if (!outcome.result.jobs.some((found) => found.job_id === job)) {
          store.delete(job);
          held.set(job, Math.max(held.get(job) ?? 0, wanted.get(job) ?? 0));
        }
    };
    /** Reads the jobs whose wanted revision is newer than held, until none
     * is; one job is read alone and several with one list read. */
    const settleReads = async (): Promise<void> => {
      const due = dueReads(wanted, held, reading);
      if (due.length === 0 || !state.active) return;
      due.forEach((job) => reading.add(job));
      try {
        if (due.length === 1) await readOne(due[0]!);
        else await readList(due);
        if (state.active) setReadFailure(null);
      } catch (error) {
        failed(error);
        // A failed read leaves the wanted revision unread: the next cue,
        // subscription or focus asks again.
        due.forEach((job) => wanted.delete(job));
      } finally {
        due.forEach((job) => reading.delete(job));
      }
      publish();
      await settleReads();
    };
    const want = (job: string | null | undefined, revision: number) => {
      if (!job) return;
      wanted.set(job, Math.max(wanted.get(job) ?? 0, revision));
    };
    const onCue = (cue: BackgroundTaskCue) => {
      if (!state.active || cue.family !== "ledger_classification") return;
      if (profile === null) {
        early.push(cue);
        return;
      }
      if (cue.profile_id !== profile) return;
      want(cue.job_id, cue.revision);
      void settleReads();
    };
    const refresh = async () => {
      let read: BackgroundTaskRevisions;
      try {
        read = await tasks.revisions();
      } catch (error) {
        failed(error);
        return false;
      }
      if (!state.active) return false;
      if (profile !== null && read.profile_id !== profile) return false;
      profile = read.profile_id;
      for (const cue of early.splice(0))
        if (cue.profile_id === profile) want(cue.job_id, cue.revision);
      for (const task of read.tasks)
        if (task.family === "ledger_classification")
          want(task.job_id, task.revision);
      await settleReads();
      return state.active;
    };
    state.refresh = () => void refresh();
    let unobserve: (() => void) | null = null;
    void tasks.observe(onCue).then(
      (stop) => {
        if (!state.active) {
          stop();
          return;
        }
        unobserve = stop;
        void refresh().then((subscribed) => {
          if (!subscribed) return;
          // Jobs left with movements to ask and no run: run them again,
          // oldest first, saying so on each.
          const left = [...store.values()]
            .filter(isResumable)
            .sort((left, right) =>
              left.created_at.localeCompare(right.created_at),
            )
            .map((job) => job.job_id);
          resumeQueue.push(...left);
          resumeNext();
          publish();
        });
      },
      (error: unknown) => failed(error),
    );
    const focused = () => void refresh();
    window.addEventListener("focus", focused);
    return () => {
      state.active = false;
      session.current = null;
      window.removeEventListener("focus", focused);
      unobserve?.();
    };
  }, [tasks, ledger, reader, notify]);

  const settle = useCallback((job: string) => {
    setBusy((current) => {
      const next = new Map(current);
      next.delete(job);
      return next;
    });
  }, []);

  const change = useCallback(
    (
      job: LedgerClassifyJobProjection,
      action: JobAction,
      submit: () => Promise<LedgerOutcome<LedgerClassifyJobChangeResult>>,
    ) => {
      const owner = session.current;
      if (!owner || !ledger) return;
      setBusy((current) => new Map(current).set(job.job_id, action));
      notify(job.job_id, null);
      void submit()
        .then(
          (outcome) => {
            if (!owner.active) return;
            if (outcome.kind === "settled") {
              owner.adopt(outcome.result.job);
              notify(job.job_id, {
                kind: "changed",
                outcome: outcome.result.outcome,
              });
              // Movements asked again need a run to ask them.
              if (
                outcome.result.outcome === "retried" ||
                outcome.result.outcome === "authorised"
              )
                owner.startRun(job.job_id, false);
              return;
            }
            notify(
              job.job_id,
              unsettledNotice(outcome) ?? {
                kind: "failed",
                code: "unknown",
              },
            );
            // A refusal may come of a job that changed since it was read.
            if (outcome.kind === "refused") owner.refresh();
          },
          (error: unknown) => {
            if (owner.active)
              notify(job.job_id, {
                kind: "failed",
                code: ledgerFailure(error).code,
              });
          },
        )
        .finally(() => {
          if (owner.active) settle(job.job_id);
        });
    },
    [ledger, notify, settle],
  );

  const act = useCallback(
    (
      job: LedgerClassifyJobProjection,
      action: Exclude<JobAction, "authorise">,
    ) => {
      if (!ledger) return;
      const request = {
        job_id: job.job_id,
        expected_revision: job.revision,
      };
      change(job, action, () =>
        action === "cancel"
          ? ledger.submit("ledger.classify.job.cancel", request)
          : action === "retry"
            ? ledger.submit("ledger.classify.job.retry", request)
            : ledger.submit("ledger.classify.job.dismiss", request),
      );
    },
    [ledger, change],
  );

  const authorise = useCallback(
    (job: LedgerClassifyJobProjection, scope: ClassificationConsentScope) => {
      if (!ledger) return;
      change(job, "authorise", () =>
        ledger.submit("ledger.classify.job.authorise", {
          job_id: job.job_id,
          expected_revision: job.revision,
          consent: {
            scope,
            provider_id: job.lane.provider_id,
            connection: job.lane.transport,
            model: job.lane.model,
          },
        }),
      );
    },
    [ledger, change],
  );

  return useMemo(() => {
    const list = [...jobs.values()].sort((left, right) =>
      right.created_at.localeCompare(left.created_at),
    );
    return {
      offered: !!tasks && !!ledger && reader !== null,
      jobs: list,
      readFailure,
      notices,
      busy,
      act,
      authorise,
      rows: rowJobStates(list),
    };
  }, [tasks, ledger, reader, jobs, readFailure, notices, busy, act, authorise]);
}
