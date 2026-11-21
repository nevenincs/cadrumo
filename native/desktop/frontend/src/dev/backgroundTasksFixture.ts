// The scenario host's background jobs: classification jobs held in this
// page's memory, answered through the ledger port's job definitions, and the
// host's cue channel and revisions read beside them. A job moves only when a
// scenario says so through `window.__scenarioBackgroundTasks`, and each move
// raises its revision and cues the window as the desktop host does. Nothing
// is read or moved on a timer. Everything here is synthetic.

import type { BackgroundTasksPort } from "../shell/backgroundTasks";
import type { BackgroundTaskCue } from "../shell/backgroundTasksContract";
import type {
  JsonObject,
  LedgerErrorDetail,
  LedgerOutcome,
} from "../shell/ledger";
import type {
  ClassificationItemFailureCause,
  LedgerClassifyJobApplyItemResult,
  LedgerClassifyJobApplyRefusal,
  ClassificationItemState,
  ClassificationJobStatus,
  LedgerClassifyJobItemProjection,
  LedgerClassifyJobLaneProjection,
  LedgerClassifyJobProjection,
} from "../shell/ledgerClassificationJobContract";
import { fixtureYear } from "./fixtureDates";
import {
  fixtureLedger,
  hex64,
  LEDGER_FIXTURE_PROFILE_ID,
  LEDGER_FIXTURE_TODAY,
} from "./fixtures/ledger";
import { reject } from "./ledgerRequestFixture";

/** The jobs a scenario can start with, named in its address as
 * `jobs=progress,consent`. */
export const JOB_SHAPES = ["progress", "consent", "resume", "settled"] as const;
export type JobShape = (typeof JOB_SHAPES)[number];

declare global {
  interface Window {
    /** Moves the scenario's background jobs, as a run in the profile's
     * worker would, and reads what the window asked of them. */
    __scenarioBackgroundTasks?: {
      /** The id of the job a shape starts. */
      job(shape: JobShape): string;
      /** The movements a job holds, in order. */
      movements(job: string): string[];
      /** One more movement asked: proposed, or failed for `cause`. Cued
       * unless `silently`. */
      step(
        job: string,
        options?: {
          cause?: ClassificationItemFailureCause;
          silently?: boolean;
        },
      ): void;
      /** Every movement still to ask proposed, and the run ended. */
      finish(job: string): void;
      /** The proposals applied, as the ledger review would. */
      apply(job: string): void;
      /** The jobs the window asked for, in order. */
      enqueued(): string[];
      /** The next apply of `movement` is refused for `cause`. */
      refuseApply(movement: string, cause: LedgerClassifyJobApplyRefusal): void;
      /** A cue for the job at `revision`, or its own revision. */
      cue(job: string, revision?: number): void;
      /** A cue naming another profile, at a revision past the job's. */
      cueOtherProfile(job: string): void;
      /** How many cue subscriptions are open. */
      observers(): number;
      /** The jobs a run was asked for, in order. */
      runs(): string[];
    };
  }
}

const LOCAL_LANE: LedgerClassifyJobLaneProjection = {
  provider_id: "llamacpp",
  transport: "local",
  model: "fixture-small",
  effort: null,
  reads_off_host: false,
};
const OFF_HOST_LANE: LedgerClassifyJobLaneProjection = {
  provider_id: "fixture-cloud",
  transport: "api",
  model: "fixture-large",
  effort: null,
  reads_off_host: true,
};

/** The fourth quarter's active movements, in the grid's order: the rows the
 * Ledger shows first. */
function quarterMovements(): string[] {
  const from = `${fixtureYear}-10-01`;
  return fixtureLedger()
    .movements.filter(
      (movement) =>
        movement.transaction.date >= from &&
        movement.transaction.date <= LEDGER_FIXTURE_TODAY &&
        movement.transaction.lifecycle_state === "ACTIVE",
    )
    .sort(
      (left, right) =>
        left.transaction.date.localeCompare(right.transaction.date) ||
        left.transaction.transaction_id.localeCompare(
          right.transaction.transaction_id,
        ),
    )
    .map((movement) => movement.transaction.transaction_id);
}

type Seed = {
  status: ClassificationJobStatus;
  lane: LedgerClassifyJobLaneProjection;
  hour: string;
  items: (
    Exclude<ClassificationItemState, "failed"> | ClassificationItemFailureCause
  )[];
};

