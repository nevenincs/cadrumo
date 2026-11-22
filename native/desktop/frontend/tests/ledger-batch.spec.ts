import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  BATCH_PLAN_CHANGED,
  BATCH_ROW_LIMIT,
} from "../src/shell/ledgerMovementContract";
import {
  batchRowOutcome,
  runPlan,
  type BatchRowResult,
} from "../src/shell/ledgerApply";
import {
  batchCounts,
  copiedProperties,
  pasteCells,
  pasteChanges,
  pasteRequests,
  undoCells,
  undoable,
  unwrittenRows,
} from "../src/shell/ledgerBatch";
import {
  batchRequest,
  batchRequestRow,
  batchRequests,
  payloadSize,
  splitBatch,
  withReviewedDigests,
  type PlanStep,
} from "../src/shell/ledgerPlan";
import type { StagedContent, StagedRowChanges } from "../src/shell/ledgerStage";
import type { LedgerErrorDetail } from "../src/shell/ledger";
import { fakePort, hexId, movement, PROFILE } from "./support/ledger";
import { planRecorded } from "./support/stagedCheck";
import { fixtureInstant } from "../src/dev/fixtureDates";
import type {
  LedgerBatchUpdateResult,
  LedgerPropertySet,
} from "../src/shell/ledgerMovementContract";
import type { LedgerTransactionReviewProjection } from "../src/shell/ledgerReadContract";

// How property edits become batch edits, how a batch's answer settles row by
// row, and how copied properties and an undo are staged. No page is opened.

const set = (value: string) => ({ kind: "set" as const, value });
const clear = { kind: "clear" as const };
const business = (id: string, extra = {}) =>
  movement(id, {
    business_classification: "BUSINESS",
    category_id: "material_oficina",
    ...extra,
  });
const mixed = (id: string) =>
  movement(id, {
    business_classification: "MIXED",
    business_pct: "0.60",
    category_id: "telefono",
  });
const rowsOf = (...rows: LedgerTransactionReviewProjection[]) =>
  new Map(rows.map((row) => [row.transaction.transaction_id, row]));
const staged = (rows: Record<string, StagedRowChanges>): StagedContent => ({
  rows,
  actions: [],
  drafts: [],
});
const DIGEST = "d".repeat(64);
const FRESH = "e".repeat(64);
const STAMP = fixtureInstant(10, 5, "09:00:00Z");

const A = hexId("a");
const M = hexId("m");
const U = hexId("u");
const NEW_A = hexId("a-new");

/** A property set as the contract holds it: every property present, null
 * where the set does not name it. */
const NONE = {
  business_classification: null,
  business_pct: null,
  category_id: null,
  usage_ratio_id: null,
  iva_category: null,
  iva_rate: null,
  irpf_category: null,
  deduction_fact_kind: null,
  exemption_article: null,
  counterparty: null,
  notes: null,
  group_label: null,
};
const props = (
  fields: LedgerPropertySet["fields"],
  values: Partial<Omit<LedgerPropertySet, "fields">> = {},
): LedgerPropertySet => ({ ...NONE, fields, ...values });

/** One row of a batch answer, shaped as the contract holds it. */
const applied = (
  id: string,
  changed: BatchRowResult["changed_fields"],
  previous: BatchRowResult["previous"],
  resultId = id,
): BatchRowResult => ({
  transaction_id: id,
  outcome: "applied",
  cause: null,
  messages: [],
  changed_fields: changed,
  previous,
  result_transaction_id: resultId,
  modified_at: STAMP,
});
const notWritten = (
  id: string,
  outcome: "refused" | "conflict",
  cause: NonNullable<BatchRowResult["cause"]>,
  messages: string[] = [],
): BatchRowResult => ({
  transaction_id: id,
  outcome,
  cause,
  messages,
  changed_fields: [],
  previous: null,
  result_transaction_id: null,
  modified_at: null,
});
const answerOf = (
  outcome: LedgerBatchUpdateResult["outcome"],
  rows: BatchRowResult[],
  digest = DIGEST,
): LedgerBatchUpdateResult => {
  const answer: LedgerBatchUpdateResult = {
    profile_id: PROFILE,
    outcome,
    plan_digest: digest,
    rows,
    counts: { applied: 0, unchanged: 0, refused: 0, conflict: 0 },
    bucket_event_ids: outcome === "applied" ? ["ev"] : [],
  };
  return { ...answer, counts: batchCounts([answer]) };
};

