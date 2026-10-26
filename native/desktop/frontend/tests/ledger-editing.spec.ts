import { expect, test } from "@playwright/test";
import {
  NO_ACCOUNT,
  askedConflicts,
  changeGroups,
  clearRefusal,
  columnField,
  copyCell,
  decimalDistance,
  draftField,
  heldUnits,
  linkMismatches,
  linksReady,
  lockReason,
  outcomeTally,
  parseCell,
  parseTsv,
  planFill,
  planPaste,
  rowCells,
  stageTally,
  type ChoiceLabels,
  type EditSubject,
} from "../src/components/ledger/editing/editingModel";
import type { CatalogueInvoice, LedgerRow } from "../src/shell/ledger";
import type { StepReport } from "../src/shell/ledgerApply";
import { planApply } from "../src/shell/ledgerPlan";
import {
  EMPTY_STAGE,
  newDraft,
  reduceStage,
  type StagedAction,
  type StagedContent,
} from "../src/shell/ledgerStage";
import { hexId, movement } from "./support/ledger";

// What editing the movements grid makes of typed, pasted and filled text,
// and how the page counts and reviews what is staged. No page is opened.

const A = hexId("a");
const B = hexId("b");
const C = hexId("c");

const labels: ChoiceLabels & { mixedShare: (share: string) => string } = {
  direction: (token) =>
    ({
      INCOMING: "Entrada",
      OUTGOING: "Salida",
      INTERNAL_TRANSFER: "Traspaso",
    })[token] ?? token,
  classification: (token) =>
    ({ BUSINESS: "Profesional", PERSONAL: "Personal", MIXED: "Mixto" })[
      token
    ] ?? token,
  category: (id) => (id === "material_oficina" ? "Material de oficina" : id),
  ivaCategory: (id) => id,
  irpfCategory: (id) => id,
  account: (id) => (id === "acc-01" ? "Cuenta del estudio" : id),
  accounts: ["acc-01", "acc-02"],
  noAccount: "Sin cuenta",
  mixedShare: (share) => `Mixto ${share}`,
};
const rowSubject = (row: LedgerRow, sealed = false): EditSubject => ({
  kind: "row",
  row,
  changes: undefined,
  sealed,
});

test("each column stages the field it shows, and a new movement the field it fills", () => {
  const booked = movement(A);
  const valued = movement(B, { value_date: "2026-10-07" });
  expect(columnField("date", booked)).toBe("booked_date");
  expect(columnField("date", valued)).toBe("value_date");
  expect(columnField("category", booked)).toBe("category_id");
  expect(columnField("classification", booked)).toBe("business_classification");
  expect(columnField("account", booked)).toBe("own_account_id");
  expect(columnField("status", booked)).toBeNull();
  expect(draftField("date")).toBe("booked_date");
  expect(draftField("category")).toBe("category_id");
  // An add takes no group label.
  expect(draftField("group_label")).toBeNull();
});

test("typed values go through the product's one grammar, and refusals echo them", () => {
  expect(parseCell("amount", "amount", "1.234,50", labels)).toEqual({
    kind: "refused",
    refusal: { key: "grouping", raw: "1.234,50", suggestion: "1234.50" },
  });
  expect(parseCell("amount", "amount", "40.50", labels)).toEqual({
    kind: "value",
    value: { value: "40.5" },
  });
  expect(parseCell("percent", "iva_rate", "0.21", labels)).toMatchObject({
    kind: "refused",
    refusal: { key: "percent_as_fraction", suggestion: "21" },
  });
  expect(parseCell("percent", "iva_rate", "21", labels)).toEqual({
    kind: "value",
    value: { value: "0.21" },
  });
  expect(parseCell("date", "booked_date", "05/10/2026", labels)).toMatchObject({
    kind: "refused",
    refusal: { key: "date_not_iso", suggestion: "2026-10-05" },
  });
  expect(parseCell("text", "description", "uno\tdos", labels)).toMatchObject({
    kind: "refused",
    refusal: { key: "line_break" },
  });
  // A choice is read by its token or its label, accents aside.
  expect(parseCell("direction", "direction", "salida", labels)).toEqual({
    kind: "value",
    value: { value: "OUTGOING" },
  });
  expect(parseCell("direction", "direction", "OUT", labels)).toEqual({
    kind: "value",
    value: { value: "OUTGOING" },
  });
  expect(
    parseCell("category", "category_id", "material de oficina", labels),
  ).toEqual({ kind: "value", value: { value: "material_oficina" } });
  expect(parseCell("category", "category_id", "Café", labels)).toMatchObject({
    kind: "refused",
    refusal: { key: "unknown_choice" },
  });
  // Mixed is read with its share, as copying writes it.
  expect(
    parseCell("classification", "business_classification", "Mixto 50%", labels),
  ).toEqual({
    kind: "value",
    value: { value: "MIXED", share: "0.5" },
  });
  expect(parseCell("account", "own_account_id", "Sin cuenta", labels)).toEqual({
    kind: "value",
    value: { value: NO_ACCOUNT },
  });
  expect(parseCell("amount", "amount", "  ", labels)).toEqual({
    kind: "empty",
  });
});

