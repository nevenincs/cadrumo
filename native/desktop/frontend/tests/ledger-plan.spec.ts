import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import type { LedgerRow } from "../src/shell/ledger";
import { RELAY_PAYLOAD_LIMIT } from "../src/shell/relayBounds";
import { classifyCells, ratioCoverage } from "../src/shell/ledgerCommands";
import {
  bulkCsv,
  payloadSize,
  splitBulk,
  type BulkRow,
  type LedgerPlan,
  type PlanBlocker,
  type PlanStep,
} from "../src/shell/ledgerPlan";
import {
  EMPTY_CONTENT,
  EMPTY_STAGE,
  newDraft,
  movementsToTrack,
  reduceStage,
  type Draft,
  type StageField,
  type StagedAction,
  type StagedContent,
  type StagedRowChanges,
} from "../src/shell/ledgerStage";
import { hexId, movement } from "./support/ledger";
import { servedFilingYears } from "../src/dev/servedYearAuthority";
import {
  planRecorded,
  recordedCheck,
  servedBlocker,
} from "./support/stagedCheck";

// How staged changes become operations. No page is opened.

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
const contextOf = (...rows: LedgerRow[]) => ({
  rows: new Map(rows.map((row) => [row.transaction.transaction_id, row])),
});
const staged = (
  rows: Record<string, StagedRowChanges>,
  actions: StagedAction[] = [],
  drafts: Draft[] = [],
): StagedContent => ({ rows, actions, drafts });
const blockersOf = (plan: LedgerPlan, id: string): PlanBlocker["kind"][] =>
  plan.entries
    .find((entry) => entry.transactionId === id)!
    .blockers.map((blocker) => blocker.kind);
const stepKinds = (plan: LedgerPlan) =>
  plan.steps.map((step) =>
    step.kind === "action" ? `action:${step.action.kind}` : step.kind,
  );

test("a selected new draft is never read as a stored movement's filing participation", () => {
  const draft = newDraft();
  const saved = hexId("a");
  const changed = hexId("b");
  const content = staged(
    { [changed]: { description: set("changed") } },
    [],
    [draft],
  );
  expect(movementsToTrack(content, new Set([draft.key, saved]))).toEqual([
    saved,
    changed,
  ]);
  expect(content.drafts).toEqual([draft]);
  // Once an apply removes the draft, its old selection is still not a stored handle.
  expect(
    movementsToTrack(
      { ...content, drafts: [] },
      new Set([draft.key, saved, "af", "", "ABC", "f".repeat(65)]),
    ),
  ).toEqual([saved, "af", changed]);
});

test("every field routes by the operation that accepts it, and by set or clear", () => {
  type Case = [StageField, "set" | "clear", boolean, string];
  const cases: Case[] = [
    // Identity and other update-only fields.
    ["description", "set", true, "update"],
    ["description", "clear", true, "cannot_clear"],
    ["amount", "set", false, "update"],
    ["amount", "clear", true, "cannot_clear"],
    ["booked_date", "clear", true, "cannot_clear"],
    ["value_date", "clear", true, "update"],
    ["operation_date", "set", true, "update"],
    ["operation_date", "clear", true, "update"],
    ["accrual_date", "set", true, "update"],
    ["accrual_date", "clear", true, "update"],
    ["direction", "set", true, "update"],
    ["currency", "set", true, "update"],
    ["counterparty", "clear", true, "update"],
    ["group_label", "set", true, "update"],
    ["group_label", "clear", false, "update"],
    ["own_account_id", "clear", true, "update"],
    // The bulk takes classification sets only.
    ["business_classification", "set", true, "bulk"],
    ["business_classification", "clear", true, "cannot_clear"],
    ["category_id", "set", true, "bulk"],
    ["category_id", "set", false, "needs_classification"],
    ["category_id", "clear", true, "classify"],
    ["category_id", "clear", false, "needs_classification"],
    ["iva_category", "set", true, "bulk"],
    ["iva_category", "clear", true, "classify"],
    ["business_pct", "set", true, "bulk"],
    ["business_pct", "clear", true, "classify"],
    ["usage_ratio_id", "set", true, "bulk"],
    ["usage_ratio_id", "set", false, "needs_classification"],
    ["usage_ratio_id", "clear", true, "cannot_clear"],
    // Tax figures: bulk on a classified row, update otherwise and to clear.
    ["taxable_base", "set", true, "bulk"],
    ["taxable_base", "set", false, "update"],
    ["taxable_base", "clear", true, "update"],
    ["iva_rate", "clear", false, "update"],
    ["iva_amount", "set", true, "bulk"],
    ["irpf_category", "set", false, "update"],
    ["irpf_category", "clear", true, "update"],
    // Notes are replaced, never blanked.
    ["notes", "set", true, "bulk"],
    ["notes", "set", false, "update"],
    ["notes", "clear", true, "cannot_clear"],
    // Fields the bulk has no column for go one at a time.
    ["counterparty_identification_state", "set", true, "classify"],
    ["counterparty_identification_state", "clear", true, "classify"],
    ["counterparty_identification_state", "set", false, "needs_classification"],
    ["counterparty_country", "set", true, "classify"],
    ["deduction_fact_kind", "clear", true, "classify"],
    ["investment_asset_id", "set", true, "classify"],
  ];
  const A = hexId("a");
  const U = hexId("u");
  for (const [field, kind, classified, expected] of cases) {
    const row = classified ? business(A) : movement(U);
    const id = row.transaction.transaction_id;
    const check = recordedCheck(
      staged({
        [id]: {
          // A classification that decides the row; the ledger reads what is staged.
          [field]:
            kind === "set"
              ? set(
                  field === "business_classification" && classified
                    ? "BUSINESS"
                    : "x",
                )
              : clear,
        },
      }),
      contextOf(row).rows,
    );
    const route = check.rows.get(id)!.routes.find((r) => r.field === field)!;
    const found = route.route ?? route.refused;
    expect(found, `${field} ${kind} classified=${classified}`).toBe(expected);
  }
});

