import { expect, test } from "@playwright/test";
import type { LedgerLlmSuggestion } from "../src/shell/ledgerMovementOperations";
import type { LedgerStagedRowAnswer } from "../src/shell/ledgerMovementCheckContract";
import type { LedgerRow } from "../src/shell/ledger";
import { EMPTY_CONTENT, type StagedContent } from "../src/shell/ledgerStage";
import {
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
  suggestionWrites,
} from "../src/components/ledger/inspector/inspectorModel";
import { sameInspectorContext } from "../src/components/ledger/inspector/inspectorContext";
import { effectiveFacts } from "../src/shell/ledgerStage";
import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { answerPeriods } from "../src/dev/periodRecording";
import { holdLedgerPeriods, ledgerPeriod } from "../src/shell/ledgerPeriods";
import "./support/servedClassifications";
import { hexId, movement } from "./support/ledger";
import { planRecorded, recordedCheck } from "./support/stagedCheck";

// What the movement inspector works out without drawing. No page is
// opened.

const NONE: ReadonlySet<string> = new Set();

/** The recorded answer about every one of `rows` with `content` staged. */
const checkOf = (content: StagedContent, rows: readonly LedgerRow[]) =>
  recordedCheck(
    content,
    new Map(rows.map((row) => [row.transaction.transaction_id, row])),
    { ids: rows.map((row) => row.transaction.transaction_id) },
  );

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
  expect(noneClassified(rows, checkOf(EMPTY_CONTENT, rows))).toBe(true);
  const staged: StagedContent = {
    ...EMPTY_CONTENT,
    rows: {
      [hexId("a")]: {
        business_classification: { kind: "set", value: "BUSINESS" },
      },
    },
  };
  expect(noneClassified(rows, checkOf(staged, rows))).toBe(false);
  // A classification staged to be cleared leaves the movement undecided.
  const stored = [movement(hexId("c"), { business_classification: "MIXED" })];
  expect(noneClassified(stored, checkOf(EMPTY_CONTENT, stored))).toBe(false);
  expect(
    noneClassified(
      stored,
      checkOf(
        {
          ...EMPTY_CONTENT,
          rows: {
            [hexId("c")]: { business_classification: { kind: "clear" } },
          },
        },
        stored,
      ),
    ),
  ).toBe(true);
});

test("set for all skips a movement whose sealed state was not read, and counts it apart", () => {
  const read = movement(hexId("rea"), { business_classification: "BUSINESS" });
  const unread = movement(hexId("unr"), {
    business_classification: "BUSINESS",
  });
  const rows = new Map(
    [read, unread].map((row) => [row.transaction.transaction_id, row]),
  );
  const ids = [...rows.keys()];
  const found = setForAll("notes", "x", ids, rows, {
    check: checkOf(EMPTY_CONTENT, [read, unread]),
    sealed: NONE,
    unread: new Set([unread.transaction.transaction_id]),
    visible: new Set(ids),
  });
  expect(found.cells.map((cell) => cell.id)).toEqual([
    read.transaction.transaction_id,
  ]);
  expect(found.skipped).toEqual({ sealed_unread: 1 });
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
  const context = {
    check: checkOf(EMPTY_CONTENT, [...rows.values()]),
    sealed: NONE,
    visible,
  };
  const found = setForAll(
    "iva_category",
    "domestic_general",
    ids,
    rows,
    context,
  );
  expect(found.cells.map((cell) => cell.id)).toEqual([
    business.transaction.transaction_id,
    personal.transaction.transaction_id,
    pending.transaction.transaction_id,
    hidden.transaction.transaction_id,
  ]);
  expect(found.visible).toBe(3);
  expect(found.hidden).toBe(1);
  expect(found.skipped).toEqual({ transfer: 1, not_active: 1 });

  // A Personal write drops the category, so it is left out of that set alone.
  const category = setForAll(
    "category_id",
    "office_supplies",
    ids,
    rows,
    context,
  );
  expect(category.skipped).toEqual({ personal: 1, transfer: 1, not_active: 1 });
  // A group label is no tax fact: Personal and unclassified rows take it.
  const labels = setForAll("group_label", "Oficina", ids, rows, {
    check: checkOf(EMPTY_CONTENT, [...rows.values()]),
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
      check: checkOf(content, [row]),
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
      check: checkOf(EMPTY_CONTENT, rows),
      sealed: NONE,
      visible: new Set(byId.keys()),
    },
  );
  const content: StagedContent = { ...EMPTY_CONTENT, rows: {} };
  for (const cell of found.cells)
    content.rows[cell.id] = { [cell.field]: cell.value };
  const plan = planRecorded(content, { rows: byId });
  expect(plan.summary.together).toBe(12);
  expect(plan.summary.oneAtATime).toBe(0);
});

test("a lifecycle action waits for the ledger's answer and the seal", () => {
  const offers = (
    ...lifecycle_actions: LedgerStagedRowAnswer["lifecycle_actions"]
  ) => ({ lifecycle_actions }) as LedgerStagedRowAnswer;
  expect(lifecycleTakes("archive", offers("archive"), false)).toBe(true);
  expect(lifecycleTakes("archive", offers("archive"), true)).toBe(false);
  expect(lifecycleTakes("restore", offers("archive"), false)).toBe(false);
  expect(lifecycleTakes("archive", undefined, false)).toBe(false);
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
  const plan = planRecorded(
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
  // The quarters are the ones the backend served for the days, as recorded.
  const probe = (day: string) =>
    recorded.periods.probes.days.find((found) => found.day === day)!;
  const served = answerPeriods("en", {
    days: ["2026-03-31", "2026-04-01", "2026-10-15", "2026-12-31"],
  })!;
  const row = movement(hexId("a"), {
    date: "2026-03-31",
    booked_date: "2026-03-31",
  });
  const crossing = effectiveFacts(row, {
    booked_date: { kind: "set", value: "2026-04-01" },
  });
  const within = effectiveFacts(
    movement(hexId("b"), { date: "2026-10-15", booked_date: "2026-10-15" }),
    { booked_date: { kind: "set", value: "2026-12-31" } },
  );
  // Nothing is named for a day whose quarter is not served.
  expect(quarterMove(row.transaction, crossing)).toBeNull();
  holdLedgerPeriods("en", served);
  try {
    expect(quarterMove(row.transaction, crossing)).toEqual({
      from: ledgerPeriod(probe("2026-03-31").quarterly),
      to: ledgerPeriod(probe("2026-04-01").quarterly),
    });
    expect(
      quarterMove(
        movement(hexId("b"), { date: "2026-10-15", booked_date: "2026-10-15" })
          .transaction,
        within,
      ),
    ).toBeNull();
  } finally {
    holdLedgerPeriods(null, null);
  }
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
