import { expect, test } from "@playwright/test";
import type {
  JsonObject,
  LedgerOutcome,
  LedgerPort,
  LedgerRow,
} from "../src/shell/ledger";
import {
  changedSinceRead,
  keepAfterApply,
  askReview,
  prepareApply,
  RELEASE_OBSERVATIONS,
  releaseReview,
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
    currency: "EUR",
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
    currency: "EUR",
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
    currency: "EUR",
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
    currency: "EUR",
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

test("a split's parts are classified one by one once the split settles, by their new ids", async () => {
  const split: StagedAction = {
    id: "split",
    kind: "split",
    transactionId: A,
    reason: "",
    children: [
      {
        amount: "10.00",
        description: "uno",
        classify: { classification: "BUSINESS", category_id: "telefono" },
      },
      { amount: "26.30", description: "dos" },
      {
        amount: "5",
        description: "tres",
        classify: { classification: "MIXED", business_pct: "0.50" },
      },
    ],
  };
  const content: StagedContent = { rows: {}, drafts: [], actions: [split] };
  const children = [hexId("c1"), hexId("c2"), hexId("c3")];
  const done = await apply(content, rowsOf(movement(A, { amount: "41.30" })), {
    "ledger.split.manual": [
      { settle: { profile_id: PROFILE, child_transaction_ids: children } },
    ],
    "ledger.classify.single": [
      { settle: { outcome: "classified", bucket_event_ids: ["e1"] } },
      { fail: { code: "unknown", operation_id: "op-c3" } },
    ],
  });
  expect(
    done.calls.map((call) => call.kind === "submit" && call.payload),
  ).toEqual([
    expect.objectContaining({ transaction_id: A }),
    {
      transaction_id: children[0],
      patch: { business_classification: "BUSINESS", category_id: "telefono" },
      patch_fields: ["business_classification", "category_id"],
    },
    {
      transaction_id: children[2],
      patch: { business_classification: "MIXED", business_pct: "0.5" },
      patch_fields: ["business_classification", "business_pct"],
    },
  ]);
  // An unknown part pauses what comes after, like any write.
  expect(done.report.paused).toEqual({ index: 0, operationId: "op-c3" });
  expect(done.report.steps.map((step) => step.follows ?? null)).toEqual([
    null,
    "split",
    "split",
  ]);
  // A split is never sent twice: it leaves the stage once it settled.
  expect(keepAfterApply(content, done.report).actions).toEqual([]);
  // A split the product refused sends no part's classification.
  const refused = await apply(content, rowsOf(movement(A)), {
    "ledger.split.manual": [{ refuse: "validation_error" }],
  });
  expect(refused.calls).toHaveLength(1);
  expect(keepAfterApply(content, refused.report).actions).toEqual(["split"]);
});

test("a split whose result does not name its parts says their classifications were not sent", async () => {
  const split: StagedAction = {
    id: "split",
    kind: "split",
    transactionId: A,
    reason: "",
    children: [
      {
        amount: "10.00",
        description: "uno",
        classify: { classification: "PERSONAL" },
      },
      { amount: "26.30", description: "dos" },
    ],
  };
  const content: StagedContent = { rows: {}, drafts: [], actions: [split] };
  for (const named of [undefined, [hexId("c1")]]) {
    const done = await apply(content, rowsOf(movement(A)), {
      "ledger.split.manual": [
        {
          settle: {
            profile_id: PROFILE,
            ...(named ? { child_transaction_ids: named } : {}),
          },
        },
      ],
    });
    // Nothing is sent to a part no result named.
    expect(done.calls).toHaveLength(1);
    expect(
      done.report.steps.map((step) => [step.outcome, step.follows ?? null]),
    ).toEqual([
      [{ kind: "applied", newId: null }, null],
      [{ kind: "not_sent", why: "parts_unnamed" }, "split"],
    ]);
    // The row says so for no movement: the split itself saved and leaves
    // the stage, and nothing is paused or held back by it.
    expect(done.report.steps[1]!.rows).toEqual([]);
    expect(done.report.paused).toBeNull();
    expect(done.report.reread).toEqual([A]);
    expect(keepAfterApply(content, done.report).actions).toEqual([]);
  }
  // A split with no part classification staged has nothing to report.
  const plain: StagedContent = {
    rows: {},
    drafts: [],
    actions: [
      {
        ...split,
        children: split.children.map(({ amount, description }) => ({
          amount,
          description,
        })),
      },
    ],
  };
  const quiet = await apply(plain, rowsOf(movement(A)), {
    "ledger.split.manual": [{ settle: { profile_id: PROFILE } }],
  });
  expect(quiet.report.steps).toHaveLength(1);
});

test("a document added as evidence is attached by the evidence id it settled with", async () => {
  const add: StagedAction = {
    id: "doc",
    kind: "attach_file",
    transactionId: A,
    file: "file-1" as never,
    name: "ticket.pdf",
    idempotencyKey: "desktop-evidence-1",
  };
  const content: StagedContent = { rows: {}, drafts: [], actions: [add] };
  const settled = {
    settle: {
      profile_id: PROFILE,
      record: { evidence_id: "0123456789abcdef" },
    },
  };
  const done = await apply(content, rowsOf(business(A)), {
    "ledger.evidence.add": [settled],
    "ledger.attach": [{ settle: { profile_id: PROFILE } }],
  });
  expect(
    done.calls.map((call) => call.kind === "submit" && call.payload),
  ).toEqual([
    { source_path: "file-1", idempotency_key: "desktop-evidence-1" },
    {
      transaction_id: A,
      purchase_invoice_evidence_id: "0123456789abcdef",
      attachment_ids: [],
    },
  ]);
  expect(keepAfterApply(content, done.report).actions).toEqual([]);
  // An attach that was refused keeps the add staged: sent again under its
  // key it is the same add, then the attach.
  const kept = await apply(content, rowsOf(business(A)), {
    "ledger.evidence.add": [settled],
    "ledger.attach": [{ refuse: "validation_error" }],
  });
  expect(keepAfterApply(content, kept.report).actions).toEqual(["doc"]);
});

test("a rule apply is one call, and the movements a rule classified are what saved", async () => {
  const rules: StagedAction = {
    id: "rules",
    kind: "rule_apply",
    reaffirm: false,
    transactionIds: [A, B],
  };
  const content: StagedContent = { rows: {}, drafts: [], actions: [rules] };
  const done = await apply(content, rowsOf(movement(A), movement(B)), {
    "ledger.rule.apply": [
      {
        settle: {
          profile_id: PROFILE,
          outcome: "applied",
          applied: [
            {
              transaction_id: A,
              matched_rule_id: "rule-1",
              classification: "PERSONAL",
            },
          ],
        },
      },
    ],
  });
  expect(done.calls).toHaveLength(1);
  expect(done.report.steps[0]!.rows).toEqual([
    { transactionId: A, outcome: { kind: "applied", newId: null } },
    { transactionId: B, outcome: { kind: "unchanged" } },
  ]);
  expect(done.report.reread.sort()).toEqual([A, B].sort());
  expect(keepAfterApply(content, done.report).actions).toEqual([]);
});

test("a rule apply whose outcome is unknown is reported by its action, never as no finding", () => {
  const rules: StagedAction = {
    id: "rules",
    kind: "rule_apply",
    reaffirm: false,
    transactionIds: [A, B],
  };
  const content: StagedContent = { rows: {}, drafts: [], actions: [rules] };
  const plan = planApply(content, { rows: rowsOf(movement(A), movement(B)) });
  const step = plan.steps[0]!;
  // The rules decide their movements as they run: a classified movement
  // does not tell whether the rules or someone else classified it.
  for (const fresh of [
    rowsOf(movement(A), movement(B)),
    rowsOf(movement(A, { business_classification: "PERSONAL" }), movement(B)),
  ])
    expect(resolveUnknown(step, content, fresh)).toEqual(
      new Map([["rules", "undetermined"]]),
    );
});

/** A port whose observations follow `seen` in order, the last repeated,
 * and whose cancel answers `cancelled`. */
function reviewPort(
  seen: (LedgerOutcome | Error)[],
  cancelled: () => Promise<LedgerOutcome>,
) {
  const asked: [string, number][] = [];
  let observed = 0;
  const port = {
    ...fakePort(() => ({ refuse: "unused" })).port,
    observe: async () => {
      const now = seen[Math.min(observed, seen.length - 1)]!;
      observed += 1;
      if (now instanceof Error) throw now;
      return now;
    },
    cancel: async (operation: string, revision: number) => {
      asked.push([operation, revision]);
      return cancelled();
    },
  };
  return { port, asked, observed: () => observed };
}
const waiting = (revision: number, cancellable = true): LedgerOutcome => ({
  kind: "review",
  operation_id: "op-1",
  revision,
  cancellable,
});
const running: LedgerOutcome = {
  kind: "running",
  operation_id: "op-1",
  revision: 8,
  cancellable: false,
};
const cancelledNow: LedgerOutcome = {
  kind: "refused",
  operation_id: "op-1",
  revision: 9,
  reason: null,
  detail: null,
};
const hostRefusal = (code: string, reason: string) =>
  Object.assign(new Error(code), { code, reason, operation_id: "op-1" });

test("a review the page will not answer is cancelled at the revision observed now, and followed until it settles", async () => {
  // The cancel answers while the review still settles; the release follows
  // it until it is neither waiting nor running.
  const settling = reviewPort(
    [waiting(7), running, running, cancelledNow],
    async () => running,
  );
  await releaseReview(settling.port, "op-1", A);
  expect(settling.asked).toEqual([["op-1", 7]]);
  expect(settling.observed()).toBe(4);

  // A cancel that settles at once is not observed again.
  const settled = reviewPort([waiting(3)], async () => cancelledNow);
  await releaseReview(settled.port, "op-1", A);
  expect(settled.asked).toEqual([["op-1", 3]]);
  expect(settled.observed()).toBe(1);
});

test("a review that cannot be cancelled now is left as it is, and a refused or lost cancel is observed, never sent again", async () => {
  for (const now of [
    waiting(3, false),
    {
      kind: "settled" as const,
      operation_id: "op-1",
      revision: 9,
      result: {},
    },
    running,
    new Error("unavailable"),
  ]) {
    const left = reviewPort([now], async () => cancelledNow);
    await releaseReview(left.port, "op-1", A);
    expect(left.asked).toEqual([]);
  }
  // Answered first: the review is now a write, followed until it settles.
  const answered = reviewPort([waiting(4), running, cancelledNow], async () => {
    throw hostRefusal("refused", "stale_operation_revision");
  });
  await releaseReview(answered.port, "op-1", A);
  expect(answered.asked).toEqual([["op-1", 4]]);
  expect(answered.observed()).toBe(3);
  const lost = reviewPort([waiting(4), cancelledNow], async () => {
    throw hostRefusal("unknown", "unknown");
  });
  await releaseReview(lost.port, "op-1", A);
  expect(lost.asked).toEqual([["op-1", 4]]);
  expect(lost.observed()).toBe(2);
  // A review the runtime cannot cancel is not waited for.
  const unsupported = reviewPort([waiting(4)], async () => {
    throw hostRefusal("refused", "cancellation_unsupported");
  });
  await releaseReview(unsupported.port, "op-1", A);
  expect(unsupported.observed()).toBe(1);
});

test("a review that never settles is followed only within the bound", async () => {
  const stuck = reviewPort([waiting(5), running], async () => running);
  await releaseReview(stuck.port, "op-1", A);
  expect(stuck.observed()).toBe(1 + RELEASE_OBSERVATIONS);
});

test("a new ask about a movement waits for its earlier review's release, and an ask about another does not", async () => {
  const events: string[] = [];
  let settle: () => void = () => {};
  const released = new Promise<void>((done) => (settle = done));
  const port = {
    ...fakePort(() => ({ refuse: "unused" })).port,
    observe: async (): Promise<LedgerOutcome> => {
      events.push("observe");
      await released;
      return cancelledNow;
    },
    cancel: async (): Promise<LedgerOutcome> => cancelledNow,
    submit: async (_definition: string, payload: unknown) => {
      events.push(`submit ${(payload as JsonObject).transaction_id}`);
      return waiting(2);
    },
  } as unknown as LedgerPort;
  const release = releaseReview(port, "op-1", A);
  const again = askReview(port, "ledger.classify.review", {
    transaction_id: A,
    mode: "classification",
    origin: "classify_llm_apply",
  });
  await askReview(port, "ledger.classify.review", {
    transaction_id: B,
    mode: "classification",
    origin: "classify_llm_apply",
  });
  expect(events).toEqual(["observe", `submit ${B}`]);
  settle();
  await release;
  await again;
  expect(events).toEqual(["observe", `submit ${B}`, `submit ${A}`]);
});