test("the bulk never carries a clear: a cleared category goes through a masked single classification", () => {
  const A = hexId("a");
  const plan = planRecorded(
    staged({ [A]: { category_id: clear, notes: set("Revisado") } }),
    contextOf(business(A)),
  );
  expect(stepKinds(plan)).toEqual(["bulk", "classify"]);
  const bulk = plan.steps[0] as Extract<PlanStep, { kind: "bulk" }>;
  expect(bulk.request.csv_text).toBe(
    `transaction_id,classification,notes\n${A},BUSINESS,Revisado\n`,
  );
  const single = plan.steps[1] as Extract<PlanStep, { kind: "classify" }>;
  expect(single.request).toEqual({
    transaction_id: A,
    patch: { business_classification: "BUSINESS", category_id: null },
    patch_fields: ["business_classification", "category_id"],
  });
  for (const step of plan.steps)
    if (step.kind === "bulk")
      for (const row of step.rows)
        for (const cell of Object.values(row.cells)) expect(cell).not.toBe("");
});

test("each bulk row names its classification, and a mixed row its share", () => {
  const A = hexId("a");
  const M = hexId("m");
  const U = hexId("u");
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
    contextOf(business(A), mixed(M), movement(U)),
  );
  expect(stepKinds(plan)).toEqual(["bulk"]);
  const bulk = plan.steps[0] as Extract<PlanStep, { kind: "bulk" }>;
  expect(bulk.request.csv_text).toBe(
    [
      "transaction_id,classification,category_id,business_pct,taxable_base,iva_rate",
      `${A},BUSINESS,telefono,,,`,
      `${M},MIXED,,0.6,30,0.21`,
      `${U},MIXED,suministros,0.5,,`,
      "",
    ].join("\n"),
  );
  const notes = plan.entries.flatMap((entry) =>
    entry.notes.map(
      (note) =>
        `${entry.transactionId === A ? "A" : entry.transactionId === M ? "M" : "U"}:${note.kind}`,
    ),
  );
  expect(notes).toEqual([
    "A:sends_current_classification",
    "M:sends_current_share",
    "M:sends_current_classification",
  ]);
});

test("single classification carries its mask sorted, the current classification and a mixed share", () => {
  const M = hexId("m");
  const plan = planRecorded(
    staged(
      {
        [M]: {
          counterparty_identification_state: set("FR"),
          counterparty_country: clear,
        },
      },
      [
        {
          id: "m210-1",
          kind: "m210",
          transactionId: M,
          options: { tipo_renta_code: "1", payer_mode: "none" },
        },
      ],
    ),
    contextOf(mixed(M)),
  );
  expect(stepKinds(plan)).toEqual(["classify"]);
  const single = plan.steps[0] as Extract<PlanStep, { kind: "classify" }>;
  expect(single.m210Action).toBe("m210-1");
  expect(single.request).toEqual({
    transaction_id: M,
    patch: {
      business_classification: "MIXED",
      business_pct: "0.6",
      counterparty_identification_state: "FR",
      counterparty_country: null,
    },
    patch_fields: [
      "business_classification",
      "business_pct",
      "counterparty_country",
      "counterparty_identification_state",
      "m210_income_classification",
    ],
    m210: { tipo_renta_code: "1", payer_mode: "none" },
  });
});

test("corrections go through a masked update; tax figures on an unclassified row too", () => {
  const U = hexId("u");
  const plan = planRecorded(
    staged({
      [U]: {
        description: set("TAXI AEROPUERTO"),
        amount: set("40.00"),
        value_date: clear,
        taxable_base: set("33.06"),
        notes: set("Viaje"),
      },
    }),
    contextOf(movement(U)),
  );
  expect(stepKinds(plan)).toEqual(["update"]);
  const update = plan.steps[0] as Extract<PlanStep, { kind: "update" }>;
  expect(update.newIdentity).toBe(true);
  expect(update.request).toEqual({
    transaction_id: U,
    patch: {
      value_date: null,
      amount: "40",
      description: "TAXI AEROPUERTO",
      taxable_base: "33.06",
      notes: "Viaje",
    },
    patch_fields: [
      "value_date",
      "amount",
      "description",
      "taxable_base",
      "notes",
    ],
  });
  expect(plan.entries[0]!.notes.map((note) => note.kind)).toContain(
    "new_identity",
  );
});

