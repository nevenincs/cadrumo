import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  COLUMN_IDS,
  NO_FILTERS,
  columnLayout,
  currencySums,
  groupRows,
  keepsRow,
  matchesSearch,
  moveColumn,
  normalisedDescription,
  presetHidden,
  presetOf,
  readinessSets,
  serverFilters,
  shownColumns,
  sortRows,
  dateWidth,
  statusMarks,
  statusWidth,
  type SortLabels,
} from "../src/components/ledger/movements/movementsModel";
import { statusWord } from "../src/components/ledger/movements/movementWords";
import type {
  LedgerPreflightReason,
  LedgerRow,
  LedgerStatusResult,
} from "../src/shell/ledger";
import {
  categoryCells,
  categorySplit,
  classifyAvailability,
  classifyCells,
  takesExpenseCategory,
} from "../src/shell/ledgerCommands";
import {
  IRPF_CATEGORIES,
  IVA_CATEGORIES,
  SHARE_CATEGORY_FAMILIES,
  SPENDING_CATEGORIES,
  SPENDING_CATEGORY_FAMILIES,
  USAGE_RATIO_CATEGORIES,
} from "../src/shell/ledgerVocabulary";
import type { StagedContent } from "../src/shell/ledgerStage";
import type { ReadinessSnapshot } from "../src/shell/ledgerWindow";
import { hexId, movement } from "./support/ledger";

// What the movements grid makes of a window, and the one classify command.
// No page is opened.

const status = (
  issues: { transaction_id: string; reason: string }[],
): LedgerStatusResult => ({
  profile_id: "p",
  period: null,
  business_income_total: "0",
  business_expense_total: "0",
  business_net_total: "0",
  total_count: 0,
  active_count: 0,
  archived_count: 0,
  stashed_count: 0,
  split_count: 0,
  // The product's own count spans the whole ledger: the strip must not use it.
  pending_review_count: 999,
  reviewed_count: 0,
  skipped_count: 0,
  checked_transaction_count: 0,
  readiness_issue_count: issues.length,
  unconverted_currency_count: 999,
  ready: issues.length === 0,
  readiness_issues: issues.map((issue) => ({
    ...issue,
    detail: "",
    transaction_present: true,
    business_classification: null,
    category_id: null,
    taxable_base: null,
    iva_rate: null,
    iva_amount: null,
  })),
  stale_filings: [],
});
/** A period's check: the preflight lists its issues. */
const snapshotOf = (
  issues: { transaction_id: string; reason: LedgerPreflightReason }[],
): ReadinessSnapshot => ({
  period: { year: 2026, code: "4T" },
  checkedAt: 0,
  status: status(issues),
  preflight: {
    profile_id: "p",
    period: { filing_year: 2026, code: "4T" },
    bucket_id: "p",
    checked_transaction_count: 0,
    issues: issues.map((issue) => ({ ...issue, detail: "" })),
    ready: issues.length === 0,
  },
  savedSince: 0,
});
/** Every period's status: no preflight, and no issues listed. */
const allPeriods = (): ReadinessSnapshot => ({
  period: null,
  checkedAt: 0,
  status: { ...status([]), ready: null },
  preflight: null,
  savedSince: 0,
});

const A = hexId("a");
const B = hexId("b");
const C = hexId("c");
const D = hexId("d");
const E = hexId("e");
const rows: LedgerRow[] = [
  movement(A),
  movement(B, {
    business_classification: "BUSINESS",
    direction: "OUTGOING",
    counterparty: "Imprenta Turia",
    description: "IMPRENTA TURIA 0412",
  }),
  movement(C, {
    business_classification: "BUSINESS",
    currency: "USD",
    amount: "12.5",
    date: "2026-11-03",
  }),
  movement(D, {
    business_classification: "PERSONAL",
    direction: "INTERNAL_TRANSFER",
    amount: "200",
  }),
  movement(E, {
    business_classification: "MIXED",
    business_pct: "0.6",
    direction: "INCOMING",
    lifecycle_state: "ARCHIVED",
    counterparty: "Imprenta Turia",
    description: "IMPRENTA TURIA 0587",
  }),
];
const byId = new Map(rows.map((row) => [row.transaction.transaction_id, row]));

