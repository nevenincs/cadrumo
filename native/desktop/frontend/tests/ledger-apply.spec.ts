import { expect, test } from "@playwright/test";
import type { JsonObject, LedgerRow } from "../src/shell/ledger";
import {
  changedSinceRead,
  keepAfterApply,
  prepareApply,
  resolveUnknown,
  runPlan,
  stageAfterApply,
  type ApplyReport,
} from "../src/shell/ledgerApply";
import { planApply, type LedgerPlan } from "../src/shell/ledgerPlan";
import {
  EMPTY_STAGE,
  newDraft,
  reduceStage,
  type StagedAction,
  type StagedContent,
} from "../src/shell/ledgerStage";
import {
  fakePort,
  hexId,
  listPage,
  movement,
  PROFILE,
  type Call,
  type FakeAnswer,
} from "./support/ledger";

// The apply runner over a fake port: these check the order and the
// outcomes of the orchestration, not the ledger's own answers.

const set = (value: string) => ({ kind: "set" as const, value });
const business = (id: string, extra = {}) =>
  movement(id, {
    business_classification: "BUSINESS",
    category_id: "material_oficina",
    ...extra,
  });
const rowsOf = (...rows: LedgerRow[]) =>
  new Map(rows.map((row) => [row.transaction.transaction_id, row]));

const A = hexId("a");
const B = hexId("b");
const C = hexId("c");
const NEW_A = hexId("a-new");

/** A settled result for each definition the runner sends. */
const bulkResult = (
  total: number,
  applied: number,
  failures: {
    row_index: number;
    transaction_id: string;
    reason: string;
  }[] = [],
): FakeAnswer => ({
  settle: {
    profile_id: PROFILE,
    outcome: "classified",
    result: {
      total,
      applied,
      skipped: total - applied - failures.length,
      failures,
      bucket_event_ids: applied ? ["ev"] : [],
    },
    validation_messages: [],
  },
});
const classified = (written: boolean): FakeAnswer => ({
  settle: {
    outcome: "classified",
    profile_id: PROFILE,
    transaction: null,
    bucket_event_ids: written ? ["ev"] : [],
    validation_kind: "none",
    validation_messages: [],
  },
});
const updated = (from: string, to: string): FakeAnswer => ({
  settle: {
    outcome: "updated",
    profile_id: PROFILE,
    source_transaction_id: from,
    transaction: { transaction_id: to } as JsonObject,
    bucket_event_ids: ["ev"],
    validation_messages: [],
  },
});
const updateRefused: FakeAnswer = {
  settle: {
    outcome: "validation_error",
    profile_id: PROFILE,
    transaction: null,
    bucket_event_ids: [],
    validation_messages: ["A finalized revision cites this movement."],
  },
};
const added = (id: string, written = true): FakeAnswer => ({
  settle: {
    outcome: "created",
    profile_id: PROFILE,
    transaction: { transaction_id: id } as JsonObject,
    bucket_event_ids: written ? ["ev"] : [],
    validation_code: null,
    validation_messages: [],
  },
});
const linked: FakeAnswer = {
  settle: { outcome: "linked", result: { transaction_id: NEW_A } },
};
const definitionOf = (call: Call) =>
  call.kind === "submit" ? call.definition : "answer";

/** Plans `content` against the rows and runs it, answering each call by
 * definition from `answers` in turn. */
async function apply(
  content: StagedContent,
  rows: Map<string, LedgerRow>,
  answers: Record<string, FakeAnswer[]>,
): Promise<{ plan: LedgerPlan; report: ApplyReport; calls: Call[] }> {
  const plan = planApply(content, { rows });
  const { port, calls } = fakePort((call) => {
    const queue = answers[definitionOf(call)];
    const next = queue?.shift();
    if (!next) throw new Error(`no answer for ${definitionOf(call)}`);
    return next;
  });
  const report = await runPlan(port, plan);
  return { plan, report, calls };
}