test("an operation date is sent through the masked update, and cleared by a null", () => {
  const O = hexId("o");
  const setPlan = planRecorded(
    staged({ [O]: { operation_date: set("2026-09-30") } }),
    contextOf(movement(O)),
  );
  expect(stepKinds(setPlan)).toEqual(["update"]);
  const sent = setPlan.steps[0] as Extract<PlanStep, { kind: "update" }>;
  expect(sent.newIdentity).toBe(false);
  expect(sent.request).toEqual({
    transaction_id: O,
    patch: { operation_date: "2026-09-30" },
    patch_fields: ["operation_date"],
  });

  const stored = movement(O, { operation_date: "2026-09-30" });
  const clearPlan = planRecorded(
    staged({ [O]: { operation_date: clear } }),
    contextOf(stored),
  );
  expect(clearPlan.entries[0]!.clears).toEqual(["operation_date"]);
  const cleared = clearPlan.steps[0] as Extract<PlanStep, { kind: "update" }>;
  expect(cleared.request).toEqual({
    transaction_id: O,
    patch: { operation_date: null },
    patch_fields: ["operation_date"],
  });
});

test("a transfer is held from an operation date by the ledger's answer", () => {
  const T = hexId("t");
  const plan = planRecorded(
    staged({ [T]: { operation_date: set("2026-09-30") } }),
    contextOf(movement(T, { direction: "INTERNAL_TRANSFER" })),
  );
  expect(blockersOf(plan, T)).toEqual(["transfer_with_tax"]);
  expect(stepKinds(plan)).toEqual([]);
});

test("an accrual date is sent through the masked update, and cleared by a null", () => {
  const O = hexId("c");
  const setPlan = planRecorded(
    staged({ [O]: { accrual_date: set("2026-09-29") } }),
    contextOf(movement(O)),
  );
  expect(stepKinds(setPlan)).toEqual(["update"]);
  const sent = setPlan.steps[0] as Extract<PlanStep, { kind: "update" }>;
  expect(sent.newIdentity).toBe(false);
  expect(sent.request).toEqual({
    transaction_id: O,
    patch: { accrual_date: "2026-09-29" },
    patch_fields: ["accrual_date"],
  });

  const stored = movement(O, { accrual_date: "2026-09-29" });
  const clearPlan = planRecorded(
    staged({ [O]: { accrual_date: clear } }),
    contextOf(stored),
  );
  expect(clearPlan.entries[0]!.clears).toEqual(["accrual_date"]);
  const cleared = clearPlan.steps[0] as Extract<PlanStep, { kind: "update" }>;
  expect(cleared.request).toEqual({
    transaction_id: O,
    patch: { accrual_date: null },
    patch_fields: ["accrual_date"],
  });
});

test("a transfer is held from an accrual date by the ledger's answer", () => {
  const T = hexId("t");
  const plan = planRecorded(
    staged({ [T]: { accrual_date: set("2026-09-29") } }),
    contextOf(movement(T, { direction: "INTERNAL_TRANSFER" })),
  );
  expect(blockersOf(plan, T)).toEqual(["transfer_with_tax"]);
  expect(stepKinds(plan)).toEqual([]);
});

test("a transfer takes no tax field and no business classification", () => {
  const A = hexId("a");
  const T = hexId("t");
  const P = hexId("p");
  const plan = planRecorded(
    staged({
      // A business row turned into a transfer keeps its business facts.
      [A]: { direction: set("INTERNAL_TRANSFER") },
      [T]: { taxable_base: set("10") },
      [P]: { business_classification: set("PERSONAL") },
    }),
    contextOf(
      business(A),
      movement(T, { direction: "INTERNAL_TRANSFER" }),
      movement(P, { direction: "INTERNAL_TRANSFER" }),
    ),
  );
  expect(blockersOf(plan, A)).toEqual(["transfer_with_tax"]);
  expect(plan.entries[0]!.blockers[0]).toEqual(
    servedBlocker("transfer_with_tax", [
      "business_classification",
      "category_id",
    ]),
  );
  expect(blockersOf(plan, T)).toEqual(["transfer_with_tax"]);
  // Personal is what a transfer may be.
  expect(blockersOf(plan, P)).toEqual([]);
  expect(stepKinds(plan)).toEqual(["bulk"]);
});