test("the readiness counts are the check's own, and each set filters the loaded movements it names", () => {
  const Z = hexId("z");
  const sets = readinessSets(
    rows,
    snapshotOf([
      { transaction_id: A, reason: "missing_business_classification" },
      { transaction_id: B, reason: "missing_category" },
      { transaction_id: B, reason: "missing_iva_rate" },
      { transaction_id: C, reason: "unsupported_currency" },
      // A movement the window does not hold is counted, not shown.
      { transaction_id: Z, reason: "missing_category" },
    ]),
  );
  expect(sets.counts).toEqual({
    fix: 3,
    fixAtLeast: false,
    toClassify: 1,
    noRate: 1,
  });
  expect([...sets.fix].sort()).toEqual([B, C, Z].sort());
  expect([...sets.toClassify]).toEqual([A]);
  expect([...sets.noRate]).toEqual([C]);
  expect(sets.reasons.map((entry) => [entry.reason, entry.ids.size])).toEqual([
    ["missing_category", 2],
    ["missing_iva_rate", 1],
    ["unsupported_currency", 1],
  ]);
  for (const [filter, loaded] of [
    ["issues", [B, C]],
    ["to_classify", [A]],
    ["no_rate", [C]],
  ] as const) {
    const kept = rows.filter((row) =>
      keepsRow(row, { ...NO_FILTERS, readiness: filter }, sets, null),
    );
    expect(kept.map((row) => row.transaction.transaction_id).sort()).toEqual(
      [...loaded].sort(),
    );
  }
  // The window's rows change none of the counts: fewer rows, the same check.
  expect(readinessSets(rows.slice(0, 1), snapshotOf([])).counts?.fix).toBe(0);
  expect(
    readinessSets(
      [],
      snapshotOf([{ transaction_id: B, reason: "missing_category" }]),
    ).counts,
  ).toEqual({ fix: 1, fixAtLeast: false, toClassify: 0, noRate: 0 });
  // Unchecked, nothing is counted.
  expect(readinessSets(rows, null).counts).toBeNull();
  expect(readinessSets(rows, null).fix.size).toBe(0);
});

test("every period's strip counts what the status read counts over the whole ledger", () => {
  const sets = readinessSets(rows, allPeriods());
  expect(sets.counts).toEqual({
    fix: 0,
    fixAtLeast: false,
    toClassify: 999,
    noRate: 999,
  });
  // The filters still select the loaded rows.
  expect([...sets.toClassify]).toEqual([A]);
  // A status that lists fewer issues than it counts gives a least count.
  const cut: ReadinessSnapshot = {
    ...allPeriods(),
    status: {
      ...status([{ transaction_id: B, reason: "missing_category" }]),
      readiness_issue_count: 5,
    },
  };
  expect(readinessSets(rows, cut).counts).toMatchObject({
    fix: 1,
    fixAtLeast: true,
  });
});

test("the product's own filters become one list read each", () => {
  expect(serverFilters(NO_FILTERS)).toEqual([]);
  // The account is the row's own field: no read asks for it.
  expect(serverFilters({ ...NO_FILTERS, account: "acc-01" })).toEqual([]);
  expect(
    serverFilters({
      ...NO_FILTERS,
      account: "acc-01",
      importBatches: ["b1", "b2"],
      hideRejected: true,
    }),
  ).toEqual([
    { filters: ["import=b1"], exclude_llm_rejected: true },
    { filters: ["import=b2"], exclude_llm_rejected: true },
  ]);
  const members = new Set([A, B]);
  const sets = readinessSets(rows, null);
  expect(
    rows
      .filter((row) => keepsRow(row, NO_FILTERS, sets, members))
      .map((row) => row.transaction.transaction_id),
  ).toEqual([A, B]);
});

test("the account filter and grouping read each row's own account", () => {
  const bound = [
    movement(A, {}, null, "acc-01"),
    movement(B, {}, null, "acc-02"),
    movement(C, {}, null, null),
  ];
  const sets = readinessSets(bound, null);
  const kept = (account: string) =>
    bound
      .filter((row) => keepsRow(row, { ...NO_FILTERS, account }, sets, null))
      .map((row) => row.transaction.transaction_id);
  expect(kept("acc-02")).toEqual([B]);
  // The empty account is the movements bound to none.
  expect(kept("")).toEqual([C]);
  const groups = groupRows(bound, "account", {
    label: (value) => value,
    pendingFirst: false,
    descending: false,
  });
  expect(groups.map((group) => group.value)).toEqual(["acc-01", "acc-02", ""]);
  const sorted = sortRows(
    bound,
    { key: "account", direction: "desc" },
    { ...labels, account: (id) => (id === "acc-01" ? "Zeta" : "Alfa") },
  );
  expect(sorted.map((row) => row.transaction.transaction_id)).toEqual([
    A,
    B,
    C,
  ]);
});

