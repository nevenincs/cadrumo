// What the movements grid makes of a period window: its columns and their
// presets, its filters and saved views, the search, the sort, the groups
// with their sums, and the readiness sets the strip counts. Everything here
// works on stored rows as they were read; nothing staged changes a count,
// a filter or a sum. The page refines a window this way only once it is
// read whole; a window read in part is filtered and sorted by the product.

import type {
  LedgerReviewStatus,
  LedgerRow,
  LedgerSortField,
} from "../../../shell/ledger";
import { compareDecimal, sameDecimal } from "../../../shell/ledgerGrammar";
import { importBatchFilters } from "../../../shell/ledgerImports";
import type { StagedContent } from "../../../shell/ledgerStage";
import {
  categoryFamily,
  SPENDING_CATEGORY_FAMILIES,
  type ImportIssue,
} from "../../../shell/ledgerVocabulary";
import type {
  LedgerWindowScope,
  ReadinessSnapshot,
} from "../../../shell/ledgerWindow";

// ---- Columns -----------------------------------------------------------------

export const COLUMN_IDS = [
  "select",
  "status",
  "date",
  "description",
  "counterparty",
  "direction",
  "amount",
  "invoice",
  "eur",
  "classification",
  "category",
  "iva_category",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "irpf_category",
  "documents",
  "group_label",
  "account",
  "notes",
  "lifecycle",
  "classified_by",
  "modified",
] as const;
export type ColumnId = (typeof COLUMN_IDS)[number];
export const isColumnId = (id: string): id is ColumnId =>
  (COLUMN_IDS as readonly string[]).includes(id);

/** How a column is laid out, in rem, and how it sorts. */
export type ColumnSpec = {
  width: number;
  minWidth?: number;
  grow?: number;
  sticky?: "start" | "end";
  align?: "end";
  /** Sortable on a window read whole. */
  sortable: boolean;
  /** The product's own sort axis, which also sorts a window read in part. */
  server?: LedgerSortField;
};

export const COLUMN_SPECS: Record<ColumnId, ColumnSpec> = {
  select: { width: 2.25, sticky: "start", sortable: false },
  // Compact rows draw the status as a glyph alone; see `statusWidth`.
  status: { width: 7.5, sticky: "start", sortable: true },
  date: { width: 4.5, sticky: "start", sortable: true, server: "date" },
  // What a movement is stays in view while its other columns scroll.
  description: {
    width: 12,
    minWidth: 12,
    grow: 2,
    sticky: "start",
    sortable: true,
    server: "description",
  },
  counterparty: { width: 9, minWidth: 9, grow: 1.5, sortable: true },
  direction: { width: 5, sortable: true },
  amount: {
    width: 6.5,
    sticky: "end",
    align: "end",
    sortable: true,
    server: "amount",
  },
  eur: { width: 6.5, align: "end", sortable: true },
  classification: {
    width: 8,
    sortable: true,
    server: "classification",
  },
  category: { width: 10, sortable: true },
  iva_category: { width: 9, sortable: true },
  taxable_base: { width: 6.5, align: "end", sortable: true },
  iva_rate: { width: 4.5, align: "end", sortable: true },
  iva_amount: { width: 6, align: "end", sortable: true },
  irpf_category: { width: 9, sortable: true },
  // The match beside the amount it accounts for: a glyph, kept in view.
  invoice: { width: 3, sticky: "end", sortable: false },
  documents: { width: 4.5, align: "end", sortable: false },
  group_label: { width: 8, sortable: true },
  account: { width: 8, sortable: true },
  notes: { width: 10, sortable: true },
  lifecycle: {
    width: 6,
    sortable: true,
    server: "lifecycle_state",
  },
  classified_by: { width: 8, sortable: true },
  modified: { width: 8, sortable: true, server: "modified_at" },
};

/** The status column's width: a glyph and a count in compact rows, the word
 * beside them in comfortable ones. */
export const statusWidth = (density: "compact" | "comfortable") =>
  density === "compact" ? 2.75 : COLUMN_SPECS.status.width;

/** Columns that are always drawn: the row's selection box. */
const FIXED: readonly ColumnId[] = ["select"];

