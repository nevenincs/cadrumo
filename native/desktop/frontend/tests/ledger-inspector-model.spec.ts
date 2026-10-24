import { expect, test } from "@playwright/test";
import type { LedgerLlmSuggestion } from "../src/shell/ledger";
import { planApply } from "../src/shell/ledgerPlan";
import { EMPTY_CONTENT, type StagedContent } from "../src/shell/ledgerStage";
import {
  checkSplit,
  commonValue,
  completeCohort,
  currentSection,
  fittingEntries,
  lifecycleTakes,
  needsShare,
  noneClassified,
  quarterMove,
  selectionCounts,
  setForAll,
  splitRemainder,
  suggestionWrites,
} from "../src/components/ledger/inspector/inspectorModel";
import { sameInspectorContext } from "../src/components/ledger/inspector/inspectorContext";
import { effectiveFacts } from "../src/shell/ledgerStage";
import { hexId, movement } from "./support/ledger";

// What the movement inspector works out without drawing. No page is
// opened.

const NONE: ReadonlySet<string> = new Set();

test("the jump index shows every entry that fits and keeps room for More", () => {
  expect(fittingEntries([60, 70, 50, 60, 60], 40, 400, 4)).toBe(5);
  // 60+70+50 with two gaps is 188; with More (40) and its gap, 232 fits in
  // 240, a fourth entry does not.
  expect(fittingEntries([60, 70, 50, 60, 60], 40, 240, 4)).toBe(3);
  expect(fittingEntries([60, 70, 50, 60, 60], 40, 10, 4)).toBe(1);
});

test("the current section is the last one reached, and the last at the end", () => {
  const tops = [
    { id: "classify", top: 0 },
    { id: "documents", top: 400 },
    { id: "invoice", top: 700 },
  ];
  expect(currentSection(tops, { top: 0, height: 300, content: 1200 }, 24)).toBe(
    "classify",
  );
  expect(
    currentSection(tops, { top: 390, height: 300, content: 1200 }, 24),
  ).toBe("documents");
  expect(
    currentSection(tops, { top: 900, height: 300, content: 1200 }, 24),
  ).toBe("invoice");
  expect(currentSection([], { top: 0, height: 1, content: 1 }, 24)).toBeNull();
});

test("a field the selection shares has one value; otherwise it says how many", () => {
  expect(commonValue(["A", "A"])).toEqual({ kind: "one", value: "A" });
  expect(commonValue([null, undefined])).toEqual({ kind: "one", value: null });
  expect(commonValue(["A", null, "B"])).toEqual({ kind: "mixed", count: 3 });
});

test("counts are by classification and by status, most first", () => {
  const rows = [
    movement(hexId("a")),
    movement(hexId("b")),
    movement(hexId("c"), { business_classification: "BUSINESS" }),
  ];
  const counts = selectionCounts(
    rows,
    new Map([[hexId("c"), ["missing_category"]]]),
  );
  expect(counts.classifications).toEqual([
    ["NOT_YET_PROCESSED", 2],
    ["BUSINESS", 1],
  ]);
  expect(counts.statuses).toEqual([
    ["pending", 2],
    ["needs_fixing", 1],
  ]);
});

test("while readiness is not measured, a reviewed movement counts as not measured, never done", () => {
  const rows = [
    movement(hexId("a")),
    movement(hexId("b"), { business_classification: "BUSINESS" }),
    movement(hexId("c"), { business_classification: "PERSONAL" }),
  ];
  expect(selectionCounts(rows, null).statuses).toEqual([
    ["unmeasured", 2],
    ["pending", 1],
  ]);
  // Measured with nothing found, the same movements are done.
  expect(selectionCounts(rows, new Map()).statuses).toEqual([
    ["done", 2],
    ["pending", 1],
  ]);
});