test("what cannot be cleared says so, and No account is a clear", () => {
  expect(clearRefusal("amount")).toEqual({ key: "required", raw: "" });
  expect(clearRefusal("notes")).toEqual({ key: "cannot_clear", raw: "" });
  expect(clearRefusal("business_classification")).toMatchObject({
    key: "cannot_clear",
  });
  expect(clearRefusal("category_id")).toBeNull();
  const row = movement(A, {}, null, "acc-01");
  expect(rowCells(A, row, "own_account_id", { value: NO_ACCOUNT })).toEqual([
    {
      id: A,
      field: "own_account_id",
      value: { kind: "clear" },
      stored: "acc-01",
    },
  ]);
  // Leaving Mixed clears the stored share with it.
  const mixed = movement(B, {
    business_classification: "MIXED",
    business_pct: "0.3",
  });
  expect(
    rowCells(B, mixed, "business_classification", { value: "PERSONAL" }),
  ).toEqual([
    {
      id: B,
      field: "business_classification",
      value: { kind: "set", value: "PERSONAL" },
      stored: "MIXED",
    },
    { id: B, field: "business_pct", value: { kind: "clear" }, stored: "0.3" },
  ]);
});

test("a cell takes no edit where nothing could save it, with the reason", () => {
  const transfer = movement(A, { direction: "INTERNAL_TRANSFER" });
  expect(lockReason("category", rowSubject(transfer))).toEqual({
    kind: "transfer",
  });
  expect(lockReason("description", rowSubject(transfer))).toBeNull();
  const archived = movement(B, { lifecycle_state: "ARCHIVED" });
  expect(lockReason("notes", rowSubject(archived))).toEqual({
    kind: "not_active",
    lifecycle: "ARCHIVED",
  });
  expect(lockReason("notes", rowSubject(movement(C), true))).toEqual({
    kind: "sealed",
  });
  expect(lockReason("eur", rowSubject(movement(C)))).toEqual({
    kind: "derived",
  });
  const draft = newDraft();
  expect(lockReason("group_label", { kind: "draft", draft })).toEqual({
    kind: "after_add",
  });
  // The direction it will have decides: a staged transfer locks too.
  expect(
    lockReason("iva_rate", {
      kind: "row",
      row: movement(C),
      changes: { direction: { kind: "set", value: "INTERNAL_TRANSFER" } },
      sealed: false,
    }),
  ).toEqual({ kind: "transfer" });
});

test("tab-separated text keeps quoted cells and refuses an open quote", () => {
  expect(parseTsv("a\tb\r\nc\td\n")).toEqual({
    kind: "cells",
    rows: [
      ["a", "b"],
      ["c", "d"],
    ],
  });
  expect(parseTsv('"dice ""hola""\tya"\tx')).toEqual({
    kind: "cells",
    rows: [['dice "hola"\tya', "x"]],
  });
  expect(parseTsv('"sin cerrar\tx')).toEqual({
    kind: "refused",
    reason: "unclosed_quote",
  });
});