export const PRESET_IDS = ["review", "iva", "irpf", "everything"] as const;
export type PresetId = (typeof PRESET_IDS)[number];
export const COLUMN_PRESETS: Record<PresetId, readonly ColumnId[]> = {
  review: [
    "select",
    "status",
    "date",
    "description",
    "counterparty",
    "direction",
    "amount",
    "invoice",
    "classification",
    "category",
    "group_label",
  ],
  iva: [
    "select",
    "status",
    "date",
    "description",
    "counterparty",
    "direction",
    "amount",
    "eur",
    "classification",
    "category",
    "iva_category",
    "taxable_base",
    "iva_rate",
    "iva_amount",
  ],
  irpf: [
    "select",
    "status",
    "date",
    "description",
    "counterparty",
    "direction",
    "amount",
    "classification",
    "category",
    "irpf_category",
  ],
  everything: COLUMN_IDS,
};

/** The columns as the person laid them out: every column in order, and
 * those hidden. A layout never chosen is the review preset in the
 * catalogue's order. Ids the page no longer has are dropped. */
export function columnLayout(stored: { hidden: string[]; order: string[] }): {
  order: ColumnId[];
  hidden: Set<ColumnId>;
} {
  if (stored.order.length === 0)
    return {
      order: [...COLUMN_IDS],
      hidden: new Set(
        COLUMN_IDS.filter((id) => !COLUMN_PRESETS.review.includes(id)),
      ),
    };
  const order = stored.order.filter(isColumnId);
  for (const id of COLUMN_IDS) if (!order.includes(id)) order.push(id);
  return {
    order,
    hidden: new Set(
      stored.hidden.filter(
        (id): id is ColumnId => isColumnId(id) && !FIXED.includes(id),
      ),
    ),
  };
}

/** The drawn columns, in order. */
export function shownColumns(layout: {
  order: readonly ColumnId[];
  hidden: ReadonlySet<ColumnId>;
}): ColumnId[] {
  return layout.order.filter((id) => !layout.hidden.has(id));
}

/** The preset the layout shows exactly, if any. */
export function presetOf(layout: {
  hidden: ReadonlySet<ColumnId>;
}): PresetId | null {
  for (const preset of PRESET_IDS) {
    const shown = COLUMN_PRESETS[preset];
    if (COLUMN_IDS.every((id) => shown.includes(id) === !layout.hidden.has(id)))
      return preset;
  }
  return null;
}

/** The hidden set that shows `preset`. */
export const presetHidden = (preset: PresetId): ColumnId[] =>
  COLUMN_IDS.filter((id) => !COLUMN_PRESETS[preset].includes(id));

/** Moves a column one place among the shown columns, past any hidden
 * one between them. */
export function moveColumn(
  layout: { order: readonly ColumnId[]; hidden: ReadonlySet<ColumnId> },
  id: ColumnId,
  by: -1 | 1,
): ColumnId[] | null {
  const shown = shownColumns(layout);
  const at = shown.indexOf(id);
  const to = at + by;
  if (at < 0 || to < 0 || to >= shown.length) return null;
  const other = shown[to]!;
  const order = layout.order.filter((entry) => entry !== id);
  const place = order.indexOf(other) + (by > 0 ? 1 : 0);
  order.splice(place, 0, id);
  return order;
}

// ---- Readiness ---------------------------------------------------------------

/** The reason a movement still needs a classification, which has its own
 * pill rather than a chip. */
export const TO_CLASSIFY_REASON = "missing_business_classification";

/** The column a reason marks and the preset that shows it. */
export const REASON_FIX: Record<
  string,
  { preset: PresetId; column: ColumnId | null }
> = {
  missing_category: { preset: "review", column: "category" },
  missing_taxable_base: { preset: "iva", column: "taxable_base" },
  missing_iva_amount: { preset: "iva", column: "iva_amount" },
  missing_iva_rate: { preset: "iva", column: "iva_rate" },
  missing_eur_tax_substrate: { preset: "iva", column: "eur" },
  missing_counterparty_identification_state: {
    preset: "iva",
    column: "counterparty",
  },
  domestic_identification_on_intra_community_transaction: {
    preset: "iva",
    column: "iva_category",
  },
  eu_member_state_on_export_transaction: {
    preset: "iva",
    column: "iva_category",
  },
  missing_counterparty_establishment_on_export: {
    preset: "iva",
    column: "iva_category",
  },
  inadmissible_deduction_classification: {
    preset: "review",
    column: "classification",
  },
  missing_proportionality_reference: {
    preset: "review",
    column: "classification",
  },
  unsupported_currency: { preset: "iva", column: "eur" },
  unsupported_period: { preset: "review", column: "date" },
  censo_ratio_mismatch: { preset: "review", column: "classification" },
  missing_home_office_afectacion: { preset: "review", column: "category" },
  anomaly_non_declarable_iva_category: {
    preset: "iva",
    column: "iva_category",
  },
  anomaly_non_declarable_recargo_equivalencia: {
    preset: "iva",
    column: "iva_category",
  },
};