test("the selection's tax fields wait for a classification, stored or staged", () => {
  const rows = [movement(hexId("a")), movement(hexId("b"))];
  expect(noneClassified(rows, EMPTY_CONTENT)).toBe(true);
  const staged: StagedContent = {
    ...EMPTY_CONTENT,
    rows: {
      [hexId("a")]: {
        business_classification: { kind: "set", value: "BUSINESS" },
      },
    },
  };
  expect(noneClassified(rows, staged)).toBe(false);
  // A classification staged to be cleared leaves the movement undecided.
  const stored = [movement(hexId("c"), { business_classification: "MIXED" })];
  expect(noneClassified(stored, EMPTY_CONTENT)).toBe(false);
  expect(
    noneClassified(stored, {
      ...EMPTY_CONTENT,
      rows: { [hexId("c")]: { business_classification: { kind: "clear" } } },
    }),
  ).toBe(true);
});

test("set for all skips what cannot take it, and counts hidden movements apart", () => {
  const business = movement(hexId("biz"), {
    business_classification: "BUSINESS",
  });
  const personal = movement(hexId("per"), {
    business_classification: "PERSONAL",
  });
  const transfer = movement(hexId("tra"), {
    business_classification: "BUSINESS",
    direction: "INTERNAL_TRANSFER",
  });
  const archived = movement(hexId("arc"), {
    business_classification: "BUSINESS",
    lifecycle_state: "ARCHIVED",
  });
  const pending = movement(hexId("pen"));
  const hidden = movement(hexId("hid"), {
    business_classification: "MIXED",
    business_pct: "0.5",
  });
  const rows = new Map(
    [business, personal, transfer, archived, pending, hidden].map((row) => [
      row.transaction.transaction_id,
      row,
    ]),
  );
  const ids = [...rows.keys()];
  const visible = new Set(
    ids.filter((id) => id !== hidden.transaction.transaction_id),
  );
  const found = setForAll("iva_category", "domestic_general", ids, rows, {
    content: EMPTY_CONTENT,
    sealed: NONE,
    visible,
  });
  expect(found.cells.map((cell) => cell.id)).toEqual([
    business.transaction.transaction_id,
    hidden.transaction.transaction_id,
  ]);
  expect(found.visible).toBe(1);
  expect(found.hidden).toBe(1);
  expect(found.skipped).toEqual({
    personal: 1,
    transfer: 1,
    not_active: 1,
    unclassified: 1,
  });
  // A group label is no tax fact: Personal and unclassified rows take it.
  const labels = setForAll("group_label", "Oficina", ids, rows, {
    content: EMPTY_CONTENT,
    sealed: new Set([business.transaction.transaction_id]),
    visible,
  });
  expect(labels.skipped).toEqual({ sealed: 1, not_active: 1 });
  expect(labels.cells).toHaveLength(4);
});

test("set for all judges a movement as staged: a staged Personal skips tax fields", () => {
  const row = movement(hexId("biz"), { business_classification: "BUSINESS" });
  const id = row.transaction.transaction_id;
  const content: StagedContent = {
    ...EMPTY_CONTENT,
    rows: {
      [id]: { business_classification: { kind: "set", value: "PERSONAL" } },
    },
  };
  const found = setForAll(
    "category_id",
    "material_oficina",
    [id],
    new Map([[id, row]]),
    {
      content,
      sealed: NONE,
      visible: new Set([id]),
    },
  );
  expect(found.cells).toEqual([]);
  expect(found.skipped).toEqual({ personal: 1 });
});

test("set-for-all cells plan as one bulk save", () => {
  const rows = Array.from({ length: 12 }, (_, at) =>
    movement(hexId(`r${at}`), { business_classification: "BUSINESS" }),
  );
  const byId = new Map(
    rows.map((row) => [row.transaction.transaction_id, row]),
  );
  const found = setForAll(
    "category_id",
    "material_oficina",
    [...byId.keys()],
    byId,
    {
      content: EMPTY_CONTENT,
      sealed: NONE,
      visible: new Set(byId.keys()),
    },
  );
  const content: StagedContent = { ...EMPTY_CONTENT, rows: {} };
  for (const cell of found.cells)
    content.rows[cell.id] = { [cell.field]: cell.value };
  const plan = planApply(content, { rows: byId });
  expect(plan.summary.together).toBe(12);
  expect(plan.summary.oneAtATime).toBe(0);
});