test("a movement whose staged fields are all properties is saved by one batch edit, with the stamp the page read", () => {
  const plan = planRecorded(
    staged({
      [A]: { category_id: set("telefono") },
      [M]: { iva_rate: set("0.21"), taxable_base: set("30.00") },
      [U]: {
        business_classification: set("MIXED"),
        business_pct: set("0.5"),
        category_id: set("suministros"),
      },
    }),
    { rows: rowsOf(business(A), mixed(M), movement(U)) },
  );
  // The base is no property a batch edit writes: that movement keeps the
  // bulk classification, whole.
  expect(plan.steps.map((step) => step.kind)).toEqual(["batch", "bulk"]);
  const batch = plan.steps[0] as Extract<PlanStep, { kind: "batch" }>;
  expect(batch.rows.map((row) => row.transactionId)).toEqual([A, U]);
  expect(batch.reviewedPlanDigest).toBeNull();
  expect(batch.request.rows).toEqual([
    {
      transaction_id: A,
      expected_modified_at: business(A).transaction.modified_at,
      properties: props(["category_id"], { category_id: "telefono" }),
    },
    {
      transaction_id: U,
      expected_modified_at: movement(U).transaction.modified_at,
      properties: props(
        ["business_classification", "business_pct", "category_id"],
        {
          business_classification: "MIXED",
          business_pct: "0.5",
          category_id: "suministros",
        },
      ),
    },
  ]);
  const bulk = plan.steps[1] as Extract<PlanStep, { kind: "bulk" }>;
  expect(bulk.rows.map((row) => row.transactionId)).toEqual([M]);
  expect(plan.summary.together).toBe(3);
  expect(plan.summary.parts).toBe(2);
  expect(batchRequests(plan)).toEqual([batch.request]);
});

test("batch parts fit the payload bound with the digest the write adds, and the row bound", () => {
  const rows = Array.from({ length: 40 }, (_, at) => ({
    request: batchRequestRow(hexId(`r${at}`), STAMP, {
      notes: "n".repeat(200),
    }),
  }));
  const limit = 4000;
  const { parts, tooLarge } = splitBatch(rows, limit);
  expect(tooLarge).toEqual([]);
  expect(parts.length).toBeGreaterThan(1);
  expect(parts.flat()).toEqual(rows);
  for (const part of parts) {
    const write = {
      ...batchRequest(part.map((row) => row.request)),
      reviewed_plan_digest: DIGEST,
    };
    expect(payloadSize(write)).toBeLessThanOrEqual(limit);
    // Each part is the longest that fits: one more row would not.
    const next = rows[rows.indexOf(part.at(-1)!) + 1];
    if (next)
      expect(
        payloadSize({
          ...batchRequest([...part, next].map((row) => row.request)),
          reviewed_plan_digest: DIGEST,
        }),
      ).toBeGreaterThan(limit);
  }
  const huge = {
    request: batchRequestRow(hexId("huge"), STAMP, {
      notes: "n".repeat(limit),
    }),
  };
  expect(splitBatch([huge, rows[0]!], limit)).toEqual({
    parts: [[rows[0]]],
    tooLarge: [huge],
  });
  const many = Array.from({ length: BATCH_ROW_LIMIT + 1 }, (_, at) => ({
    request: batchRequestRow(String(at), STAMP, { notes: null }),
  }));
  expect(
    splitBatch(many, Number.MAX_SAFE_INTEGER).parts.map((part) => part.length),
  ).toEqual([BATCH_ROW_LIMIT, 1]);
});