/** Movements to classify whose staged change classifies them or approves a
 * suggestion: the staged progress the to-classify pill draws (M8). */
export function stagedClassifyCount(
  toClassify: ReadonlySet<string>,
  content: StagedContent,
): number {
  return [...toClassify].filter(
    (id) =>
      content.rows[id]?.business_classification?.kind === "set" ||
      content.actions.some(
        (action) =>
          action.kind === "suggestion" &&
          action.transactionId === id &&
          action.decision === "apply",
      ),
  ).length;
}

/** Whether a movement is foreign and has no euro value: the EUR column
 * says "No rate", never zero. */
export const lacksRate = (row: LedgerRow) =>
  row.transaction.currency !== "EUR" && row.transaction.value_in_eur === null;

/** The sets the readiness strip counts, each over the rows of the window,
 * so that what a pill or chip filters is exactly what it counts. The
 * issues are as the last check found them; the rest is the stored rows. */
export type ReadinessSets = {
  /** A check has answered for this window. */
  checked: boolean;
  /** By movement, what the check found other than a missing
   * classification. */
  issues: Map<string, string[]>;
  fix: Set<string>;
  toClassify: Set<string>;
  noRate: Set<string>;
  /** By reason, most movements first. */
  reasons: { reason: string; ids: Set<string> }[];
};

export function readinessSets(
  rows: readonly LedgerRow[],
  snapshot: ReadinessSnapshot | null,
): ReadinessSets {
  const present = new Set(rows.map((row) => row.transaction.transaction_id));
  const issues = new Map<string, string[]>();
  const byReason = new Map<string, Set<string>>();
  const found = snapshot
    ? (snapshot.preflight?.issues ?? snapshot.status.readiness_issues)
    : [];
  for (const issue of found) {
    if (issue.reason === TO_CLASSIFY_REASON) continue;
    if (!present.has(issue.transaction_id)) continue;
    const reasons = issues.get(issue.transaction_id) ?? [];
    if (!reasons.includes(issue.reason)) reasons.push(issue.reason);
    issues.set(issue.transaction_id, reasons);
    const ids = byReason.get(issue.reason) ?? new Set<string>();
    ids.add(issue.transaction_id);
    byReason.set(issue.reason, ids);
  }
  const toClassify = new Set<string>();
  const noRate = new Set<string>();
  for (const row of rows) {
    const id = row.transaction.transaction_id;
    if (row.review_status === "pending") toClassify.add(id);
    if (lacksRate(row)) noRate.add(id);
  }
  return {
    checked: snapshot !== null,
    issues,
    fix: new Set(issues.keys()),
    toClassify,
    noRate,
    reasons: [...byReason]
      .map(([reason, ids]) => ({ reason, ids }))
      .sort(
        (a, b) => b.ids.size - a.ids.size || a.reason.localeCompare(b.reason),
      ),
  };
}

// ---- Filters -----------------------------------------------------------------

export type ReadinessFilter = "issues" | "to_classify" | "no_rate";

export type MovementFilters = {
  status: LedgerReviewStatus[];
  direction: string[];
  classification: string[];
  lifecycle: string[];
  /** The movements' own account, as each row names it; the empty string
   * is the movements bound to none. */
  account: string | null;
  /** The product's own filters, read from the ledger: the batches an
   * import wrote, when the person asked to see them, and what the import
   * noted. */
  importBatches: string[];
  importIssue: ImportIssue | null;
  /** Null is any; `{ label: null }` is the movements with no group label. */
  group: { label: string | null } | null;
  reason: string | null;
  readiness: ReadinessFilter | null;
  hideRejected: boolean;
  foreignOnly: boolean;
  /** Classified for the business, active and not yet linked to an invoice. */
  toMatch: boolean;
};