test("a search matches every word, months by name and figures either way", () => {
  const context = {
    months: [
      [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ],
    ],
    category: (id: string) => id,
  };
  const found = (text: string) =>
    rows
      .filter((row) =>
        matchesSearch(
          row,
          text.toLowerCase().split(/\s+/).filter(Boolean),
          context,
        ),
      )
      .map((row) => row.transaction.transaction_id);
  expect(found("imprenta 0412")).toEqual([B]);
  expect(found("imprenta")).toEqual([B, E]);
  expect(found("nov")).toEqual([C]);
  expect(found("12,50")).toEqual([C]);
  expect(found("12.5")).toEqual([C]);
  expect(found("nothing-like-it")).toEqual([]);
});

const labels: SortLabels = {
  category: (id) => id,
  ivaCategory: (id) => id,
  irpfCategory: (id) => id,
  classification: (row) => row.transaction.business_classification,
  direction: (direction) => direction,
  lifecycle: (state) => state,
  classifiedBy: (source) => source,
  account: (id) => id,
  status: (row) => row.review_status,
};

test("sorting puts an empty value last both ways and amounts by value", () => {
  const ids = (sorted: LedgerRow[]) =>
    sorted.map((row) => row.transaction.transaction_id);
  expect(
    ids(sortRows(rows, { key: "amount", direction: "asc" }, labels)),
  ).toEqual([C, A, B, E, D]);
  expect(
    ids(sortRows(rows, { key: "amount", direction: "desc" }, labels)),
  ).toEqual([D, A, B, E, C]);
  const withValueDate = rows.map((row, at) =>
    at === 1
      ? {
          ...row,
          transaction: { ...row.transaction, value_date: "2026-10-01" },
        }
      : row,
  );
  for (const direction of ["asc", "desc"] as const)
    expect(
      ids(sortRows(withValueDate, { key: "value_date", direction }, labels))[0],
    ).toBe(B);
});

test("groups sum each currency by direction and never mix currencies", () => {
  const groups = groupRows(rows, "counterparty", {
    label: (value) => value,
    pendingFirst: false,
    descending: false,
  });
  // The largest group comes first.
  expect(groups.map((group) => [group.value, group.rows.length])).toEqual([
    ["PAPELERÍA TRAZO", 3],
    ["IMPRENTA TURIA", 2],
  ]);
  expect(currencySums(rows)).toEqual([
    { currency: "EUR", incoming: "36.30", outgoing: "72.60", transfer: "200" },
    { currency: "USD", incoming: null, outgoing: "12.5", transfer: null },
  ]);
  expect(normalisedDescription("IMPRENTA TURIA 0412")).toBe(
    normalisedDescription("Imprenta Turia, 0587/B"),
  );
});

test("columns keep the person's order and presets show exactly their set", () => {
  const fresh = columnLayout({ hidden: [], order: [] });
  expect(presetOf(fresh)).toBe("review");
  const iva = columnLayout({
    hidden: presetHidden("iva"),
    order: [...COLUMN_IDS],
  });
  expect(presetOf(iva)).toBe("iva");
  const moved = moveColumn(fresh, "counterparty", -1)!;
  const layout = columnLayout({ hidden: [...fresh.hidden], order: moved });
  const shown = shownColumns(layout);
  expect(shown.indexOf("counterparty")).toBeLessThan(
    shown.indexOf("description"),
  );
  expect(presetOf(layout)).toBe("review");
  // Moving past the end does nothing, and unknown ids are dropped.
  expect(moveColumn(fresh, shown.at(-1)!, 1)).toBeNull();
  expect(
    columnLayout({ hidden: ["nonsense"], order: ["nonsense", "date"] })
      .order[0],
  ).toBe("date");
});