test("a batch part is written only with the digest its preview answered", async () => {
  const plan = planRecorded(staged({ [A]: { category_id: set("telefono") } }), {
    rows: rowsOf(business(A)),
  });
  const unreviewed = fakePort(() => {
    throw new Error("nothing is sent unreviewed");
  });
  const held = await runPlan(unreviewed.port, plan);
  expect(unreviewed.calls).toEqual([]);
  expect(held.steps[0]!.outcome).toEqual({
    kind: "not_sent",
    why: "unreviewed",
  });

  const reviewed = withReviewedDigests(plan, [DIGEST]);
  const { port, calls } = fakePort(() => ({
    settle: answerOf("applied", [
      applied(
        A,
        ["category_id"],
        props(["category_id"], { category_id: "material_oficina" }),
        NEW_A,
      ),
    ]),
  }));
  const report = await runPlan(port, reviewed);
  expect(calls).toHaveLength(1);
  expect(calls[0]).toMatchObject({
    kind: "submit",
    definition: "ledger.update.batch",
    payload: { reviewed_plan_digest: DIGEST },
  });
  expect(report.steps[0]!.rows).toEqual([
    { transactionId: A, outcome: { kind: "applied", newId: NEW_A } },
  ]);
  expect(report.steps[0]!.batch?.outcome).toBe("applied");
});

test("each batch row settles as the ledger said: written, already so, refused with its sentences, or changed since seen", () => {
  expect(batchRowOutcome(A, applied(A, ["notes"], props(["notes"])))).toEqual({
    kind: "applied",
    newId: null,
  });
  expect(
    batchRowOutcome(A, {
      ...applied(A, [], props(["notes"], { notes: "x" })),
      outcome: "unchanged",
    }),
  ).toEqual({ kind: "unchanged" });
  expect(
    batchRowOutcome(
      A,
      notWritten(A, "refused", "sealed", ["A filed declaration cites it."]),
    ),
  ).toEqual({
    kind: "refused",
    reason: "sealed",
    messages: ["A filed declaration cites it."],
    detail: null,
  });
  const stale = batchRowOutcome(
    A,
    notWritten(A, "conflict", "changed_since_seen"),
  );
  expect(stale).toMatchObject({
    kind: "refused",
    reason: "changed_since_seen",
  });
  expect(
    batchRowOutcome(A, notWritten(A, "refused", "invalid", ["No."])),
  ).toMatchObject({ kind: "refused", reason: "invalid" });
  // A row the answer does not name was not written.
  expect(batchRowOutcome(A, undefined)).toMatchObject({ kind: "refused" });
});

test("a partly written batch reports every row, and only its written rows leave the changes", async () => {
  const plan = withReviewedDigests(
    planRecorded(
      staged({
        [A]: { category_id: set("telefono") },
        [U]: {
          business_classification: set("MIXED"),
          business_pct: set("0.5"),
          category_id: set("suministros"),
        },
      }),
      { rows: rowsOf(business(A), movement(U)) },
    ),
    [DIGEST],
  );
  const { port } = fakePort(() => ({
    settle: answerOf("applied", [
      applied(
        A,
        ["category_id"],
        props(["category_id"], { category_id: "material_oficina" }),
      ),
      notWritten(U, "refused", "invalid", ["The share is not accepted."]),
    ]),
  }));
  const report = await runPlan(port, plan);
  const step = report.steps[0]!;
  expect(step.outcome.kind).toBe("applied");
  expect(step.rows.map((row) => [row.transactionId, row.outcome.kind])).toEqual(
    [
      [A, "applied"],
      [U, "refused"],
    ],
  );
  expect(report.reread).toContain(A);
});

test("a batch that met another plan than the reviewed one writes nothing and asks for a new review", async () => {
  const plan = withReviewedDigests(
    planRecorded(staged({ [A]: { category_id: set("telefono") } }), {
      rows: rowsOf(business(A)),
    }),
    [DIGEST],
  );
  const fresh = answerOf(
    "plan_changed",
    [notWritten(A, "refused", "sealed", ["A filed declaration cites it."])],
    FRESH,
  );
  const { port } = fakePort(() => ({
    outcome: {
      kind: "refused",
      operation_id: "op",
      revision: 3,
      reason: BATCH_PLAN_CHANGED,
      detail: fresh as unknown as LedgerErrorDetail,
    },
  }));
  const report = await runPlan(port, plan);
  const row = report.steps[0]!.rows[0]!;
  expect(row.outcome).toEqual({
    kind: "refused",
    reason: BATCH_PLAN_CHANGED,
    messages: ["A filed declaration cites it."],
    detail: null,
  });
  expect(report.steps[0]!.batch?.plan_digest).toBe(FRESH);
  expect(report.reread).not.toContain(A);
});