const SEEDS: Record<JobShape, Seed> = {
  // Running: two proposed, one being asked, two to ask, one failed.
  progress: {
    status: "running",
    lane: LOCAL_LANE,
    hour: "10",
    items: [
      "proposed",
      "proposed",
      "running",
      "pending",
      "pending",
      "model_unavailable",
    ],
  },
  // Settled on an off-host lane with no consent to read.
  consent: {
    status: "settled",
    lane: OFF_HOST_LANE,
    hour: "09",
    items: ["consent_required", "consent_required"],
  },
  // Left running by a run that stopped, with movements still to ask.
  resume: {
    status: "running",
    lane: LOCAL_LANE,
    hour: "08",
    items: ["proposed", "pending", "pending"],
  },
  // Settled, every movement proposed.
  settled: {
    status: "settled",
    lane: LOCAL_LANE,
    hour: "07",
    items: ["proposed", "proposed"],
  },
};

const FAILURES: ReadonlySet<string> = new Set<ClassificationItemFailureCause>([
  "model_unavailable",
  "consent_required",
  "consent_revoked",
  "consent_expired",
  "lane_changed",
  "lane_refused",
  "invalid_response",
  "timed_out",
  "movement_not_found",
]);

const CONSENT_FAILURES: ReadonlySet<string> = new Set([
  "consent_required",
  "consent_revoked",
  "consent_expired",
  "lane_changed",
]);

const at = (hour: string, minute = 0) =>
  `${LEDGER_FIXTURE_TODAY}T${hour}:${String(minute).padStart(2, "0")}:00Z`;

function proposal(movement: string, minute: number) {
  return {
    movement_revision_id: hex64(`revision:${movement}`),
    classification: "BUSINESS" as const,
    confidence: "0.9",
    category: "gastos_bancarios",
    iva_category: "domestic_general",
    business_pct: null,
    multiple_components: null,
    proposed_at: at("11", minute % 60),
  };
}

function counts(items: readonly LedgerClassifyJobItemProjection[]) {
  const tally = {
    pending: 0,
    running: 0,
    proposed: 0,
    failed: 0,
    unknown: 0,
    cancelled: 0,
    stale: 0,
    applied: 0,
  };
  for (const item of items) tally[item.state] += 1;
  return tally;
}

/** A refusal settled by the operation, with the words the backend served. */
function refused(
  operation: string,
  reason: string,
  words: string,
): LedgerOutcome {
  const detail: LedgerErrorDetail = {
    detail_version: 1,
    kind: "operation_refused",
    error_code: reason,
    message_key: null,
    context: [],
    context_entries_omitted: 0,
    precondition_verdict_json: null,
    refusal_words: words,
    refusal_words_language: "en",
  };
  return {
    kind: "refused",
    operation_id: operation,
    revision: 3,
    reason,
    detail,
  };
}

type Controls = NonNullable<Window["__scenarioBackgroundTasks"]>;
/** Every job store the page made. */
const instances = new Set<Controls>();

export type BackgroundTasksFixture = {
  port: BackgroundTasksPort;
  /** Answers one job definition the ledger port was asked, or null where
   * the fixture has no job behaviour for it. */
  submit(
    definition: string,
    request: JsonObject,
    operation: string,
  ): LedgerOutcome | null;
};