test("classifying asks for what each kind needs and stages it as one step", () => {
  const all = { ids: [A, B, C, D, E], hidden: 0, partial: false };
  // A hidden selection is never classified unseen.
  expect(classifyAvailability("business", { ...all, hidden: 2 }, byId)).toEqual(
    {
      kind: "blocked",
      block: { kind: "hidden", hidden: 2, selected: 5 },
    },
  );
  // Unknown ids remain nothing selected, even when the caller says hidden.
  expect(
    classifyAvailability(
      "business",
      { ids: ["missing"], hidden: 1, partial: false },
      byId,
    ),
  ).toEqual({
    kind: "blocked",
    block: { kind: "nothing_selected" },
  });
  const business = classifyAvailability("business", all, byId);
  // The transfer and the archived movement are left as they are.
  expect(business).toEqual({
    kind: "ready",
    ids: [A, B, C],
    skipped: 2,
    partial: false,
  });
  expect(classifyAvailability("personal", all, byId)).toMatchObject({
    ids: [A, B, C, D],
  });
  expect(
    classifyAvailability(
      "mixed",
      { ids: [D], hidden: 0, partial: false },
      byId,
    ),
  ).toEqual({ kind: "blocked", block: { kind: "transfers_only" } });

  expect(classifyCells({ kind: "business", ids: [A] }, byId)).toEqual({
    kind: "needs",
    field: "category",
  });
  expect(classifyCells({ kind: "mixed", ids: [A] }, byId)).toEqual({
    kind: "needs",
    field: "share",
  });
  expect(
    classifyCells({ kind: "mixed", ids: [A], share: "0.5" }, byId),
  ).toMatchObject({ kind: "refused", refusal: { key: "percent_as_fraction" } });
  const staged = classifyCells(
    { kind: "business", ids: [A, B], category: "material_oficina" },
    byId,
  );
  expect(staged.kind).toBe("staged");
  if (staged.kind !== "staged") return;
  expect(staged.movements).toBe(2);
  expect(
    staged.event.cells.map((cell) => [cell.id, cell.field, cell.value]),
  ).toEqual([
    [A, "business_classification", { kind: "set", value: "BUSINESS" }],
    [A, "category_id", { kind: "set", value: "material_oficina" }],
    [B, "business_classification", { kind: "set", value: "BUSINESS" }],
    [B, "category_id", { kind: "set", value: "material_oficina" }],
  ]);
  // Mixed stages its share as the fraction the product stores, with an
  // expense's category; leaving Mixed clears the stored share.
  const mixed = classifyCells(
    { kind: "mixed", ids: [A], share: "60", category: "telefonia_fija" },
    byId,
  );
  expect(mixed.kind === "staged" && mixed.event.cells[1]).toEqual({
    id: A,
    field: "business_pct",
    value: { kind: "set", value: "0.6" },
    stored: null,
  });
  const personal = classifyCells({ kind: "personal", ids: [E] }, byId);
  expect(personal.kind === "staged" && personal.event.cells[1]).toEqual({
    id: E,
    field: "business_pct",
    value: { kind: "clear" },
    stored: "0.6",
  });
  // A category alone goes only where the movement takes one.
  expect(categoryCells([A, B, E], "material_oficina", byId)).toMatchObject({
    kind: "staged",
    movements: 1,
    skipped: 2,
  });
});

const registry = (name: string) =>
  readFileSync(
    fileURLToPath(
      new URL(
        `../../../../src/cadrumo/_data/registry/aeat/${name}`,
        import.meta.url,
      ),
    ),
    "utf8",
  );

test("the page's vocabularies are the published registry's own lists", () => {
  const profile = registry("facts/0064-categories-profile.toml");
  const order = /key = "spending_category\.order", value = "([^"]+)"/
    .exec(profile)![1]!
    .split(",");
  expect([...SPENDING_CATEGORIES].sort()).toEqual([...order].sort());
  for (const [family, members] of SPENDING_CATEGORY_FAMILIES) {
    const listed = new RegExp(
      `key = "spending_category\\.family\\.${family}", value = "([^"]+)"`,
    ).exec(profile);
    expect(listed?.[1]?.split(","), family).toEqual([...members]);
  }
  const iva = [
    ...registry("iva/catalogues.toml").matchAll(/^category = "([a-z_]+)"$/gm),
  ].map((found) => found[1]);
  expect([...IVA_CATEGORIES]).toEqual(iva);
  const irpf = /key = "catalogue\.ids", value = "([^"]+)"/
    .exec(registry("facts/0081-irpf-ledger-category-taxonomy.toml"))![1]!
    .split(",");
  expect([...IRPF_CATEGORIES]).toEqual(irpf);
});