test("an action and an edit on the same row hold the row; exclude names the classification", () => {
  const A = hexId("a");
  const B = hexId("b");
  const C = hexId("c");
  const plan = planRecorded(
    staged(
      {
        [A]: { notes: set("x") },
        [B]: { category_id: set("telefono") },
        [C]: { description: set("OTRA") },
      },
      [
        { id: "arch", kind: "archive", transactionId: A, reason: "" },
        { id: "excl", kind: "exclude", transactionId: B, reason: "Duplicado" },
        { id: "link", kind: "link", transactionId: C, invoiceId: "inv-1" },
      ],
    ),
    contextOf(business(A), business(B), business(C)),
  );
  expect(plan.entries[0]!.blockers).toEqual([
    { kind: "action_and_edits", action: "arch" },
  ]);
  expect(plan.entries[1]!.blockers).toEqual([
    { kind: "exclude_and_classification", action: "excl" },
  ]);
  // A link may follow a correction: it is sent under the row's new id.
  expect(blockersOf(plan, C)).toEqual([]);
  expect(stepKinds(plan)).toEqual(["update", "action:link"]);
  expect(plan.held).toEqual({
    rows: [A, B],
    drafts: [],
    actions: ["arch", "excl"],
  });
});

test("sealed, inactive and vanished rows hold their changes", () => {
  const S = hexId("s");
  const I = hexId("i");
  const G = hexId("g");
  const R = hexId("r");
  const plan = planRecorded(
    staged(
      {
        [S]: { category_id: set("telefono") },
        [I]: { notes: set("x") },
        [G]: { notes: set("y") },
      },
      [{ id: "restore", kind: "restore", transactionId: R, reason: "" }],
    ),
    {
      ...contextOf(
        business(S),
        movement(I, { lifecycle_state: "ARCHIVED" }),
        movement(R, { lifecycle_state: "STASHED" }),
      ),
      sealed: new Set([S]),
    },
  );
  expect(blockersOf(plan, S)).toEqual(["sealed"]);
  expect(blockersOf(plan, I)).toEqual(["not_active"]);
  expect(blockersOf(plan, G)).toEqual(["gone"]);
  // Restoring a set-aside row is what makes it editable.
  expect(blockersOf(plan, R)).toEqual([]);
  expect(stepKinds(plan)).toEqual(["action:restore"]);
});

test("what cannot be cleared or needs a classification first is held, never dropped", () => {
  const A = hexId("a");
  const U = hexId("u");
  const M = hexId("m");
  const P = hexId("p");
  const plan = planRecorded(
    staged({
      [A]: { notes: clear, usage_ratio_id: clear },
      [U]: { category_id: set("telefono"), counterparty_country: set("FR") },
      [M]: { business_pct: clear },
      [P]: { business_pct: set("0.5") },
    }),
    contextOf(
      business(A, { notes: "Algo" }),
      movement(U),
      mixed(M),
      business(P),
    ),
  );
  expect(plan.entries[0]!.blockers).toEqual([
    servedBlocker("cannot_clear", ["usage_ratio_id", "notes"]),
  ]);
  expect(plan.entries[1]!.blockers).toEqual([
    servedBlocker("needs_classification", [
      "category_id",
      "counterparty_country",
    ]),
  ]);
  expect(blockersOf(plan, M)).toEqual(["mixed_needs_share"]);
  expect(blockersOf(plan, P)).toEqual(["share_needs_mixed"]);
  expect(plan.steps).toEqual([]);
  expect(plan.summary.held).toBe(4);
  expect(plan.summary.blockers).toEqual({
    cannot_clear: 1,
    needs_classification: 1,
    mixed_needs_share: 1,
    share_needs_mixed: 1,
  });
});

test("a model suggestion is not combined with the person's own edits or a second action", () => {
  const A = hexId("a");
  const B = hexId("b");
  const suggestion = (id: string, row: string): StagedAction => ({
    id,
    kind: "suggestion",
    transactionId: row,
    operationId: `op-${id}`,
    reviewDigest: `digest-${id}`,
    decision: "apply",
    reason: "",
  });
  const plan = planRecorded(
    staged({ [A]: { category_id: set("telefono") } }, [
      suggestion("s1", A),
      suggestion("s2", B),
      { id: "arch", kind: "archive", transactionId: B, reason: "" },
      { id: "l1", kind: "link", transactionId: A, invoiceId: "inv-1" },
      { id: "l2", kind: "link", transactionId: A, invoiceId: "inv-2" },
    ]),
    contextOf(business(A), business(B)),
  );
  expect(plan.entries[0]!.blockers).toEqual([
    { kind: "suggestion_and_edits", action: "s1" },
    { kind: "actions_conflict", actions: ["l1", "l2"] },
  ]);
  expect(plan.entries[1]!.blockers).toEqual([
    { kind: "actions_conflict", actions: ["arch", "s2"] },
  ]);
  expect(plan.steps).toEqual([]);
});