export const NO_FILTERS: MovementFilters = {
  status: [],
  direction: [],
  classification: [],
  lifecycle: [],
  account: null,
  importBatches: [],
  importIssue: null,
  group: null,
  reason: null,
  readiness: null,
  hideRejected: false,
  foreignOnly: false,
  toMatch: false,
};

/** The filters only the product can apply, as the list reads that keep
 * the movements they select: the rows a window holds do not carry them. A
 * list takes one clause of each kind, so several import batches are one
 * read each, and a movement in any of them is kept. Empty when none is in
 * force. */
export function serverFilters(filters: MovementFilters): LedgerWindowScope[] {
  if (!hasServerFilters(filters)) return [];
  const clauses: string[] = [];
  if (filters.importIssue) clauses.push(`issue=${filters.importIssue}`);
  const scope = (extra: string[]): LedgerWindowScope => ({
    ...(clauses.length || extra.length
      ? { filters: [...clauses, ...extra] }
      : {}),
    ...(filters.hideRejected ? { exclude_llm_rejected: true } : {}),
  });
  return filters.importBatches.length
    ? filters.importBatches.map((batch) => scope(importBatchFilters(batch)))
    : [scope([])];
}
export const hasServerFilters = (filters: MovementFilters) =>
  !!(
    filters.importBatches.length ||
    filters.importIssue ||
    filters.hideRejected
  );

/** How many filters are in force, one for each chip shown. */
export function activeFilters(filters: MovementFilters): number {
  return (
    filters.status.length +
    filters.direction.length +
    filters.classification.length +
    filters.lifecycle.length +
    [
      filters.account,
      filters.importBatches.length ? filters.importBatches : null,
      filters.importIssue,
      filters.group,
      filters.reason,
      filters.readiness,
    ].filter((value) => value !== null).length +
    [filters.hideRejected, filters.foreignOnly, filters.toMatch].filter(Boolean)
      .length
  );
}

const DECIDED_BUSINESS = ["BUSINESS", "MIXED"];

/** Whether a stored row passes the filters the page applies itself.
 * `members` holds the rows the product's own filters keep, where any is in
 * force. */
export function keepsRow(
  row: LedgerRow,
  filters: MovementFilters,
  readiness: ReadinessSets,
  members: ReadonlySet<string> | null,
): boolean {
  const t = row.transaction;
  const id = t.transaction_id;
  if (members && !members.has(id)) return false;
  if (filters.status.length && !filters.status.includes(row.review_status))
    return false;
  if (filters.direction.length && !filters.direction.includes(t.direction))
    return false;
  if (
    filters.classification.length &&
    !filters.classification.includes(t.business_classification)
  )
    return false;
  if (
    filters.lifecycle.length &&
    !filters.lifecycle.includes(t.lifecycle_state)
  )
    return false;
  if (filters.group && (row.group_label ?? null) !== filters.group.label)
    return false;
  if (
    filters.account !== null &&
    (row.own_account_id ?? "") !== filters.account
  )
    return false;
  if (filters.reason && !readiness.issues.get(id)?.includes(filters.reason))
    return false;
  if (filters.readiness === "issues" && !readiness.fix.has(id)) return false;
  if (filters.readiness === "to_classify" && !readiness.toClassify.has(id))
    return false;
  if (filters.readiness === "no_rate" && !readiness.noRate.has(id))
    return false;
  if (filters.foreignOnly && t.currency === "EUR") return false;
  if (filters.toMatch && !needsInvoice(row)) return false;
  return true;
}

/** Whether a movement still waits for its invoice: an active business
 * movement, not a transfer, with none linked. */
export function needsInvoice(row: LedgerRow): boolean {
  const t = row.transaction;
  return (
    t.lifecycle_state === "ACTIVE" &&
    t.direction !== "INTERNAL_TRANSFER" &&
    t.invoice_id === null &&
    DECIDED_BUSINESS.includes(t.business_classification)
  );
}

// ---- Saved views -------------------------------------------------------------

export const SAVED_VIEW_IDS = [
  "all",
  "to_classify",
  "to_fix",
  "to_match",
  "foreign",
  "business_expenses",
] as const;
export type SavedViewId = (typeof SAVED_VIEW_IDS)[number];
export const isSavedView = (id: string | null): id is SavedViewId =>
  id !== null && (SAVED_VIEW_IDS as readonly string[]).includes(id);

/** What each saved view filters, by key only, and how it groups. */
export const SAVED_VIEWS: Record<
  SavedViewId,
  { filters: Partial<MovementFilters>; groupBy?: GroupingId }