test("a lifecycle action is offered only where it can run", () => {
  const active = movement(hexId("a"));
  const archived = movement(hexId("b"), { lifecycle_state: "ARCHIVED" });
  const excluded = movement(hexId("c"), {
    business_classification: "REVIEWED_EXCLUDED",
  });
  expect(lifecycleTakes("archive", active, NONE)).toBe(true);
  expect(lifecycleTakes("archive", active, new Set([hexId("a")]))).toBe(false);
  expect(lifecycleTakes("restore", active, NONE)).toBe(false);
  expect(lifecycleTakes("restore", archived, NONE)).toBe(true);
  expect(lifecycleTakes("stash", archived, NONE)).toBe(false);
  expect(lifecycleTakes("exclude", excluded, NONE)).toBe(false);
});

test("a merge needs every active part of the split, and nothing else", () => {
  const parent = movement(hexId("p"), { lifecycle_state: "SPLIT" });
  const one = movement(hexId("x"));
  const two = movement(hexId("y"));
  const rows = new Map(
    [parent, one, two].map((row) => [row.transaction.transaction_id, row]),
  );
  const cohort = [hexId("x"), hexId("p"), hexId("y"), hexId("old")];
  expect(completeCohort([hexId("x"), hexId("y")], cohort, rows)).toBe(true);
  expect(completeCohort([hexId("x")], cohort, rows)).toBe(false);
  expect(
    completeCohort([hexId("x"), hexId("y"), hexId("p")], cohort, rows),
  ).toBe(false);
  expect(completeCohort([hexId("x")], [hexId("x")], rows)).toBe(false);
});

test("a split's last part takes what the others leave, in its shortest form", () => {
  expect(splitRemainder("59.99", ["20"])).toBe("39.99");
  expect(splitRemainder("100", ["40.5", "9.5"])).toBe("50");
  expect(splitRemainder("10.20", ["10.10"])).toBe("0.1");
  expect(splitRemainder("10", ["10"])).toBeNull();
  expect(splitRemainder("10", ["11"])).toBeNull();
  expect(splitRemainder("10", ["1.000"])).toBeNull();
  expect(splitRemainder("10", [""])).toBeNull();
});

test("a split is refused unless its parts add up exactly and differ", () => {
  expect(
    checkSplit("59.99", [
      { amount: "20.00", description: " Licencia " },
      { amount: "39.99", description: "Soporte" },
    ]),
  ).toEqual({
    ok: true,
    children: [
      { amount: "20", description: "Licencia" },
      { amount: "39.99", description: "Soporte" },
    ],
  });
  expect(checkSplit("10", [{ amount: "10", description: "a" }])).toEqual({
    ok: false,
    problem: { kind: "count" },
  });
  expect(
    checkSplit("10", [
      { amount: "6", description: "a" },
      { amount: "5", description: "b" },
    ]),
  ).toEqual({
    ok: false,
    problem: { kind: "sum", difference: "1", over: true },
  });
  expect(
    checkSplit("10", [
      { amount: "5", description: "a" },
      { amount: "4.5", description: "b" },
    ]),
  ).toEqual({
    ok: false,
    problem: { kind: "sum", difference: "0.5", over: false },
  });
  expect(
    checkSplit("10", [
      { amount: "5", description: "a" },
      { amount: "5", description: "a" },
    ]),
  ).toEqual({ ok: false, problem: { kind: "duplicate", index: 1 } });
  expect(
    checkSplit("10", [
      { amount: "5", description: "a" },
      { amount: "5", description: "  " },
    ]),
  ).toEqual({ ok: false, problem: { kind: "description", index: 1 } });
  expect(
    checkSplit("10", [
      { amount: "0", description: "a" },
      { amount: "10", description: "b" },
    ]),
  ).toEqual({ ok: false, problem: { kind: "amount", index: 0 } });
});

const suggestion = (
  extra: Partial<LedgerLlmSuggestion["suggestion"]>,
): LedgerLlmSuggestion["suggestion"] => ({
  kind: "classification",
  transaction_id: hexId("a"),
  provenance: "llm:local-medium",
  reason: "",
  evidence_id: null,
  classification: "BUSINESS",
  category: "material_oficina",
  confidence: "0.82",
  multiple_components: false,
  business_pct: null,
  iva_category: "domestic_general",
  iva_rate: null,
  taxable_base: null,
  iva_amount: null,
  rate_derivable: false,
  derivation_note: "",
  evidence_advisory: "",
  parent_amount: null,
  children: [],
  ...extra,
});