test("a mixed apply sends each step once, in order, under the ids earlier steps gave", async () => {
  const draft = newDraft();
  draft.fields = {
    booked_date: "2026-10-21",
    amount: "12",
    direction: "OUTGOING",
    description: "TAXI",
  };
  const link: StagedAction = {
    id: "link",
    kind: "link",
    transactionId: A,
    invoiceId: "inv-7",
  };
  const content: StagedContent = {
    rows: {
      [A]: { amount: set("40"), category_id: set("telefono") },
      [B]: { counterparty_country: set("FR") },
    },
    drafts: [draft],
    actions: [link],
  };
  const { report, calls } = await apply(
    content,
    rowsOf(business(A), business(B)),
    {
      "ledger.classify.bulk": [bulkResult(1, 1)],
      "ledger.classify.single": [classified(false)],
      "ledger.update": [updated(A, NEW_A)],
      "ledger.add": [added(hexId("added"))],
      "ledger.link": [linked],
    },
  );
  expect(calls.map(definitionOf)).toEqual([
    "ledger.classify.bulk",
    "ledger.classify.single",
    "ledger.update",
    "ledger.add",
    "ledger.link",
  ]);
  // The link names the id the correction gave the movement.
  const linkCall = calls[4]!;
  expect(linkCall.kind === "submit" && linkCall.payload).toEqual({
    transaction_id: NEW_A,
    invoice_id: "inv-7",
  });
  expect(report.steps.map((step) => step.outcome.kind)).toEqual([
    "applied",
    "unchanged",
    "applied",
    "applied",
    "applied",
  ]);
  expect(report.paused).toBeNull();
  expect(report.stopped).toBeNull();
  expect(report.rekeys).toEqual([{ from: A, to: NEW_A }]);
  // What saved and what was unchanged are both read again.
  expect(report.reread.sort()).toEqual([B, NEW_A].sort());
  expect(keepAfterApply(content, report)).toEqual({
    rows: {},
    drafts: [],
    actions: [],
  });
});

test("a refused row stays staged with its reason, and its later steps are not sent", async () => {
  const content: StagedContent = {
    rows: {
      [A]: { description: set("OTRA") },
      [B]: { description: set("OTRA B") },
    },
    drafts: [],
    actions: [
      { id: "arch", kind: "archive", transactionId: C, reason: "" },
      { id: "link", kind: "link", transactionId: A, invoiceId: "inv-1" },
    ],
  };
  const { report, calls } = await apply(
    content,
    rowsOf(business(A), business(B), business(C)),
    {
      "ledger.update": [updateRefused, updated(B, B)],
      "ledger.archive": [{ settle: { outcome: "updated" } }],
    },
  );
  expect(calls.map(definitionOf)).toEqual([
    "ledger.update",
    "ledger.update",
    "ledger.archive",
  ]);
  expect(report.steps.map((step) => step.outcome)).toEqual([
    {
      kind: "refused",
      reason: "validation_error",
      messages: ["A finalized revision cites this movement."],
      detail: null,
    },
    { kind: "applied", newId: null },
    { kind: "not_sent", why: "after_refusal" },
    { kind: "applied", newId: null },
  ]);
  expect(keepAfterApply(content, report)).toEqual({
    rows: { [A]: ["description"] },
    drafts: [],
    actions: ["link"],
  });
});

test("an unknown outcome pauses every later write and nothing is sent again", async () => {
  const draft = newDraft();
  draft.fields = {
    booked_date: "2026-10-21",
    amount: "12",
    direction: "OUTGOING",
    description: "TAXI",
  };
  const content: StagedContent = {
    rows: {
      [A]: { description: set("OTRA") },
      [B]: { notes: set("Nota") },
    },
    drafts: [draft],
    actions: [{ id: "link", kind: "link", transactionId: C, invoiceId: "inv" }],
  };
  const { report, calls } = await apply(
    content,
    rowsOf(business(A), movement(B), business(C)),
    {
      "ledger.update": [
        { fail: { code: "unknown", operation_id: "op-77" } },
        updated(B, B),
      ],
    },
  );
  expect(calls).toHaveLength(1);
  expect(report.paused).toEqual({ index: 0, operationId: "op-77" });
  expect(report.steps.map((step) => step.outcome.kind)).toEqual([
    "unknown",
    "not_sent",
    "not_sent",
    "not_sent",
  ]);
  expect(report.steps[1]!.outcome).toEqual({ kind: "not_sent", why: "paused" });
  // The unknown change, the draft with its key and the link stay staged.
  const keep = keepAfterApply(content, report);
  expect(keep).toEqual({
    rows: { [A]: ["description"], [B]: ["notes"] },
    drafts: [draft.key],
    actions: ["link"],
  });
  expect(report.reread).toEqual([A]);
});

test("a running or waiting write was not observed to settle: it is unknown", async () => {
  const content: StagedContent = {
    rows: { [A]: { notes: set("Nota") } },
    drafts: [],
    actions: [],
  };
  const { report } = await apply(content, rowsOf(business(A)), {
    "ledger.classify.bulk": [
      {
        outcome: {
          kind: "running",
          operation_id: "op-9",
          revision: 2,
          cancellable: false,
        },
      },
    ],
  });
  expect(report.steps[0]!.outcome).toEqual({
    kind: "unknown",
    operationId: "op-9",
  });
  expect(report.paused).toEqual({ index: 0, operationId: "op-9" });
});