> = {
  all: { filters: {} },
  to_classify: { filters: { status: ["pending"] }, groupBy: "counterparty" },
  to_fix: { filters: { readiness: "issues" } },
  to_match: { filters: { toMatch: true } },
  foreign: { filters: { foreignOnly: true } },
  business_expenses: {
    filters: { classification: ["BUSINESS", "MIXED"], direction: ["OUTGOING"] },
  },
};
export const viewFilters = (view: SavedViewId): MovementFilters => ({
  ...NO_FILTERS,
  ...SAVED_VIEWS[view].filters,
});

// ---- Search ------------------------------------------------------------------

/** The words of a search, each matched on its own. */
export function searchTerms(text: string): string[] {
  return text
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter((word) => word !== "");
}

/** What a search reads of a row besides its own text. */
export type SearchContext = {
  /** Month names in the chrome language, January first, long and short. */
  months: readonly string[][];
  category: (id: string) => string;
};

const AMOUNT_TERM = /^\d+([.,]\d{1,2})?$/;

/** Whether every word matches the row: its description, counterparty,
 * notes, group label or category, its month by name, or one of its figures
 * written with a dot or a comma. */
export function matchesSearch(
  row: LedgerRow,
  terms: readonly string[],
  context: SearchContext,
): boolean {
  if (terms.length === 0) return true;
  const t = row.transaction;
  const text = [
    t.description,
    t.counterparty,
    t.notes,
    row.group_label ?? "",
    t.category_id ? context.category(t.category_id) : "",
    t.invoice_id ?? "",
  ]
    .join("\n")
    .toLocaleLowerCase();
  const month = Number(t.date.slice(5, 7)) - 1;
  const names = context.months
    .map((list) => list[month]?.toLocaleLowerCase() ?? "")
    .filter(Boolean);
  const figures = [t.amount, t.taxable_base, t.iva_amount, t.value_in_eur];
  return terms.every((term) => {
    if (text.includes(term)) return true;
    if (names.some((name) => name.startsWith(term))) return true;
    if (AMOUNT_TERM.test(term)) {
      const amount = term.replace(",", ".");
      return figures.some(
        (figure) => figure !== null && sameDecimal(figure, amount),
      );
    }
    return false;
  });
}

// ---- Sort --------------------------------------------------------------------

/** Sort axes with no column of their own. */
export const EXTRA_SORT_KEYS = [
  "value_date",
  "created_at",
  "classified_at",
] as const;
export type SortKey = ColumnId | (typeof EXTRA_SORT_KEYS)[number];
export type MovementSort = { key: SortKey; direction: "asc" | "desc" };
export const DEFAULT_SORT: MovementSort = { key: "date", direction: "asc" };

const EXTRA_SERVER: Record<(typeof EXTRA_SORT_KEYS)[number], LedgerSortField> =
  {
    value_date: "value_date",
    created_at: "created_at",
    classified_at: "classified_at",
  };

/** The product's own axis for a sort key, which a window read in part can
 * still be sorted by. */
export function serverSortField(key: SortKey): LedgerSortField | null {
  if (key in EXTRA_SERVER)
    return EXTRA_SERVER[key as keyof typeof EXTRA_SERVER];
  return COLUMN_SPECS[key as ColumnId]?.server ?? null;
}

/** Every key the sort menu offers, in its order. */
export const SORT_KEYS: readonly SortKey[] = [
  "date",
  "value_date",
  "created_at",
  "classified_at",
  "amount",
  "description",
  "counterparty",
  "classification",
  "category",
  "iva_category",
  "eur",
  "status",
  "direction",
  "group_label",
  "account",
  "lifecycle",
  "modified",
];

/** The words a row sorts by where its order is its label. */
export type SortLabels = {
  category: (id: string) => string;
  ivaCategory: (id: string) => string;
  irpfCategory: (id: string) => string;
  classification: (row: LedgerRow) => string;
  direction: (direction: string) => string;
  lifecycle: (state: string) => string;
  classifiedBy: (source: string) => string;
  status: (row: LedgerRow) => string;
  /** An own account's label; null where the row names none. */
  account: (id: string) => string;
};

type SortValue =
  { kind: "text"; text: string } | { kind: "decimal"; text: string };