test("a model approval waits while the same movement has its own edits, and the edits are not sent first", () => {
  const A = hexId("a");
  const approval: StagedAction = {
    id: "s1",
    kind: "suggestion",
    transactionId: A,
    operationId: "op-s1",
    reviewDigest: "digest-s1",
    decision: "apply",
    reason: "",
  };
  // Its commit expects the movement exactly as the model saw it: a notes
  // edit saved in the bulk, or a description that gives it a new id, would
  // make it refuse.
  for (const edit of [
    { notes: set("Revisado") },
    { description: set("OTRA DESCRIPCION") },
    { counterparty: clear },
  ]) {
    const plan = planRecorded(
      staged({ [A]: edit }, [approval]),
      contextOf(business(A, { counterparty: "ACME" })),
    );
    expect(plan.entries[0]!.blockers).toEqual([
      { kind: "suggestion_and_edits", action: "s1" },
    ]);
    expect(plan.steps).toEqual([]);
    expect(plan.held).toEqual({ rows: [A], drafts: [], actions: ["s1"] });
  }
  // Alone, it is answered.
  const alone = planRecorded(staged({}, [approval]), contextOf(business(A)));
  expect(stepKinds(alone)).toEqual(["answer"]);
});

test("a model approval and a rules apply that names its movement hold each other", () => {
  const A = hexId("a");
  const B = hexId("b");
  const approval: StagedAction = {
    id: "s1",
    kind: "suggestion",
    transactionId: A,
    operationId: "op-s1",
    reviewDigest: "digest-s1",
    decision: "apply",
    reason: "",
  };
  const rules = (id: string, ids: string[]): StagedAction => ({
    id,
    kind: "rule_apply",
    reaffirm: false,
    transactionIds: ids,
  });
  const plan = planRecorded(
    staged({}, [rules("r1", [B, A]), approval]),
    contextOf(business(A), business(B)),
  );
  expect(
    plan.entries.find((entry) => entry.transactionId === A)!.blockers,
  ).toEqual([{ kind: "suggestion_and_rules", action: "s1", rules: ["r1"] }]);
  // Neither runs: the rules could change the movement before the answer,
  // and the answer could change it under the rules.
  expect(plan.steps).toEqual([]);
  expect(plan.held.actions.sort()).toEqual(["r1", "s1"]);
  // Rules that do not name it leave the approval alone.
  const apart = planRecorded(
    staged({}, [rules("r2", [B]), approval]),
    contextOf(business(A), business(B)),
  );
  expect(stepKinds(apart)).toEqual(["action:rule_apply", "answer"]);
  expect(apart.held.actions).toEqual([]);
});

test("reclassifying Mixed movements saves them together: the classification clears the share itself", () => {
  const ids = Array.from({ length: 120 }, (_, at) => hexId(`mx${at}`));
  const rows = contextOf(...ids.map(mixed));
  for (const [kind, category] of [
    ["business", "material_oficina"],
    ["personal", undefined],
  ] as const) {
    const outcome = classifyCells(
      {
        kind,
        ids,
        category,
        check: recordedCheck(EMPTY_CONTENT, rows.rows, {
          ids,
          categories: category ? [category] : [],
        }),
      },
      rows.rows,
    );
    expect(outcome.kind).toBe("staged");
    if (outcome.kind !== "staged") return;
    // The share's clear is staged, so the grid shows no share on the row.
    expect(
      outcome.event.cells.filter((cell) => cell.field === "business_pct"),
    ).toHaveLength(120);
    const content = reduceStage(EMPTY_STAGE, outcome.event).content;
    const plan = planRecorded(content, rows);
    expect(stepKinds(plan)).toEqual(["bulk"]);
    expect(plan.summary).toMatchObject({
      together: 120,
      parts: 1,
      singleClassifications: 0,
      oneAtATime: 0,
      held: 0,
    });
    const bulk = plan.steps[0] as Extract<PlanStep, { kind: "bulk" }>;
    // The row carries the clear as one of the fields it saves, with no
    // cell of its own: a blank cell would mean unchanged.
    expect(bulk.rows[0]!.fields).toContain("business_pct");
    expect(bulk.request.csv_text.split("\n")[0]).toBe(
      kind === "business"
        ? "transaction_id,classification,category_id"
        : "transaction_id,classification",
    );
  }
  // A share cleared on a movement that stays Mixed still needs its own
  // write, and is held for the share Mixed needs.
  const M = hexId("m");
  const kept = planRecorded(
    staged({ [M]: { business_pct: clear } }),
    contextOf(mixed(M)),
  );
  expect(blockersOf(kept, M)).toEqual(["mixed_needs_share"]);
});