test("a session that went away stops the run without pausing it", async () => {
  const content: StagedContent = {
    rows: {
      [A]: { description: set("OTRA") },
      [B]: { description: set("OTRA B") },
    },
    drafts: [],
    actions: [],
  };
  const { report, calls } = await apply(
    content,
    rowsOf(business(A), business(B)),
    {
      "ledger.update": [
        { fail: { code: "not_signed_in", operation_id: null } },
      ],
    },
  );
  expect(calls).toHaveLength(1);
  expect(report.stopped).toBe("not_signed_in");
  expect(report.paused).toBeNull();
  expect(report.steps.map((step) => step.outcome)).toEqual([
    { kind: "not_sent", why: "stopped" },
    { kind: "not_sent", why: "stopped" },
  ]);
  expect(keepAfterApply(content, report).rows).toEqual({
    [A]: ["description"],
    [B]: ["description"],
  });
});

test("a bulk part saves row by row: failed rows stay staged, the rest are settled", async () => {
  const content: StagedContent = {
    rows: {
      [A]: { category_id: set("telefono") },
      [B]: { category_id: set("telefono") },
      [C]: { category_id: set("telefono") },
    },
    drafts: [],
    actions: [],
  };
  const rows = rowsOf(business(A), business(B), business(C));
  const { report } = await apply(content, rows, {
    "ledger.classify.bulk": [
      bulkResult(3, 1, [
        { row_index: 1, transaction_id: B, reason: "Categoría desconocida." },
      ]),
    ],
  });
  const part = report.steps[0]!;
  // One saved, one skipped: the counts do not say which.
  expect(part.outcome).toEqual({ kind: "settled" });
  expect(part.rows.map((row) => [row.transactionId, row.outcome.kind])).toEqual(
    [
      [A, "settled"],
      [B, "refused"],
      [C, "settled"],
    ],
  );
  expect(part.rows[1]!.outcome).toEqual({
    kind: "refused",
    reason: null,
    messages: ["Categoría desconocida."],
    detail: null,
  });
  expect(keepAfterApply(content, report).rows).toEqual({
    [B]: ["category_id"],
  });
});

test("a part refused whole saves nothing, keeps every row and stops the parts after it", async () => {
  const ids = Array.from({ length: 4 }, (_, at) => hexId(`p${at}`));
  const content: StagedContent = {
    rows: Object.fromEntries(
      ids.map((id) => [id, { category_id: set("telefono") }]),
    ),
    drafts: [],
    actions: [],
  };
  const rows = rowsOf(...ids.map((id) => business(id)));
  // A bound small enough for one row per part.
  const plan = planApply(content, { rows, payloadLimit: 160 });
  expect(plan.steps.filter((step) => step.kind === "bulk")).toHaveLength(4);
  const { port, calls } = fakePort((_, at) =>
    at === 0 ? bulkResult(1, 1) : { refuse: "REFUSED_LEDGER_REVISION_CHANGED" },
  );
  const report = await runPlan(port, plan);
  expect(calls).toHaveLength(2);
  expect(report.steps.map((step) => step.outcome)).toEqual([
    { kind: "applied", newId: null },
    {
      kind: "refused",
      reason: "REFUSED_LEDGER_REVISION_CHANGED",
      messages: [],
      detail: null,
    },
    { kind: "not_sent", why: "after_part" },
    { kind: "not_sent", why: "after_part" },
  ]);
  expect(Object.keys(keepAfterApply(content, report).rows).sort()).toEqual(
    ids.slice(1).sort(),
  );
});

test("a model suggestion is answered with the digest of the review the page showed", async () => {
  const suggestion: StagedAction = {
    id: "s",
    kind: "suggestion",
    transactionId: A,
    operationId: "op-review",
    reviewDigest: "digest-shown",
    decision: "apply",
    reason: "",
  };
  const content: StagedContent = {
    rows: {},
    drafts: [],
    actions: [suggestion],
  };
  const ok = await apply(content, rowsOf(movement(A)), {
    answer: [{ settle: { response: "apply" } }],
  });
  expect(ok.calls).toEqual([
    {
      kind: "answer",
      operation: "op-review",
      digest: "digest-shown",
      decision: "apply",
    },
  ]);
  expect(ok.report.steps[0]!.outcome.kind).toBe("applied");
  // A review that changed since it was shown needs a new answer.
  const changed = await apply(content, rowsOf(movement(A)), {
    answer: [{ fail: { code: "review_changed", operation_id: "op-review" } }],
  });
  expect(changed.report.steps[0]!.outcome).toEqual({
    kind: "refused",
    reason: "review_changed",
    messages: [],
    detail: null,
  });
  expect(keepAfterApply(content, changed.report).actions).toEqual(["s"]);
});