test("copied properties are one typed set in contract order, an empty value carried as a clear", () => {
  const row = business(A, { counterparty: "", iva_category: "general" });
  expect(
    copiedProperties(row, ["counterparty", "category_id", "iva_category"]),
  ).toEqual(
    props(["category_id", "iva_category", "counterparty"], {
      category_id: "material_oficina",
      iva_category: "general",
    }),
  );
});

test("a paste asks about each selected movement with its own stamp and stages only what the ledger would change", () => {
  const set_ = copiedProperties(business(A, { notes: "Revisado" }), [
    "category_id",
    "notes",
  ]);
  const rows = rowsOf(movement(M), business(U));
  const asked = pasteRequests(set_, [M, U, hexId("absent")], rows);
  expect(asked.unread).toBe(1);
  expect(asked.requests).toEqual([
    {
      rows: [
        {
          transaction_id: M,
          expected_modified_at: movement(M).transaction.modified_at,
          properties: set_,
        },
        {
          transaction_id: U,
          expected_modified_at: business(U).transaction.modified_at,
          properties: set_,
        },
      ],
    },
  ]);
  const previewed = [
    answerOf("previewed", [
      applied(M, ["category_id", "notes"], props(["category_id", "notes"])),
      applied(
        U,
        ["notes"],
        props(["category_id", "notes"], { category_id: "material_oficina" }),
      ),
    ]),
  ];
  expect(pasteChanges(set_, previewed)).toEqual([
    { field: "category_id", value: "material_oficina", rows: 1 },
    { field: "notes", value: "Revisado", rows: 2 },
  ]);
  expect(pasteCells(set_, previewed, rows)).toEqual([
    {
      id: M,
      field: "category_id",
      value: set("material_oficina"),
      stored: null,
    },
    { id: M, field: "notes", value: set("Revisado"), stored: null },
    { id: U, field: "notes", value: set("Revisado"), stored: null },
  ]);
  // A row the ledger would refuse or find changed stages nothing.
  const refusing = [
    answerOf("previewed", [
      notWritten(M, "refused", "sealed", ["Sealed."]),
      notWritten(U, "conflict", "changed_since_seen"),
    ]),
  ];
  expect(pasteCells(set_, refusing, rows)).toEqual([]);
  expect(unwrittenRows(refusing).map((row) => row.cause)).toEqual([
    "sealed",
    "changed_since_seen",
  ]);
});

test("an undo writes each written row's earlier values back on the movement as it now is", () => {
  const reports = [
    {
      index: 0,
      step: {
        kind: "batch",
        part: 1,
        parts: 1,
        rows: [{ transactionId: A, fields: ["category_id"] }],
        request: { rows: [] },
        reviewedPlanDigest: DIGEST,
      },
      outcome: { kind: "applied", newId: null },
      rows: [],
      batch: answerOf("applied", [
        applied(A, ["category_id"], props(["category_id"]), NEW_A),
        applied(U, ["notes"], props(["notes"], { notes: "Antes" })),
        notWritten(M, "refused", "sealed", ["Sealed."]),
      ]),
    },
  ] satisfies Parameters<typeof undoCells>[0];
  expect(undoable(reports)).toBe(true);
  const now = rowsOf(
    business(NEW_A, { category_id: "telefono", modified_at: STAMP }),
  );
  expect(undoCells(reports, now)).toEqual({
    cells: [
      { id: NEW_A, field: "category_id", value: clear, stored: "telefono" },
    ],
    unread: 1,
  });
  expect(undoable([{ ...reports[0]!, batch: undefined }])).toBe(false);
});