function sortValue(
  row: LedgerRow,
  key: SortKey,
  labels: SortLabels,
): SortValue | null {
  const t = row.transaction;
  const text = (value: string | null | undefined): SortValue | null =>
    value ? { kind: "text", text: value } : null;
  const decimal = (value: string | null): SortValue | null =>
    value === null ? null : { kind: "decimal", text: value };
  switch (key) {
    case "date":
      return text(t.date);
    case "value_date":
      return text(t.value_date);
    case "created_at":
      return text(t.created_at);
    case "classified_at":
      return text(t.classified_at);
    case "modified":
      return text(t.modified_at);
    case "amount":
      return decimal(t.amount);
    case "eur":
      return decimal(t.currency === "EUR" ? t.amount : t.value_in_eur);
    case "taxable_base":
      return decimal(t.taxable_base);
    case "iva_rate":
      return decimal(t.iva_rate);
    case "iva_amount":
      return decimal(t.iva_amount);
    case "description":
      return text(t.description);
    case "counterparty":
      return text(t.counterparty);
    case "notes":
      return text(t.notes);
    case "group_label":
      return text(row.group_label);
    case "account":
      return text(row.own_account_id && labels.account(row.own_account_id));
    case "category":
      return text(t.category_id && labels.category(t.category_id));
    case "iva_category":
      return text(t.iva_category && labels.ivaCategory(t.iva_category));
    case "irpf_category":
      return text(t.irpf_category && labels.irpfCategory(t.irpf_category));
    case "classification":
      return text(labels.classification(row));
    case "direction":
      return text(labels.direction(t.direction));
    case "lifecycle":
      return text(labels.lifecycle(t.lifecycle_state));
    case "classified_by":
      return text(labels.classifiedBy(t.classified_by));
    case "status":
      return text(labels.status(row));
    default:
      return null;
  }
}

const collator = new Intl.Collator(undefined, { sensitivity: "base" });

/** The rows in `sort`'s order. An empty value sorts last either way, and
 * ties keep the window's own order, which is the product's. */
export function sortRows(
  rows: readonly LedgerRow[],
  sort: MovementSort,
  labels: SortLabels,
): LedgerRow[] {
  const factor = sort.direction === "asc" ? 1 : -1;
  const keyed = rows.map((row, at) => ({
    row,
    at,
    value: sortValue(row, sort.key, labels),
  }));
  keyed.sort((a, b) => {
    if (!a.value || !b.value) {
      if (a.value === b.value) return a.at - b.at;
      return a.value ? -1 : 1;
    }
    const order =
      a.value.kind === "decimal" && b.value.kind === "decimal"
        ? compareDecimal(a.value.text, b.value.text)
        : collator.compare(a.value.text, b.value.text);
    return order * factor || a.at - b.at;
  });
  return keyed.map((entry) => entry.row);
}

// ---- Groups ------------------------------------------------------------------

export const GROUPING_IDS = [
  "category",
  "category_family",
  "classification",
  "status",
  "direction",
  "month",
  "group_label",
  "iva_category",
  "counterparty",
  "description",
  "account",
] as const;
export type GroupingId = (typeof GROUPING_IDS)[number];
export const isGrouping = (id: string | null): id is GroupingId =>
  id !== null && (GROUPING_IDS as readonly string[]).includes(id);
/** The one grouping the product partitions by itself, which a window read
 * in part can still be grouped by. */
export const SERVER_GROUPING: GroupingId = "group_label";

/** A description with its digits, references and punctuation taken out, so
 * the same payment each month falls in one group. */
export function normalisedDescription(text: string): string {
  return text
    .toLocaleUpperCase()
    .replace(/[^\p{L}\s]+/gu, " ")
    .split(/\s+/)
    .filter((word) => word.length > 1)
    .join(" ");
}

/** The value a row is grouped by, or "" where it has none. */
export function groupValue(row: LedgerRow, by: GroupingId): string {
  const t = row.transaction;
  switch (by) {
    case "category":
      return t.category_id ?? "";
    case "category_family":
      return t.category_id ? (categoryFamily(t.category_id) ?? "") : "";
    case "classification":
      return t.business_classification;
    case "status":
      return row.review_status;
    case "direction":
      return t.direction;
    case "month":
      return t.date.slice(0, 7);
    case "group_label":
      return row.group_label ?? "";
    case "iva_category":
      return t.iva_category ?? "";
    case "counterparty":
      return t.counterparty.trim().toLocaleUpperCase();
    case "description":
      return normalisedDescription(t.description);
    case "account":
      return row.own_account_id ?? "";
  }
}