test("a paste stages cell by cell, leaves blanks, drops what falls past the grid and asks first", () => {
  const rows = new Map([
    [A, movement(A)],
    [B, movement(B)],
    [C, movement(C, { lifecycle_state: "ARCHIVED" })],
  ]);
  const subjectOf = (key: string) => {
    const row = rows.get(key);
    return row ? rowSubject(row) : undefined;
  };
  const order = {
    rows: [A, B, C],
    columns: ["description", "counterparty", "amount"] as const,
  };
  const plan = planPaste(
    "Uno\tTrazo SL\n\tOtra SL\nTres\t\nCuatro",
    { key: A, column: "counterparty" },
    null,
    { rows: order.rows, columns: [...order.columns] },
    subjectOf,
    labels,
  );
  if ("kind" in plan) throw new Error("refused");
  // From the counterparty: the first value and the amount column.
  expect(plan.stage.map((cell) => [cell.id, cell.field])).toEqual([
    [A, "counterparty"],
  ]);
  expect(plan.refused.map((cell) => [cell.key, cell.refusal.key])).toEqual([
    [A, "not_a_number"],
    [B, "not_a_number"],
    [C, "locked"],
  ]);
  expect(plan.blanks).toBe(2);
  expect(plan.dropped).toBe(1);
  expect(plan.needsPreview).toBe(true);
  // One value pasted over a range fills every cell of it.
  const fill = planPaste(
    "Oficina",
    { key: A, column: "group_label" },
    { rows: [A, B], columns: ["group_label"] },
    { rows: [A, B], columns: ["group_label"] },
    subjectOf,
    labels,
  );
  if ("kind" in fill) throw new Error("refused");
  expect(fill.stage.map((cell) => cell.id)).toEqual([A, B]);
  // An identity cell is shown before it is pasted, and counted.
  const identity = planPaste(
    "NUEVA DESCRIPCION",
    { key: A, column: "description" },
    null,
    { rows: [A], columns: ["description"] },
    subjectOf,
    labels,
  );
  if ("kind" in identity) throw new Error("refused");
  expect(identity.needsPreview).toBe(true);
  expect(identity.newIdentity).toBe(1);
});

test("fill down carries the top value as it would be saved, with a Mixed share", () => {
  const top = movement(A, {
    business_classification: "MIXED",
    business_pct: "0.4",
  });
  const rows = new Map([
    [A, top],
    [B, movement(B)],
    [C, movement(C, { direction: "INTERNAL_TRANSFER" })],
  ]);
  const subjectOf = (key: string) => rowSubject(rows.get(key)!);
  expect(
    planFill({ rows: [A], columns: ["classification"] }, subjectOf),
  ).toEqual({
    kind: "too_short",
  });
  const plan = planFill(
    { rows: [A, B, C], columns: ["classification", "category"] },
    subjectOf,
  );
  if (plan.kind !== "fill") throw new Error("too short");
  expect(plan.stage.map((cell) => [cell.id, cell.field, cell.value])).toEqual([
    [B, "business_classification", { kind: "set", value: "MIXED" }],
    [B, "business_pct", { kind: "set", value: "0.4" }],
    [C, "business_classification", { kind: "set", value: "MIXED" }],
    [C, "business_pct", { kind: "set", value: "0.4" }],
  ]);
  // The empty top category fills nothing; the transfer's category is locked.
  expect(plan.kept).toBe(2);
});

test("copying writes what pasting reads back", () => {
  const row = movement(A, {
    business_classification: "MIXED",
    business_pct: "0.5",
    iva_rate: "0.21",
    amount: "36.3",
  });
  const subject = rowSubject(row);
  expect(copyCell(subject, "classification", labels)).toBe("Mixto 50%");
  expect(copyCell(subject, "iva_rate", labels)).toBe("21%");
  expect(copyCell(subject, "amount", labels)).toBe("36.30");
  expect(copyCell(subject, "account", labels)).toBe("Sin cuenta");
  expect(
    parseCell("classification", "business_classification", "Mixto 50%", labels),
  ).toMatchObject({ value: { value: "MIXED", share: "0.5" } });
});

