import type {
  OperationHistoryCursorV1,
  OperationHistoryRowV1,
  OperationsServed,
} from "../../shell/operationsContract";

// What the operation history serves, in the shape the product serves it, for
// the scenario host and the stories. SYNTHETIC: the operation ids, the
// references and the error code are invented placeholders, and the window
// draws exactly what is served. The first runs stand for each state the page
// must keep apart; the rest only fill a second page.

const PROFILE = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";

/** How many runs the synthetic history holds. */
export const OPERATIONS_FIXTURE_RUNS = 30;

/** Where the history begins; each older run started a minute earlier. */
const NEWEST = 1795089600000;

const instant = (milliseconds: number): string =>
  new Date(milliseconds).toISOString().replace(".000Z", "Z");

const at = (index: number, seconds = 0): string =>
  instant(NEWEST - index * 60_000 + seconds * 1000);

const identity = (index: number) =>
  `synthetic-run-${String(index).padStart(2, "0")}`;

const run = (
  index: number,
  change: Partial<OperationHistoryRowV1>,
): OperationHistoryRowV1 => ({
  operation_id: identity(index),
  definition_id: "app.review.queue",
  register_page: null,
  started_at: at(index),
  updated_at: at(index, 20),
  lifecycle: "terminal",
  effect: "none",
  phase_code: null,
  cancellation_requested: false,
  receipt: {
    condition: "succeeded",
    effect: "none",
    settled_at: at(index, 20),
    result_stored: true,
    refusal_ref: null,
    failure_error_code: null,
  },
  ...change,
});

const settled = (
  index: number,
  condition: NonNullable<OperationHistoryRowV1["receipt"]>["condition"],
  effect: OperationHistoryRowV1["effect"],
  receipt: Partial<NonNullable<OperationHistoryRowV1["receipt"]>> = {},
  change: Partial<OperationHistoryRowV1> = {},
): OperationHistoryRowV1 =>
  run(index, {
    effect,
    receipt: {
      condition,
      effect,
      settled_at: at(index, 20),
      result_stored: true,
      refusal_ref: null,
      failure_error_code: null,
      ...receipt,
    },
    ...change,
  });

/** The synthetic history, newest first. */
export function operationsHistory(): OperationHistoryRowV1[] {
  const named: OperationHistoryRowV1[] = [
    run(0, {
      definition_id: "ledger.add",
      register_page: "ledger",
      lifecycle: "settling",
      effect: "unknown",
      phase_code: "ledger.add",
      receipt: null,
    }),
    run(1, {
      definition_id: "overview.status",
      register_page: "home",
      lifecycle: "running",
      phase_code: "overview.status",
      receipt: null,
    }),
    settled(
      2,
      "succeeded",
      "updated",
      {},
      {
        definition_id: "ledger.classify.bulk",
        register_page: "ledger",
      },
    ),
    settled(
      3,
      "failed",
      "partial",
      { failure_error_code: "SYNTHETIC_FAILURE", result_stored: false },
      { definition_id: "modelo.export", register_page: "declarations" },
    ),
    settled(
      4,
      "refused",
      "none",
      { refusal_ref: "synthetic-refusal-ref", result_stored: false },
      { definition_id: "user-profile.patch", register_page: "profile" },
    ),
    settled(
      5,
      "timed_out",
      "unknown",
      { result_stored: false },
      {
        definition_id: "live.notifications.capture",
        register_page: "aeat-sync",
      },
    ),
    run(6, {
      definition_id: "reference.corpus.search",
      register_page: "reference",
      lifecycle: "cancellation_requested",
      cancellation_requested: true,
      receipt: null,
    }),
    settled(7, "succeeded", "none", {}, { definition_id: "workflow.run.read" }),
    settled(
      8,
      "succeeded",
      "none",
      {},
      {
        definition_id: "synthetic.installation.status",
        register_page: "installation",
      },
    ),
  ];
  const filler = Array.from(
    { length: OPERATIONS_FIXTURE_RUNS - named.length },
    (_, offset) => run(named.length + offset, {}),
  );
  return [...named, ...filler];
}

const cursorOf = (row: OperationHistoryRowV1): OperationHistoryCursorV1 => ({
  started_at: row.started_at,
  operation_id: row.operation_id,
});

/** What the scenario host answers: the page of at most `limit` runs after
 * `after`, the way the product pages its history, or an empty history. */
export function operationsFixture(
  limit: number,
  after: OperationHistoryCursorV1 | null,
  options: {
    empty?: boolean;
    damaged?: boolean;
    unrecognised?: boolean;
  } = {},
): OperationsServed {
  const all = options.empty ? [] : operationsHistory();
  const later =
    after === null
      ? all
      : all.filter(
          (row) =>
            row.started_at < after.started_at ||
            (row.started_at === after.started_at &&
              row.operation_id < after.operation_id),
        );
  const runs = later
    .slice(0, limit)
    .map((row, index) =>
      options.unrecognised && index === 0 && after === null
        ? ({ ...row, lifecycle: "synthetic_new" } as unknown as typeof row)
        : row,
    );
  const last = later[limit - 1];
  return {
    result_version: 1,
    profile_id: PROFILE,
    observed_at: instant(NEWEST + 5 * 60_000),
    runs,
    run_count: all.length,
    next_cursor: later.length > limit && last ? cursorOf(last) : null,
    unreadable_records: options.damaged ? 2 : 0,
    unverifiable_records: options.damaged ? 1 : 0,
  };
}