/** Sums of one currency, split by direction. An empty side is null, never
 * zero: nothing of that sense was summed. */
export type CurrencySum = {
  currency: string;
  incoming: string | null;
  outgoing: string | null;
  transfer: string | null;
};

type Exact = { units: bigint; scale: number };
function exactOf(text: string): Exact | null {
  const found = /^(\d+)(?:\.(\d+))?$/.exec(text);
  if (!found) return null;
  const fraction = found[2] ?? "";
  return { units: BigInt(found[1]! + fraction), scale: fraction.length };
}
function addExact(left: Exact, right: Exact): Exact {
  const scale = Math.max(left.scale, right.scale);
  const lift = (value: Exact) =>
    value.units * 10n ** BigInt(scale - value.scale);
  return { units: lift(left) + lift(right), scale };
}
function textOfExact(value: Exact): string {
  const digits = value.units.toString().padStart(value.scale + 1, "0");
  if (value.scale === 0) return digits;
  return `${digits.slice(0, -value.scale)}.${digits.slice(-value.scale)}`;
}

/** The movements' amounts summed per currency and direction, euros first.
 * Currencies are never mixed. */
export function currencySums(rows: readonly LedgerRow[]): CurrencySum[] {
  const sums = new Map<
    string,
    { incoming: Exact | null; outgoing: Exact | null; transfer: Exact | null }
  >();
  for (const row of rows) {
    const t = row.transaction;
    const amount = exactOf(t.amount);
    if (!amount) continue;
    const held = sums.get(t.currency) ?? {
      incoming: null,
      outgoing: null,
      transfer: null,
    };
    const side =
      t.direction === "INCOMING"
        ? "incoming"
        : t.direction === "OUTGOING"
          ? "outgoing"
          : "transfer";
    const before = held[side];
    held[side] = before ? addExact(before, amount) : amount;
    sums.set(t.currency, held);
  }
  return [...sums]
    .sort(([a], [b]) =>
      a === "EUR" ? -1 : b === "EUR" ? 1 : a.localeCompare(b),
    )
    .map(([currency, held]) => ({
      currency,
      incoming: held.incoming && textOfExact(held.incoming),
      outgoing: held.outgoing && textOfExact(held.outgoing),
      transfer: held.transfer && textOfExact(held.transfer),
    }));
}

export type MovementGroup = {
  /** The grid's key for the group's header row. */
  key: string;
  value: string;
  rows: LedgerRow[];
};

const FAMILY_ORDER = new Map<string, number>(
  SPENDING_CATEGORY_FAMILIES.map(([family], at) => [family, at]),
);

/**
 * The rows in groups, each group's rows in the order given. Months follow
 * the date order, families the registry's; counterparty and description
 * groups put the largest first, and in the "To classify" view those with
 * most left to classify. Other groups go by their label. The group with no
 * value is last.
 */
export function groupRows(
  rows: readonly LedgerRow[],
  by: GroupingId,
  options: {
    label: (value: string) => string;
    pendingFirst: boolean;
    descending: boolean;
  },
): MovementGroup[] {
  const groups = new Map<string, LedgerRow[]>();
  for (const row of rows) {
    const value = groupValue(row, by);
    const members = groups.get(value);
    if (members) members.push(row);
    else groups.set(value, [row]);
  }
  const pending = (members: LedgerRow[]) =>
    members.filter((row) => row.review_status === "pending").length;
  const entries = [...groups];
  entries.sort(([a, left], [b, right]) => {
    if (a === "" || b === "") return a === b ? 0 : a === "" ? 1 : -1;
    if (by === "month")
      return options.descending ? b.localeCompare(a) : a.localeCompare(b);
    if (by === "category_family")
      return (FAMILY_ORDER.get(a) ?? 99) - (FAMILY_ORDER.get(b) ?? 99);
    if (by === "counterparty" || by === "description")
      return (
        (options.pendingFirst ? pending(right) - pending(left) : 0) ||
        right.length - left.length ||
        collator.compare(options.label(a), options.label(b))
      );
    return collator.compare(options.label(a), options.label(b));
  });
  return entries.map(([value, members]) => ({
    key: `group:${by}:${value}`,
    value,
    rows: members,
  }));
}