test("making a Mixed movement Personal stages the category clear and the plan says the classification write drops it", () => {
  const A = hexId("a");
  const rows = contextOf(mixed(A));
  const outcome = classifyCells(
    {
      kind: "personal",
      ids: [A],
      check: recordedCheck(EMPTY_CONTENT, rows.rows, { ids: [A] }),
    },
    rows.rows,
  );
  expect(outcome.kind).toBe("staged");
  if (outcome.kind !== "staged") return;
  const cleared = outcome.event.cells
    .filter((cell) => cell.value.kind === "clear")
    .map((cell) => cell.field)
    .sort();
  expect(cleared).toEqual(["business_pct", "category_id"]);
  const content = reduceStage(EMPTY_STAGE, outcome.event).content;
  const plan = planRecorded(content, rows);
  // Review lists the category clear on its own.
  expect(plan.entries[0]!.clears.sort()).toEqual(cleared);
  expect(plan.entries[0]!.routes.category_id).toBe("bulk");
  expect(stepKinds(plan)).toEqual(["bulk"]);
  const bulk = plan.steps[0] as Extract<PlanStep, { kind: "bulk" }>;
  // The bulk's blank means unchanged and carries no clear; the write of
  // Personal is what drops the category, so the row names the field it
  // drops and no column.
  expect(bulk.rows[0]!.fields).toContain("category_id");
  expect(bulk.request.csv_text.split("\n")[0]).toBe(
    "transaction_id,classification",
  );
});

test("the classification write also carries the clears of what it drops on a Personal movement", () => {
  const A = hexId("a");
  const plan = planRecorded(
    staged({
      [A]: {
        business_classification: set("PERSONAL"),
        category_id: clear,
        usage_ratio_id: clear,
        iva_category: clear,
      },
    }),
    contextOf(business(A, { usage_ratio_id: "ratio-1", iva_category: "x" })),
  );
  // The IVA category is not dropped by the classification: it goes alone.
  expect(stepKinds(plan)).toEqual(["bulk", "classify"]);
  expect(plan.entries[0]!.routes).toEqual({
    business_classification: "bulk",
    category_id: "bulk",
    usage_ratio_id: "bulk",
    iva_category: "classify",
  });
});

test("bulk requests carry the window's language for their row refusals", () => {
  const A = hexId("a");
  const content = staged({ [A]: { notes: set("Revisado") } });
  const worded = planRecorded(content, {
    ...contextOf(business(A)),
    outputLanguage: "hu",
  });
  const bulk = worded.steps[0] as Extract<PlanStep, { kind: "bulk" }>;
  expect(bulk.request.output_language).toBe("hu");
  const plain = planRecorded(content, contextOf(business(A)));
  expect(
    "output_language" in
      (plain.steps[0] as Extract<PlanStep, { kind: "bulk" }>).request,
  ).toBe(false);
});

test("new movements need their five facts and keep their key", () => {
  const ready = newDraft();
  ready.fields = {
    booked_date: "2026-10-21",
    amount: "12.50",
    currency: "EUR",
    direction: "OUTGOING",
    description: "TAXI",
    business_classification: "BUSINESS",
    iva_rate: "0.10",
  };
  const missing = newDraft();
  missing.fields = { amount: "5" };
  const mixedDraft = newDraft();
  mixedDraft.fields = {
    booked_date: "2026-10-21",
    amount: "5",
    currency: "EUR",
    direction: "OUTGOING",
    description: "X",
    business_classification: "MIXED",
  };
  const transfer = newDraft();
  transfer.fields = {
    booked_date: "2026-10-21",
    amount: "5",
    currency: "EUR",
    direction: "INTERNAL_TRANSFER",
    description: "X",
    iva_amount: "1",
  };
  const plan = planRecorded(
    { ...EMPTY_CONTENT, drafts: [ready, missing, mixedDraft, transfer] },
    contextOf(),
  );
  expect(plan.drafts.map((entry) => entry.blockers)).toEqual([
    [],
    [
      servedBlocker("draft_incomplete", [
        "booked_date",
        "currency",
        "direction",
        "description",
      ]),
    ],
    [servedBlocker("mixed_needs_share")],
    [servedBlocker("transfer_with_tax", ["iva_amount"])],
  ]);
  expect(plan.steps).toEqual([
    {
      kind: "add",
      draftKey: ready.key,
      request: {
        booked_date: "2026-10-21",
        amount: "12.5",
        currency: "EUR",
        direction: "OUTGOING",
        description: "TAXI",
        business_classification: "BUSINESS",
        iva_rate: "0.1",
        idempotency_key: ready.idempotencyKey,
      },
    },
  ]);
});