test("a replayed add is unchanged, and a saved-but-unread write pauses but is not kept", async () => {
  const draft = newDraft();
  draft.fields = {
    booked_date: "2026-10-21",
    amount: "12",
    direction: "OUTGOING",
    description: "TAXI",
  };
  const replay = await apply(
    { rows: {}, drafts: [draft], actions: [] },
    rowsOf(),
    { "ledger.add": [added(hexId("x"), false)] },
  );
  expect(replay.report.steps[0]!.outcome).toEqual({ kind: "unchanged" });
  expect(
    keepAfterApply({ rows: {}, drafts: [draft], actions: [] }, replay.report)
      .drafts,
  ).toEqual([]);

  const content: StagedContent = {
    rows: { [A]: { notes: set("x") }, [B]: { notes: set("y") } },
    drafts: [],
    actions: [],
  };
  const unread = await apply(content, rowsOf(movement(A), movement(B)), {
    "ledger.update": [{ fail: { code: "saved_unread", operation_id: "op-5" } }],
  });
  expect(unread.report.paused).toEqual({ index: 0, operationId: "op-5" });
  expect(keepAfterApply(content, unread.report).rows).toEqual({
    [B]: ["notes"],
  });
});

test("the stage after an apply keeps what did not save under the movement's new id", async () => {
  const content: StagedContent = {
    rows: { [A]: { amount: set("40") } },
    drafts: [],
    actions: [{ id: "link", kind: "link", transactionId: A, invoiceId: "inv" }],
  };
  const { report } = await apply(content, rowsOf(business(A)), {
    "ledger.update": [updated(A, NEW_A)],
    "ledger.link": [
      {
        fail: { code: "refused", operation_id: null, reason: "invoice_linked" },
      },
    ],
  });
  let state = { ...EMPTY_STAGE, content };
  state = reduceStage(state, { type: "apply_started" });
  for (const event of stageAfterApply(content, report))
    state = reduceStage(state, event);
  expect(state.content).toEqual({
    rows: {},
    drafts: [],
    actions: [
      { id: "link", kind: "link", transactionId: NEW_A, invoiceId: "inv" },
    ],
  });
  expect(state.undo).toEqual([]);
});

test("the read at apply names staged rows that changed or left since the page read them", async () => {
  const before = business(A);
  const content: StagedContent = {
    rows: { [A]: { notes: set("x") }, [B]: { notes: set("y") } },
    drafts: [],
    actions: [{ id: "arch", kind: "archive", transactionId: C, reason: "" }],
  };
  const read = rowsOf(before, movement(B), movement(C));
  const after = business(A, {
    modified_at: "2026-10-23T10:58:00Z",
    notes: "Otra ventana",
  });
  const fresh = rowsOf(after, movement(B));
  expect(changedSinceRead(content, read, fresh)).toEqual([
    { kind: "changed", transactionId: A, before, after },
    { kind: "gone", transactionId: C, before: movement(C) },
  ]);
  const { port } = fakePort(() => ({
    settle: listPage([after, movement(B)], 2, 0, 250),
  }));
  const prepared = await prepareApply(
    port,
    { year: 2026, code: "4T" },
    content,
    read,
  );
  expect(prepared.kind).toBe("ready");
  expect(
    prepared.kind === "ready" && prepared.conflicts.map((c) => c.kind),
  ).toEqual(["changed", "gone"]);
});

test("a re-read tells whether an unknown write saved; an add is never told", () => {
  const content: StagedContent = {
    rows: { [A]: { notes: set("Nota") } },
    drafts: [],
    actions: [],
  };
  const plan = planApply(content, { rows: rowsOf(movement(A)) });
  const step = plan.steps[0]!;
  expect(
    resolveUnknown(step, content, rowsOf(movement(A, { notes: "Nota" }))),
  ).toEqual(new Map([[A, "saved"]]));
  expect(resolveUnknown(step, content, rowsOf(movement(A)))).toEqual(
    new Map([[A, "not_saved"]]),
  );
  expect(resolveUnknown(step, content, rowsOf())).toEqual(
    new Map([[A, "undetermined"]]),
  );
  const link: StagedAction = {
    id: "l",
    kind: "link",
    transactionId: A,
    invoiceId: "inv",
  };
  const linkPlan = planApply(
    { rows: {}, drafts: [], actions: [link] },
    { rows: rowsOf(movement(A)) },
  );
  expect(
    resolveUnknown(
      linkPlan.steps[0]!,
      content,
      rowsOf(movement(A, { invoice_id: "inv" })),
    ),
  ).toEqual(new Map([[A, "saved"]]));
  expect(
    resolveUnknown(linkPlan.steps[0]!, content, rowsOf(movement(A))),
  ).toEqual(new Map([[A, "not_saved"]]));
  const draft = newDraft();
  draft.fields = {
    booked_date: "2026-10-01",
    amount: "1",
    direction: "INCOMING",
    description: "X",
  };
  const addPlan = planApply(
    { rows: {}, drafts: [draft], actions: [] },
    { rows: rowsOf() },
  );
  expect(resolveUnknown(addPlan.steps[0]!, content, rowsOf())).toEqual(
    new Map([[draft.key, "undetermined"]]),
  );
});