test("income takes no spending category, and Mixed only one a share applies to", () => {
  const OUT = hexId("10");
  const IN = hexId("11");
  const REFUND = hexId("12");
  const income = new Map(
    [
      movement(OUT),
      movement(IN, { direction: "INCOMING", description: "TALLERES ONDARA" }),
      movement(REFUND, {
        direction: "INCOMING",
        purchase_invoice_evidence_id: "evidence-1",
      }),
    ].map((row) => [row.transaction.transaction_id, row]),
  );
  // An income that refunds an expense carries its purchase invoice and
  // takes the expense's category; pure income takes none.
  expect(takesExpenseCategory(income.get(OUT)!)).toBe(true);
  expect(takesExpenseCategory(income.get(IN)!)).toBe(false);
  expect(takesExpenseCategory(income.get(REFUND)!)).toBe(true);
  expect(categorySplit([OUT, IN, REFUND], income)).toEqual({
    expenses: 2,
    income: 1,
  });

  // Business on income alone is staged at once, with no category.
  const alone = classifyCells({ kind: "business", ids: [IN] }, income);
  expect(alone.kind).toBe("staged");
  if (alone.kind !== "staged") return;
  expect(alone.event.cells.map((cell) => cell.field)).toEqual([
    "business_classification",
  ]);
  // Business on expenses and income asks for a category, which only the
  // expenses get.
  expect(classifyCells({ kind: "business", ids: [OUT, IN] }, income)).toEqual({
    kind: "needs",
    field: "category",
  });
  const both = classifyCells(
    { kind: "business", ids: [OUT, IN], category: "vehiculo_combustible" },
    income,
  );
  expect(
    both.kind === "staged" &&
      both.event.cells
        .filter((cell) => cell.field === "category_id")
        .map((cell) => cell.id),
  ).toEqual([OUT]);

  // Mixed takes a category a business-use share applies to.
  expect(
    classifyCells(
      {
        kind: "mixed",
        ids: [OUT],
        share: "30",
        category: "software_suscripcion",
      },
      income,
    ),
  ).toEqual({ kind: "needs", field: "category" });
  // Home depreciation is recorded through the asset register, not a
  // usage-ratio deduction on a ledger movement.
  expect(
    classifyCells(
      {
        kind: "mixed",
        ids: [OUT],
        share: "30",
        category: "amortizacion_vivienda_afecto",
      },
      income,
    ),
  ).toEqual({ kind: "needs", field: "category" });
  // A mobile line is deductible only in exclusive use, so it takes no share.
  expect(
    classifyCells(
      { kind: "mixed", ids: [OUT], share: "30", category: "telefonia_movil" },
      income,
    ),
  ).toEqual({ kind: "needs", field: "category" });
  const phone = classifyCells(
    { kind: "mixed", ids: [OUT], share: "30", category: "telefonia_fija" },
    income,
  );
  expect(
    phone.kind === "staged" && phone.event.cells.map((cell) => cell.field),
  ).toEqual(["business_classification", "business_pct", "category_id"]);
  expect(
    classifyCells({ kind: "mixed", ids: [IN], share: "30" }, income).kind,
  ).toBe("staged");

  // A category alone goes to no income.
  const classified = new Map(
    [...income.values()].map((row) => [
      row.transaction.transaction_id,
      {
        ...row,
        transaction: {
          ...row.transaction,
          business_classification: "BUSINESS",
        },
      },
    ]),
  );
  expect(
    categoryCells([OUT, IN, REFUND], "material_oficina", classified),
  ).toMatchObject({ kind: "staged", movements: 2, skipped: 1 });
});