test("the work is ordered: bulk, single classifications, corrections, adds, then actions", () => {
  const ids = ["a", "b", "c", "d", "e", "f"].map(hexId);
  const [A, B, C, D, E, F] = ids as [
    string,
    string,
    string,
    string,
    string,
    string,
  ];
  const draft = newDraft();
  draft.fields = {
    booked_date: "2026-10-21",
    amount: "1",
    currency: "EUR",
    direction: "INCOMING",
    description: "X",
  };
  const plan = planRecorded(
    staged(
      {
        [A]: { description: set("NUEVA"), category_id: set("telefono") },
        [B]: { counterparty_country: set("PT") },
      },
      [
        { id: "rm", kind: "remove", transactionId: E, reason: "" },
        {
          id: "split",
          kind: "split",
          transactionId: D,
          reason: "",
          children: [
            { amount: "10.00", description: "uno" },
            { amount: "26.30", description: "dos" },
          ],
        },
        { id: "arch", kind: "archive", transactionId: C, reason: "" },
        { id: "link", kind: "link", transactionId: A, invoiceId: "inv-1" },
        {
          id: "sug",
          kind: "suggestion",
          transactionId: F,
          operationId: "op",
          reviewDigest: "d",
          decision: "apply",
          reason: "",
        },
      ],
      [draft],
    ),
    contextOf(...ids.map((id) => business(id))),
  );
  expect(stepKinds(plan)).toEqual([
    "bulk",
    "classify",
    "update",
    "add",
    "answer",
    "action:link",
    "action:archive",
    "action:split",
    "action:remove",
  ]);
  const split = plan.steps.find(
    (step) => step.kind === "action" && step.action.kind === "split",
  ) as Extract<PlanStep, { kind: "action" }>;
  expect(split.definition).toBe("ledger.split.manual");
  expect(split.request).toEqual({
    transaction_id: D,
    children: [
      { amount: "10", description: "uno" },
      { amount: "26.3", description: "dos" },
    ],
    reason: "",
  });
  expect(plan.summary).toMatchObject({
    together: 1,
    parts: 1,
    singleClassifications: 1,
    corrections: 1,
    newMovements: 1,
    oneAtATime: 8,
    seconds: 24,
    permanentLinks: 1,
    held: 0,
    actions: { suggestion: 1, link: 1, archive: 1, split: 1, remove: 1 },
  });
});

test("the CSV quotes what the CSV reader would split", () => {
  const rows: BulkRow[] = [
    {
      transactionId: "aa",
      fields: ["notes"],
      cells: {
        transaction_id: "aa",
        classification: "BUSINESS",
        notes: 'Pedido "urgente", ver\nadjunto',
      },
    },
    {
      transactionId: "bb",
      fields: ["category_id"],
      cells: { transaction_id: "bb", classification: "PERSONAL" },
    },
  ];
  expect(bulkCsv(rows)).toBe(
    'transaction_id,classification,notes\naa,BUSINESS,"Pedido ""urgente"", ver\nadjunto"\nbb,PERSONAL,\n',
  );
});

test("the bulk is cut into parts that each fit the host's bound, in order", () => {
  const ids = Array.from({ length: 300 }, (_, at) => hexId(`row${at}`));
  const content = staged(
    Object.fromEntries(
      ids.map((id) => [
        id,
        {
          category_id: set("material_oficina"),
          notes: set("Revisado por la gestoría en octubre"),
        },
      ]),
    ),
  );
  const rows = contextOf(...ids.map((id) => business(id)));
  const bulkOf = (plan: LedgerPlan) =>
    plan.steps.filter(
      (step): step is Extract<PlanStep, { kind: "bulk" }> =>
        step.kind === "bulk",
    );
  // At the relay's own bound the whole bulk is one request.
  const whole = bulkOf(planRecorded(content, rows));
  expect(whole).toHaveLength(1);
  expect(payloadSize(whole[0]!.request)).toBeLessThanOrEqual(
    RELAY_PAYLOAD_LIMIT,
  );
  // At a bound a fraction of it, the parts each fit, in order.
  const limit = 8 * 1024;
  const plan = planRecorded(content, { ...rows, payloadLimit: limit });
  const parts = bulkOf(plan);
  expect(parts.length).toBeGreaterThan(1);
  for (const part of parts) {
    expect(payloadSize(part.request)).toBeLessThanOrEqual(limit);
    expect(part.parts).toBe(parts.length);
  }
  // Each part is as full as the bound allows: one more row would not fit.
  const first = parts[0]!;
  const next = parts[1]!.rows[0]!;
  expect(
    payloadSize({ csv_text: bulkCsv([...first.rows, next]) }),
  ).toBeGreaterThan(limit);
  expect(
    parts.flatMap((part) => part.rows.map((row) => row.transactionId)),
  ).toEqual(ids);
  expect(plan.summary.together).toBe(300);
  expect(plan.summary.parts).toBe(parts.length);
});

test("the bound counts bytes, and a row too large to send alone is held", () => {
  const row = (id: string, notes: string): BulkRow => ({
    transactionId: id,
    fields: ["notes"],
    cells: { transaction_id: id, classification: "BUSINESS", notes },
  });
  const limit = payloadSize({ csv_text: bulkCsv([row("a", "x".repeat(20))]) });
  // Twenty characters of euro signs are sixty bytes.
  const split = splitBulk(
    [row("a", "x".repeat(20)), row("b", "€".repeat(20)), row("c", "y")],
    limit,
  );
  expect(split.parts.map((part) => part.map((r) => r.transactionId))).toEqual([
    ["a"],
    ["c"],
  ]);
  expect(split.tooLarge.map((r) => r.transactionId)).toEqual(["b"]);

  // Quotes are doubled in the CSV and escaped again in its JSON: 4,000 of
  // them are over 16,000 bytes.
  const A = hexId("a");
  const plan = planRecorded(
    staged({ [A]: { notes: set('"'.repeat(4_000)) } }),
    {
      ...contextOf(business(A)),
      payloadLimit: 16_000,
    },
  );
  expect(blockersOf(plan, A)).toEqual(["too_large"]);
  expect(plan.steps).toEqual([]);
});