export function backgroundTasksFixture(options: {
  say: (call: string) => void;
  signedIn: () => boolean;
  shapes: readonly JobShape[];
}): BackgroundTasksFixture {
  const { say } = options;
  const ids = quarterMovements();
  const jobs = new Map<string, LedgerClassifyJobProjection>();
  let offset = 0;
  for (const shape of JOB_SHAPES) {
    const seed = SEEDS[shape];
    const movements = ids.slice(offset, offset + seed.items.length);
    offset += seed.items.length;
    if (!options.shapes.includes(shape)) continue;
    const items = seed.items.map(
      (state, index): LedgerClassifyJobItemProjection => {
        const movement = movements[index]!;
        const failed = FAILURES.has(state);
        return {
          movement_id: movement,
          state: failed ? "failed" : (state as ClassificationItemState),
          attempt: state === "pending" ? 0 : 1,
          failure_cause: failed
            ? (state as ClassificationItemFailureCause)
            : null,
          proposal: state === "proposed" ? proposal(movement, index) : null,
        };
      },
    );
    const job: LedgerClassifyJobProjection = {
      job_id: hex64(`job:${shape}`),
      scope: "selection",
      period_start: null,
      period_end: null,
      lane: seed.lane,
      consent_scope: null,
      status: seed.status,
      revision: 3,
      created_at: at(seed.hour),
      updated_at: at(seed.hour, 5),
      counts: counts(items),
      items,
    };
    jobs.set(job.job_id, job);
  }
  const listeners = new Set<(cue: BackgroundTaskCue) => void>();
  const runs: string[] = [];
  const enqueued: string[] = [];
  // Applies a scenario asked to be refused, by movement.
  const applyRefusals = new Map<string, LedgerClassifyJobApplyRefusal>();
  // The job whose run holds the profile: runs do not overlap.
  let running: string | null = null;
  let clock = 0;

  const emit = (cue: BackgroundTaskCue) => {
    say(`background cue ${cue.revision}`);
    listeners.forEach((listener) => listener(cue));
  };
  const cueOf = (job: LedgerClassifyJobProjection): BackgroundTaskCue => ({
    family: "ledger_classification",
    profile_id: LEDGER_FIXTURE_PROFILE_ID,
    job_id: job.job_id,
    revision: job.revision,
  });
  /** Stores a change to `job`: its counts, a higher revision, and a cue. */
  const store = (
    job: LedgerClassifyJobProjection,
    change: Partial<LedgerClassifyJobProjection>,
    cue = true,
  ) => {
    clock += 1;
    const items = change.items ?? job.items;
    const next: LedgerClassifyJobProjection = {
      ...job,
      ...change,
      items,
      counts: counts(items),
      revision: job.revision + 1,
      updated_at: at("12", clock % 60),
    };
    jobs.set(job.job_id, next);
    if (running === job.job_id && next.status !== "running") running = null;
    if (cue) emit(cueOf(next));
    return next;
  };
  const found = (id: string) => {
    const job = jobs.get(id);
    if (!job) throw new Error(`no fixture job ${id}`);
    return job;
  };
  const step = (
    id: string,
    {
      cause,
      silently = false,
    }: {
      cause?: ClassificationItemFailureCause;
      silently?: boolean;
    } = {},
  ) => {
    const job = found(id);
    const flying = job.items.findIndex((item) => item.state === "running");
    const index =
      flying >= 0
        ? flying
        : job.items.findIndex((item) => item.state === "pending");
    if (index < 0) return;
    const items = job.items.map((item, position) =>
      position !== index
        ? item
        : cause
          ? {
              ...item,
              state: "failed" as const,
              attempt: item.attempt + 1,
              failure_cause: cause,
            }
          : {
              ...item,
              state: "proposed" as const,
              attempt: item.attempt + 1,
              proposal: proposal(item.movement_id, position),
            },
    );
    const left = items.some(
      (item) => item.state === "pending" || item.state === "running",
    );
    store(job, { items, status: left ? job.status : "settled" }, !silently);
  };

  const controls: Controls = {
    job: (shape) => hex64(`job:${shape}`),
    movements: (id) => found(id).items.map((item) => item.movement_id),
    step,
    finish(id) {
      const job = found(id);
      const items = job.items.map((item, position) =>
        item.state === "pending" || item.state === "running"
          ? {
              ...item,
              state: "proposed" as const,
              attempt: item.attempt + 1,
              proposal: proposal(item.movement_id, position),
            }
          : item,
      );
      store(job, { items, status: "settled" });
    },
    apply(id) {
      const job = found(id);
      store(job, {
        items: job.items.map((item) =>
          item.state === "proposed"
            ? { ...item, state: "applied" as const }
            : item,
        ),
      });
    },
    cue(id, revision) {
      const job = found(id);
      emit({ ...cueOf(job), revision: revision ?? job.revision });
    },
    cueOtherProfile(id) {
      const job = found(id);
      emit({
        ...cueOf(job),
        profile_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        revision: job.revision + 10,
      });
    },
    enqueued: () => [...enqueued],
    refuseApply(movement, cause) {
      applyRefusals.set(movement, cause);
    },
    observers: () => listeners.size,
    runs: () => [...runs],
  };
  // The page may make its host more than once: the controls move the jobs
  // of every instance, and the window's is the one it subscribed to.
  instances.add(controls);
  window.__scenarioBackgroundTasks = {
    job: controls.job,
    movements: (id) => controls.movements(id),
    step: (id, options) => instances.forEach((each) => each.step(id, options)),
    finish: (id) => instances.forEach((each) => each.finish(id)),
    apply: (id) => instances.forEach((each) => each.apply(id)),
    cue: (id, revision) => instances.forEach((each) => each.cue(id, revision)),
    cueOtherProfile: (id) =>
      instances.forEach((each) => each.cueOtherProfile(id)),
    enqueued: () => [...instances].flatMap((each) => each.enqueued()),
    refuseApply: (movement, cause) =>
      instances.forEach((each) => each.refuseApply(movement, cause)),
    observers: () =>
      [...instances].reduce((sum, each) => sum + each.observers(), 0),
    runs: () => [...instances].flatMap((each) => each.runs()),
  };

  const port: BackgroundTasksPort = {
    observe(listener) {
      say("background observe");
      listeners.add(listener);
      return Promise.resolve(() => {
        say("background unobserve");
        listeners.delete(listener);
      });
    },
    revisions() {
      say("background revisions");
      if (!options.signedIn()) return reject("not_signed_in");
      return Promise.resolve({
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        tasks: [...jobs.values()].map((job) => ({
          family: "ledger_classification" as const,
          job_id: job.job_id,
          revision: job.revision,
        })),
      });
    },
  };

  /** Answers one change the person asked for at the revision they saw. */
  const change = (
    operation: string,
    request: JsonObject,
    apply: (job: LedgerClassifyJobProjection) =>
      | { refusal: [string, string] }
      | {
          change: Partial<LedgerClassifyJobProjection>;
          outcome: string;
        },
  ): LedgerOutcome => {
    const job = jobs.get(String(request.job_id));
    if (!job)
      return refused(operation, "job_not_found", "This job is not stored.");
    if (request.expected_revision !== job.revision)
      return refused(
        operation,
        "revision_conflict",
        "The job changed since you read it; it is read again.",
      );
    const answer = apply(job);
    if ("refusal" in answer) return refused(operation, ...answer.refusal);
    const next = store(job, answer.change);
    return {
      kind: "settled",
      operation_id: operation,
      revision: 3,
      result: {
        profile_id: LEDGER_FIXTURE_PROFILE_ID,
        outcome: answer.outcome,
        job: next,
      } as unknown as JsonObject,
    };
  };
  const settled = (operation: string, result: object): LedgerOutcome => ({
    kind: "settled",
    operation_id: operation,
    revision: 3,
    result: result as JsonObject,
  });

  return {
    port,
    submit(definition, request, operation) {
      if (definition === "ledger.classify.job.list") {
        const listed = [...jobs.values()]
          .filter(
            (job) =>
              request.include_dismissed === true || job.status !== "dismissed",
          )
          .sort((left, right) =>
            right.created_at.localeCompare(left.created_at),
          );
        return settled(operation, {
          profile_id: LEDGER_FIXTURE_PROFILE_ID,
          queue_revision: hex64(
            listed.map((job) => `${job.job_id}:${job.revision}`).join(","),
          ),
          jobs: listed,
          more: false,
        });
      }
      if (definition === "ledger.classify.job.read") {
        const job = jobs.get(String(request.job_id));
        return job
          ? settled(operation, { profile_id: LEDGER_FIXTURE_PROFILE_ID, job })
          : refused(operation, "job_not_found", "This job is not stored.");
      }
      if (definition === "ledger.classify.job.enqueue") {
        const movements = Array.isArray(request.movement_ids)
          ? request.movement_ids.map(String)
          : [];
        if (movements.length === 0)
          return refused(
            operation,
            "nothing_to_classify",
            "No movement was named to classify; select one and ask again.",
          );
        clock += 1;
        const items = movements.map(
          (movement): LedgerClassifyJobItemProjection => ({
            movement_id: movement,
            state: "pending",
            attempt: 0,
            failure_cause: null,
            proposal: null,
          }),
        );
        const job: LedgerClassifyJobProjection = {
          job_id: hex64(`job:enqueued:${enqueued.length}`),
          scope: request.scope === "single" ? "single" : "selection",
          period_start: null,
          period_end: null,
          lane: LOCAL_LANE,
          consent_scope: null,
          status: "queued",
          revision: 1,
          created_at: at("13", enqueued.length % 60),
          updated_at: at("13", enqueued.length % 60),
          counts: counts(items),
          items,
        };
        enqueued.push(job.job_id);
        jobs.set(job.job_id, job);
        emit(cueOf(job));
        return settled(operation, {
          profile_id: LEDGER_FIXTURE_PROFILE_ID,
          outcome: "enqueued",
          job,
        });
      }
      if (definition === "ledger.classify.job.apply") {
        const job = jobs.get(String(request.job_id));
        if (!job)
          return refused(operation, "job_not_found", "This job is not stored.");
        if (request.expected_revision !== job.revision)
          return refused(
            operation,
            "revision_conflict",
            "The job changed since you read it; it is read again.",
          );
        const accepted = Array.isArray(request.accepted)
          ? (request.accepted as JsonObject[])
          : [];
        const results = accepted.map(
          (entry): LedgerClassifyJobApplyItemResult => {
            const movement = String(entry.movement_id);
            const item = job.items.find(
              (found) => found.movement_id === movement,
            );
            const asked = applyRefusals.get(movement);
            applyRefusals.delete(movement);
            const refusal: LedgerClassifyJobApplyRefusal | null = !item
              ? "not_in_job"
              : item.state !== "proposed" || !item.proposal
                ? "not_proposed"
                : item.proposal.movement_revision_id !==
                    entry.movement_revision_id
                  ? "stale"
                  : (asked ?? null);
            return {
              movement_id: movement,
              outcome: refusal === null ? "applied" : "refused",
              refusal,
            };
          },
        );
        const applied = new Set(
          results
            .filter((result) => result.outcome === "applied")
            .map((result) => result.movement_id),
        );
        const next =
          applied.size === 0
            ? job
            : store(job, {
                items: job.items.map((item) =>
                  applied.has(item.movement_id)
                    ? { ...item, state: "applied" as const }
                    : item,
                ),
              });
        return settled(operation, {
          profile_id: LEDGER_FIXTURE_PROFILE_ID,
          job: next,
          items: results,
        });
      }
      if (definition === "ledger.classify.job.run") {
        const job = jobs.get(String(request.job_id));
        if (!job)
          return refused(operation, "job_not_found", "This job is not stored.");
        runs.push(job.job_id);
        if (running !== null && running !== job.job_id)
          return reject("refused", { reason: "subject_busy" });
        if (!job.items.some((item) => item.state === "pending"))
          return settled(operation, {
            profile_id: LEDGER_FIXTURE_PROFILE_ID,
            outcome: "settled",
            job,
          });
        running = job.job_id;
        store(job, { status: "running" });
        return {
          kind: "running",
          operation_id: operation,
          revision: 2,
          cancellable: true,
        };
      }
      if (definition === "ledger.classify.job.cancel")
        return change(operation, request, (job) => {
          const flying = job.items.some((item) => item.state === "running");
          return {
            change: {
              status: flying ? "cancelling" : "cancelled",
              items: job.items.map((item) =>
                item.state === "pending"
                  ? { ...item, state: "cancelled" as const }
                  : item,
              ),
            },
            outcome: flying ? "cancelling" : "cancelled",
          };
        });
      if (definition === "ledger.classify.job.retry")
        return change(operation, request, (job) => ({
          change: {
            status: "queued",
            items: job.items.map((item) =>
              item.state === "failed" || item.state === "unknown"
                ? { ...item, state: "pending" as const, failure_cause: null }
                : item,
            ),
          },
          outcome: "retried",
        }));
      if (definition === "ledger.classify.job.dismiss")
        return change(operation, request, (job) =>
          job.status === "running" || job.status === "queued"
            ? {
                refusal: [
                  "job_active",
                  "A job is dismissed once its run has ended.",
                ],
              }
            : { change: { status: "dismissed" }, outcome: "dismissed" },
        );
      if (definition === "ledger.classify.job.authorise")
        return change(operation, request, (job) => {
          const consent = request.consent as JsonObject | null;
          if (
            !consent ||
            consent.provider_id !== job.lane.provider_id ||
            consent.model !== job.lane.model ||
            consent.connection !== job.lane.transport
          )
            return {
              refusal: [
                "lane_changed",
                "The agent now reads with another model; ask again.",
              ],
            };
          return {
            change: {
              status: "queued",
              consent_scope:
                consent.scope as LedgerClassifyJobProjection["consent_scope"],
              items: job.items.map((item) =>
                item.state === "failed" &&
                CONSENT_FAILURES.has(item.failure_cause ?? "")
                  ? { ...item, state: "pending" as const, failure_cause: null }
                  : item,
              ),
            },
            outcome: "authorised",
          };
        });
      return null;
    },
  };
}