test("one counting unit: movements changed, actions and new movements; held back in the same unit", () => {
  const link: StagedAction = {
    id: "l",
    kind: "link",
    transactionId: B,
    invoiceId: "inv",
  };
  let state = reduceStage(EMPTY_STAGE, {
    type: "stage",
    label: "set",
    cells: [
      {
        id: A,
        field: "notes",
        value: { kind: "set", value: "x" },
        stored: null,
      },
      {
        id: A,
        field: "group_label",
        value: { kind: "set", value: "g" },
        stored: null,
      },
      {
        id: C,
        field: "category_id",
        value: { kind: "set", value: "telefono" },
        stored: null,
      },
    ],
  });
  state = reduceStage(state, { type: "stage_action", action: link });
  state = reduceStage(state, { type: "add_draft", draft: newDraft() });
  const tally = stageTally(state.content);
  expect(tally).toMatchObject({
    units: 4,
    movements: 2,
    edits: 3,
    drafts: 1,
    actions: 1,
  });
  const plan = planApply(state.content, {
    rows: new Map([
      [A, movement(A, { business_classification: "BUSINESS" })],
      [B, movement(B)],
      [C, movement(C)],
    ]),
  });
  // C needs a classification and the draft its facts: two held.
  expect(heldUnits(state.content, plan)).toBe(2);
});

test("the summary groups changes by field, stored value and staged value", () => {
  const content: StagedContent = {
    rows: {
      [A]: { category_id: { kind: "set", value: "telefono" } },
      [B]: { category_id: { kind: "set", value: "telefono" } },
      [C]: { category_id: { kind: "clear" } },
    },
    drafts: [],
    actions: [],
  };
  const groups = changeGroups(
    content,
    new Map([
      [A, movement(A)],
      [B, movement(B)],
      [C, movement(C, { category_id: "material_oficina" })],
    ]),
  );
  expect(groups.map((group) => [group.field, group.from, group.ids])).toEqual([
    ["category_id", null, [A, B]],
    ["category_id", "material_oficina", [C]],
  ]);
});

test("a change elsewhere asks only when it touched a field the person changed", () => {
  const before = movement(A, { counterparty: "Uno", notes: "" });
  const content: StagedContent = {
    rows: { [A]: { counterparty: { kind: "set", value: "Mío" } } },
    drafts: [],
    actions: [],
  };
  const otherField = movement(A, { counterparty: "Uno", notes: "nota" });
  expect(
    askedConflicts(
      [{ kind: "changed", transactionId: A, before, after: otherField }],
      content,
    ),
  ).toEqual([]);
  const sameField = movement(A, { counterparty: "Suyo" });
  expect(
    askedConflicts(
      [{ kind: "changed", transactionId: A, before, after: sameField }],
      content,
    ),
  ).toEqual([
    {
      kind: "changed",
      transactionId: A,
      before,
      after: sameField,
      fields: ["counterparty"],
    },
  ]);
  // The same amount written another way is no change.
  const amounts: StagedContent = {
    rows: { [A]: { amount: { kind: "set", value: "12" } } },
    drafts: [],
    actions: [],
  };
  expect(
    askedConflicts(
      [
        {
          kind: "changed",
          transactionId: A,
          before: movement(A, { amount: "36.30" }),
          after: movement(A, { amount: "36.3" }),
        },
      ],
      amounts,
    ),
  ).toEqual([]);
});