test("Mixed names the category's configured usage ratio, through the bulk, and says where none is configured", () => {
  // Three filing years, newest first: one with a ratio for fixed lines, one
  // with none, one not read.
  const [configured, unconfigured, notRead] = servedFilingYears
    .slice(-3)
    .reverse();
  if (
    configured === undefined ||
    unconfigured === undefined ||
    notRead === undefined
  )
    throw new Error("the recording serves fewer than three filing years");
  const phone = movement(hexId("r201"), { date: `${configured}-03-02` });
  const old = movement(hexId("r202"), { date: `${unconfigured}-11-20` });
  const unread = movement(hexId("r203"), { date: `${notRead}-06-01` });
  const income = movement(hexId("r204"), { direction: "INCOMING" });
  const rows = contextOf(phone, old, unread, income);
  const ids = [phone, old, unread, income].map(
    (row) => row.transaction.transaction_id,
  );
  const ratios = new Map<number, ReadonlySet<string> | null>([
    [configured, new Set(["telefonia_fija"])],
    [unconfigured, new Set(["suministros_home_office_luz"])],
    [notRead, null],
  ]);
  const check = recordedCheck(EMPTY_CONTENT, rows.rows, {
    ids,
    categories: ["telefonia_fija"],
  });
  expect(
    ratioCoverage(ids, rows.rows, "telefonia_fija", ratios, check),
  ).toEqual({
    staged: 1,
    missing: 1,
    unread: 1,
  });
  const outcome = classifyCells(
    {
      check,
      kind: "mixed",
      ids,
      share: "30",
      category: "telefonia_fija",
      ratios,
    },
    rows.rows,
  );
  expect(outcome.kind).toBe("staged");
  if (outcome.kind !== "staged") return;
  const ratioCells = outcome.event.cells.filter(
    (cell) => cell.field === "usage_ratio_id",
  );
  expect(ratioCells.map((cell) => [cell.id, cell.value])).toEqual([
    [phone.transaction.transaction_id, set("telefonia_fija")],
  ]);
  // The usage ratio goes in the bulk, beside the classification it needs.
  const plan = planRecorded(
    reduceStage(EMPTY_STAGE, outcome.event).content,
    rows,
  );
  const bulk = plan.steps.find(
    (step): step is Extract<PlanStep, { kind: "bulk" }> => step.kind === "bulk",
  )!;
  const [header, ...lines] = bulk.request.csv_text.trim().split("\n");
  const column = header!.split(",").indexOf("usage_ratio_id");
  expect(column).toBeGreaterThan(0);
  const named = lines
    .map((line) => line.split(","))
    .filter((cells) => cells[column] !== "")
    .map((cells) => [cells[0], cells[column]]);
  expect(named).toEqual([[phone.transaction.transaction_id, "telefonia_fija"]]);
  // Without the ratios read, Mixed names none and stages the rest.
  const unseen = classifyCells(
    {
      check,
      kind: "mixed",
      ids,
      share: "30",
      category: "telefonia_fija",
    },
    rows.rows,
  );
  expect(
    unseen.kind === "staged" &&
      unseen.event.cells.some((cell) => cell.field === "usage_ratio_id"),
  ).toBe(false);
});

test("a movement whose sealed state was not read is held, neither sealed nor savable", () => {
  const read = business(hexId("r211"));
  const unread = business(hexId("r212"));
  const sealed = business(hexId("r213"));
  const id = (row: LedgerRow) => row.transaction.transaction_id;
  const content = staged({
    [id(read)]: { notes: set("Read") },
    [id(unread)]: { notes: set("Unread") },
    [id(sealed)]: { notes: set("Sealed") },
  });
  const plan = planRecorded(content, {
    ...contextOf(read, unread, sealed),
    sealed: new Set([id(sealed)]),
    unread: new Set([id(unread), id(sealed)]),
  });
  expect(blockersOf(plan, id(read))).toEqual([]);
  expect(blockersOf(plan, id(unread))).toEqual(["sealed_unread"]);
  // Read as sealed, it is sealed, whatever an older read left unread.
  expect(blockersOf(plan, id(sealed))).toEqual(["sealed"]);
  expect(plan.summary.blockers).toMatchObject({ sealed_unread: 1, sealed: 1 });
  expect(plan.summary.together).toBe(1);
  expect(plan.held.rows.sort()).toEqual([id(unread), id(sealed)].sort());
});