test("whether a movement takes a spending category is read as staged, not as stored", () => {
  const OUT = hexId("20");
  const IN = hexId("21");
  const rows = new Map(
    [
      movement(OUT),
      movement(IN, { direction: "INCOMING", description: "TALLERES ONDARA" }),
    ].map((row) => [row.transaction.transaction_id, row]),
  );
  // The expense is staged to become income, and the income to carry a
  // purchase invoice it refunds.
  const staged: StagedContent = {
    rows: { [OUT]: { direction: { kind: "set", value: "INCOMING" } } },
    drafts: [],
    actions: [
      {
        id: "attach",
        kind: "attach",
        transactionId: IN,
        evidenceId: "evidence-1",
        attachmentIds: [],
      },
    ],
  };
  expect(takesExpenseCategory(rows.get(OUT)!)).toBe(true);
  expect(takesExpenseCategory(rows.get(OUT)!, staged)).toBe(false);
  expect(takesExpenseCategory(rows.get(IN)!)).toBe(false);
  expect(takesExpenseCategory(rows.get(IN)!, staged)).toBe(true);
  expect(categorySplit([OUT, IN], rows, staged)).toEqual({
    expenses: 1,
    income: 1,
  });
  const business = classifyCells(
    {
      kind: "business",
      ids: [OUT, IN],
      category: "material_oficina",
      staged,
    },
    rows,
  );
  expect(
    business.kind === "staged" &&
      business.event.cells
        .filter((cell) => cell.field === "category_id")
        .map((cell) => cell.id),
  ).toEqual([IN]);
});

test("the categories a share applies to are the registry's usage-ratio ones", () => {
  const profile = registry("facts/0064-categories-profile.toml");
  const ratio = new Set(
    [
      ...profile.matchAll(
        /key = "proportionality_kind\.([a-z_]+)\.is_usage_ratio", value = "true"/g,
      ),
    ].map((found) => found[1]),
  );
  expect(ratio.size).toBeGreaterThan(0);
  // Every variant of a category names its proportionality kind.
  const kinds = new Map<string, Set<string>>();
  for (const variant of profile.split("[[fact.variants]]").slice(1)) {
    const category = /name = "category", value = "([a-z_]+)"/.exec(
      variant,
    )?.[1];
    const kind = /key = "proportionality_kind", value = "([a-z_]+)"/.exec(
      variant,
    )?.[1];
    if (!category || !kind) continue;
    const seen = kinds.get(category) ?? new Set<string>();
    seen.add(kind);
    kinds.set(category, seen);
  }
  const usage = SPENDING_CATEGORIES.filter((category) =>
    [...(kinds.get(category) ?? [])].some((kind) => ratio.has(kind)),
  );
  expect([...USAGE_RATIO_CATEGORIES].sort()).toEqual([...usage].sort());
  // The families offered with a share are the vocabulary's, narrowed.
  const offered = SHARE_CATEGORY_FAMILIES.flatMap(([, members]) => members);
  expect([...offered].sort()).toEqual([...usage].sort());
  for (const [family, members] of SHARE_CATEGORY_FAMILIES) {
    const all = SPENDING_CATEGORY_FAMILIES.find(([name]) => name === family);
    expect(all, family).toBeDefined();
    expect(members.every((member) => all![1].includes(member as never))).toBe(
      true,
    );
  }
});

test("a reviewed movement is done only once readiness has measured it", () => {
  expect(statusWord("reviewed", 0)).toBe("done");
  expect(statusWord("reviewed", 2)).toBe("needs_fixing");
  // Not measured is not zero issues.
  expect(statusWord("reviewed", null)).toBe("unmeasured");
  // A movement still to classify says so whatever readiness knows.
  expect(statusWord("pending", null)).toBe("pending");
});

test("a compact status column widens by one glyph for each kind of mark beside the status", () => {
  const active = movement(hexId("a"));
  const archived = movement(hexId("b"), { lifecycle_state: "ARCHIVED" });
  const none = new Set<string>();
  expect(statusMarks([active], none)).toBe(0);
  expect(statusMarks([active, archived], none)).toBe(1);
  expect(statusMarks([active, archived], new Set([hexId("a")]))).toBe(2);
  // Two archived movements are one kind of mark.
  expect(
    statusMarks(
      [archived, movement(hexId("c"), { lifecycle_state: "SPLIT" })],
      none,
    ),
  ).toBe(1);
  expect(statusWidth("compact")).toBe(2.75);
  expect(statusWidth("compact", 2)).toBe(5.25);
  // Comfortable rows have room for a mark beside the word.
  expect(statusWidth("comfortable", 2)).toBe(7.5);
});

test("a date carrying its year gets the room for it", () => {
  expect(dateWidth(false)).toBe(4.5);
  expect(dateWidth(true)).toBeGreaterThan(dateWidth(false));
});