test("an approval lists what it writes, the registry's figures marked as worked out", () => {
  expect(suggestionWrites(suggestion({}))).toEqual([
    { field: "business_classification", value: "BUSINESS" },
    { field: "category_id", value: "material_oficina" },
    { field: "iva_category", value: "domestic_general" },
  ]);
  expect(
    suggestionWrites(
      suggestion({
        kind: "saturated",
        classification: "MIXED",
        business_pct: "0.3",
        rate_derivable: true,
        iva_rate: "0.21",
        taxable_base: "35",
        iva_amount: "7.35",
      }),
    ),
  ).toEqual([
    { field: "business_classification", value: "MIXED" },
    { field: "business_pct", value: "0.3" },
    { field: "category_id", value: "material_oficina" },
    { field: "iva_category", value: "domestic_general" },
    { field: "taxable_base", value: "35", derived: true },
    { field: "iva_rate", value: "0.21", derived: true },
    { field: "iva_amount", value: "7.35", derived: true },
  ]);
  expect(suggestionWrites(suggestion({ kind: "split" }))).toEqual([]);
});

test("a Mixed proposal with no share is held", () => {
  expect(needsShare(suggestion({ classification: "MIXED" }))).toBe(true);
  expect(
    needsShare(suggestion({ classification: "MIXED", business_pct: "0.5" })),
  ).toBe(false);
  expect(needsShare(suggestion({}))).toBe(false);
  // The plan holds the same approval back.
  const row = movement(hexId("a"));
  const plan = planApply(
    {
      ...EMPTY_CONTENT,
      actions: [
        {
          id: "suggestion:a",
          kind: "suggestion",
          transactionId: hexId("a"),
          operationId: "op",
          reviewDigest: "digest",
          decision: "apply",
          reason: "",
          writes: suggestionWrites(suggestion({ classification: "MIXED" })),
        },
      ],
    },
    { rows: new Map([[hexId("a"), row]]) },
  );
  expect(plan.summary.blockers.suggestion_needs_share).toBe(1);
});

test("a date that crosses a quarter is named, one within it is not", () => {
  const row = movement(hexId("a"), {
    date: "2026-09-30",
    booked_date: "2026-09-30",
  });
  const facts = effectiveFacts(row, {
    booked_date: { kind: "set", value: "2026-10-01" },
  });
  expect(quarterMove(row.transaction, facts)).toEqual({
    from: { year: 2026, code: "3T" },
    to: { year: 2026, code: "4T" },
  });
  const same = effectiveFacts(row, {
    booked_date: { kind: "set", value: "2026-09-01" },
  });
  expect(quarterMove(row.transaction, same)).toBeNull();
});

test("the inspector hears of a section only when what it shows changed", () => {
  const base = {
    visible: new Set(["a", "b"]),
    partial: false,
    checked: true,
    issues: new Map([["a", ["missing_category"]]]),
    accounts: null,
    duplicates: new Set(["a"]),
    classify: () => undefined,
    focusActive: () => undefined,
    showHidden: () => undefined,
  };
  // A duplicate marked or cleared is news.
  expect(
    sameInspectorContext(base, { ...base, duplicates: new Set<string>() }),
  ).toBe(false);
  expect(
    sameInspectorContext(base, {
      ...base,
      visible: new Set(["b", "a"]),
      issues: new Map([["a", ["missing_category"]]]),
      classify: () => undefined,
    }),
  ).toBe(true);
  expect(sameInspectorContext(base, { ...base, visible: new Set(["a"]) })).toBe(
    false,
  );
  expect(
    sameInspectorContext(base, {
      ...base,
      issues: new Map([["a", ["missing_iva_rate"]]]),
    }),
  ).toBe(false);
  expect(sameInspectorContext(base, { ...base, partial: true })).toBe(false);
  // Readiness measured or not is news: the inspector draws "done" only once
  // it is.
  expect(sameInspectorContext(base, { ...base, checked: false })).toBe(false);
});