test("a permanent link names how its sides differ and needs a second tick for it", () => {
  const row = movement(A, {
    amount: "72.60",
    counterparty: "Arroyo Asesores SL",
  });
  const invoice = {
    invoice_id: "inv",
    invoice_number: "GT-2026-0917",
    grand_total: { decimal: "1548.80" },
    currency: "EUR",
    counterparty_name: "Imprenta Gráficas Turia SL",
    linked_transaction_ids: [B],
  } as unknown as CatalogueInvoice;
  const mismatches = linkMismatches(row, invoice);
  expect(mismatches).toEqual([
    { kind: "amount", difference: "1476.2" },
    { kind: "counterparty" },
    { kind: "linked_elsewhere", count: 1 },
  ]);
  const same = linkMismatches(
    movement(A, { amount: "1548.8", counterparty: "Imprenta Graficas Turia" }),
    { ...invoice, linked_transaction_ids: [A] },
  );
  expect(same).toEqual([]);
  // A movement in another currency differs in its currency, not by an
  // amount: the two numbers have no difference to state.
  const foreign = linkMismatches(
    movement(A, {
      amount: "1548.80",
      currency: "USD",
      counterparty: "Imprenta Graficas Turia",
    }),
    { ...invoice, linked_transaction_ids: [A] },
  );
  expect(foreign).toEqual([
    { kind: "currency", movement: "USD", invoice: "EUR" },
  ]);
  expect(
    linksReady([{ id: "f", mismatches: foreign }], {
      f: { sure: true, differ: false },
    }),
  ).toBe(false);
  expect(decimalDistance("10", "12.5")).toBe("2.5");
  const links = [{ id: "l", mismatches }];
  expect(linksReady(links, {})).toBe(false);
  expect(linksReady(links, { l: { sure: true, differ: false } })).toBe(false);
  expect(linksReady(links, { l: { sure: true, differ: true } })).toBe(true);
  expect(
    linksReady([{ id: "m", mismatches: [] }], {
      m: { sure: true, differ: false },
    }),
  ).toBe(true);
});

test("a Mixed model approval without a share is held, never saved so", () => {
  const approval = (
    writes: {
      field: "business_classification" | "business_pct";
      value: string | null;
    }[],
  ): StagedAction => ({
    id: "s",
    kind: "suggestion",
    transactionId: A,
    operationId: "op",
    reviewDigest: "d",
    decision: "apply",
    reason: "",
    writes,
  });
  const rows = new Map([[A, movement(A)]]);
  const held = planApply(
    {
      rows: {},
      drafts: [],
      actions: [
        approval([{ field: "business_classification", value: "MIXED" }]),
      ],
    },
    { rows },
  );
  expect(held.entries[0]!.blockers).toEqual([
    { kind: "suggestion_needs_share", action: "s" },
  ]);
  expect(held.steps).toEqual([]);
  const sent = planApply(
    {
      rows: {},
      drafts: [],
      actions: [
        approval([
          { field: "business_classification", value: "MIXED" },
          { field: "business_pct", value: "0.5" },
        ]),
      ],
    },
    { rows },
  );
  expect(sent.steps.map((step) => step.kind)).toEqual(["answer"]);
});

test("outcomes are tallied per movement for a bulk part and per write otherwise", () => {
  const reports = [
    {
      index: 0,
      step: { kind: "bulk" } as never,
      outcome: { kind: "settled" },
      rows: [
        { transactionId: A, outcome: { kind: "settled" } },
        {
          transactionId: B,
          outcome: {
            kind: "refused",
            reason: null,
            messages: [],
            detail: null,
          },
        },
      ],
    },
    {
      index: 1,
      step: { kind: "update" } as never,
      outcome: { kind: "unknown", operationId: "op" },
      rows: [
        { transactionId: C, outcome: { kind: "unknown", operationId: "op" } },
      ],
    },
  ] as StepReport[];
  expect(outcomeTally(reports)).toEqual({ settled: 1, refused: 1, unknown: 1 });
});

test("undo history follows a movement's new id after an apply", () => {
  let state = reduceStage(EMPTY_STAGE, {
    type: "stage",
    label: "set",
    cells: [
      {
        id: A,
        field: "notes",
        value: { kind: "set", value: "x" },
        stored: null,
      },
    ],
  });
  state = reduceStage(state, {
    type: "stage",
    label: "set",
    cells: [
      {
        id: A,
        field: "group_label",
        value: { kind: "set", value: "g" },
        stored: null,
      },
    ],
  });
  state = reduceStage(state, { type: "rekey", from: A, to: B });
  expect(Object.keys(state.content.rows)).toEqual([B]);
  state = reduceStage(state, { type: "undo" });
  expect(state.content.rows).toEqual({
    [B]: { notes: { kind: "set", value: "x" } },
  });
});
