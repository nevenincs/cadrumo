// How staged changes become ledger operations. Each value goes to the
// operation that accepts it, by whether it sets or clears: the bulk
// classification saves many rows at once but cannot clear, single
// classification and update take a field mask and can. Every row is checked
// against its other staged changes before anything is sent, the work is
// ordered so each step finds the row as it expects, and the bulk is cut into
// parts the host will carry.

import {
  LEDGER_BULK_CLASSIFY_COLUMNS,
  LEDGER_PAYLOAD_LIMIT,
  LEDGER_UPDATE_FIELDS,
  type JsonObject,
  type LedgerAddRequest,
  type LedgerBulkClassifyRequest,
  type LedgerClassifyField,
  type LedgerClassifyRequest,
  type LedgerDefinitionId,
  type LedgerRow,
  type LedgerUpdateField,
  type LedgerUpdateRequest,
  type OutputLanguage,
} from "./ledger";
import {
  canonicalDecimal,
  periodOf,
  samePeriod,
  type LedgerPeriod,
} from "./ledgerGrammar";
import {
  actionRows,
  changesIdentity,
  effectiveFacts,
  STAGE_FIELDS,
  type Draft,
  type DraftField,
  type MovementFacts,
  type StageField,
  type StagedAction,
  type StagedActionKind,
  type StagedContent,
  type StagedValue,
} from "./ledgerStage";

export type LedgerWriteRoute = "bulk" | "classify" | "update";
type Capability = { set: boolean; clear: boolean };
/** What each operation accepts for one field. */
export type FieldRoutes = {
  /** `ledger.classify.bulk`: sets only, since a blank cell is unchanged. */
  bulk: boolean;
  /** `ledger.classify.single`, with a field mask. */
  classify: Capability;
  /** `ledger.update`, with a field mask. */
  update: Capability;
};
const NONE: Capability = { set: false, clear: false };
const SET: Capability = { set: true, clear: false };
const BOTH: Capability = { set: true, clear: true };
const updateOnly = (update: Capability): FieldRoutes => ({
  bulk: false,
  classify: NONE,
  update,
});
const classifyOnly: FieldRoutes = { bulk: false, classify: BOTH, update: NONE };
const taxFigure: FieldRoutes = { bulk: true, classify: BOTH, update: BOTH };

/** The fields each operation accepts, from their registered contracts. An
 * update can replace notes but never blank them, and nothing clears a
 * usage ratio or a classification. */
export const FIELD_ROUTES: Record<StageField, FieldRoutes> = {
  booked_date: updateOnly(SET),
  value_date: updateOnly(BOTH),
  amount: updateOnly(SET),
  direction: updateOnly(SET),
  currency: updateOnly(SET),
  counterparty: updateOnly(BOTH),
  description: updateOnly(SET),
  group_label: updateOnly(BOTH),
  own_account_id: updateOnly(BOTH),
  business_classification: { bulk: true, classify: SET, update: NONE },
  business_pct: { bulk: true, classify: BOTH, update: NONE },
  category_id: { bulk: true, classify: BOTH, update: NONE },
  usage_ratio_id: { bulk: true, classify: NONE, update: NONE },
  taxable_base: taxFigure,
  iva_rate: taxFigure,
  iva_amount: taxFigure,
  iva_category: { bulk: true, classify: BOTH, update: NONE },
  irpf_category: taxFigure,
  notes: { bulk: true, classify: SET, update: SET },
  deduction_fact_kind: classifyOnly,
  investment_asset_id: classifyOnly,
  counterparty_country: classifyOnly,
  counterparty_identification_state: classifyOnly,
};

/** The classifications a person decides; the others are dispositions the
 * product sets. */
export const DECIDED_CLASSIFICATIONS: readonly string[] = [
  "BUSINESS",
  "PERSONAL",
  "MIXED",
];
const decided = (classification: string | null | undefined) =>
  classification != null && DECIDED_CLASSIFICATIONS.includes(classification);

/** Where one staged value goes, or why it can go nowhere. `classified` is
 * whether the row is, or will be, Business, Personal or Mixed. */
export type RouteDecision =
  | { route: LedgerWriteRoute }
  | { refused: "cannot_clear" | "needs_classification" };
export function routeChange(
  field: StageField,
  value: StagedValue,
  classified: boolean,
): RouteDecision {
  const routes = FIELD_ROUTES[field];
  const clear = value.kind === "clear";
  const can = (capability: Capability) =>
    clear ? capability.clear : capability.set;
  const updateOnlyField =
    !routes.bulk && !can(routes.classify) && can(routes.update);
  // A clear, a field only an update takes, and a tax figure on a row with no
  // classification all go through the update's field mask.
  if (can(routes.update) && (updateOnlyField || clear || !classified))
    return { route: "update" };
  // The bulk never carries a clear: a blank cell there means unchanged.
  if (!clear && routes.bulk && classified) return { route: "bulk" };
  if (can(routes.classify) && classified) return { route: "classify" };
  if (can(routes.classify) || (!clear && routes.bulk))
    return { refused: "needs_classification" };
  return { refused: "cannot_clear" };
}

const TAX_FIELDS: readonly StageField[] = [
  "business_pct",
  "category_id",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "deduction_fact_kind",
  "investment_asset_id",
  "counterparty_identification_state",
];
const CLASSIFICATION_FIELDS: ReadonlySet<StageField> = new Set([
  ...TAX_FIELDS,
  "business_classification",
  "counterparty_country",
]);
const DECIMAL_FIELDS: ReadonlySet<StageField> = new Set([
  "amount",
  "business_pct",
  "taxable_base",
  "iva_rate",
  "iva_amount",
]);
const STRUCTURAL: ReadonlySet<StagedActionKind> = new Set([
  "archive",
  "stash",
  "restore",
  "exclude",
  "split",
  "merge",
  "remove",
]);
/** Actions that write a movement's classification figures themselves. */
const CLASSIFYING: ReadonlySet<StagedActionKind> = new Set([
  "iva_derive",
  "allocate",
]);

export type PlanField = StageField | "m210_income_classification";

/** Why a row, a new movement or an action is held back from the apply. */
export type PlanBlocker =
  | { kind: "gone" }
  | { kind: "not_active"; lifecycle: string }
  | { kind: "sealed" }
  | { kind: "cannot_clear"; fields: PlanField[] }
  | { kind: "needs_classification"; fields: PlanField[] }
  | { kind: "mixed_needs_share" }
  | { kind: "share_needs_mixed" }
  | { kind: "transfer_with_tax"; fields: (PlanField | DraftField)[] }
  | { kind: "action_and_edits"; action: string }
  | { kind: "exclude_and_classification"; action: string }
  | { kind: "suggestion_and_edits"; action: string }
  /** A Mixed approval names no business share: it is never saved so. */
  | { kind: "suggestion_needs_share"; action: string }
  | { kind: "actions_conflict"; actions: string[] }
  | { kind: "too_large" }
  | { kind: "draft_incomplete"; fields: DraftField[] };

/** What the review says about a row's work without holding it back. */
export type PlanNote =
  | { kind: "sends_current_classification"; classification: string }
  | { kind: "sends_current_share"; share: string }
  | { kind: "new_identity"; fields: StageField[] }
  | { kind: "moves_period"; from: LedgerPeriod; to: LedgerPeriod };

/** One movement's staged work. */
export type PlanEntry = {
  transactionId: string;
  fields: StageField[];
  routes: Partial<Record<StageField, LedgerWriteRoute>>;
  clears: StageField[];
  actions: string[];
  blockers: PlanBlocker[];
  notes: PlanNote[];
};
export type DraftEntry = { key: string; blockers: PlanBlocker[] };

export type BulkColumn = (typeof LEDGER_BULK_CLASSIFY_COLUMNS)[number];
/** One row of a bulk part, by CSV column. */
export type BulkRow = {
  transactionId: string;
  /** The staged fields this row saves. */
  fields: StageField[];
  cells: Partial<Record<BulkColumn, string>>;
};
export type SuggestionAction = Extract<StagedAction, { kind: "suggestion" }>;
export type PlanStep =
  | {
      kind: "bulk";
      part: number;
      parts: number;
      rows: BulkRow[];
      request: LedgerBulkClassifyRequest;
    }
  | {
      kind: "classify";
      transactionId: string;
      fields: StageField[];
      m210Action: string | null;
      request: LedgerClassifyRequest;
    }
  | {
      kind: "update";
      transactionId: string;
      fields: StageField[];
      newIdentity: boolean;
      request: LedgerUpdateRequest;
    }
  | { kind: "add"; draftKey: string; request: LedgerAddRequest }
  | {
      kind: "action";
      action: StagedAction;
      definition: LedgerDefinitionId;
      request: JsonObject;
    }
  | { kind: "answer"; action: SuggestionAction };

/** What the review says the apply will do, in counts the page words. */
export type PlanSummary = {
  /** Movements saved together, and in how many parts. */
  together: number;
  parts: number;
  singleClassifications: number;
  corrections: number;
  newMovements: number;
  actions: Partial<Record<StagedActionKind, number>>;
  /** Writes that each load and save the whole ledger. */
  oneAtATime: number;
  /** About how long the one-at-a-time writes take. */
  seconds: number;
  permanentLinks: number;
  /** Rows, new movements and actions held back. */
  held: number;
  /** Held-back work by why, to group "297 need a classification". */
  blockers: Partial<Record<PlanBlocker["kind"], number>>;
};

export type LedgerPlan = {
  entries: PlanEntry[];
  drafts: DraftEntry[];
  steps: PlanStep[];
  held: { rows: string[]; drafts: string[]; actions: string[] };
  summary: PlanSummary;
};

export type PlanContext = {
  /** The stored rows, as read at the apply. */
  rows: ReadonlyMap<string, LedgerRow>;
  /** Rows a finalized declaration cites: their facts are sealed. */
  sealed?: ReadonlySet<string>;
  outputLanguage?: OutputLanguage;
  /** The host's payload bound; tests use a smaller one. */
  payloadLimit?: number;
};

/** About how long one write that loads and saves the whole ledger takes. */
export const SINGLE_WRITE_SECONDS = 3;

/** The size the host measures a payload by, in UTF-8 bytes of compact
 * JSON: never fewer than its characters, and within the line bound. */
export function payloadSize(payload: unknown): number {
  return new TextEncoder().encode(JSON.stringify(payload)).length;
}

const wire = (field: StageField, value: string) =>
  DECIMAL_FIELDS.has(field) ? (canonicalDecimal(value) ?? value) : value;

// ---- Bulk CSV ----------------------------------------------------------------

const BULK_COLUMN: Partial<Record<StageField, BulkColumn>> = {
  business_classification: "classification",
  business_pct: "business_pct",
  category_id: "category_id",
  usage_ratio_id: "usage_ratio_id",
  taxable_base: "taxable_base",
  iva_rate: "iva_rate",
  iva_amount: "iva_amount",
  iva_category: "iva_category",
  irpf_category: "irpf_category",
  notes: "notes",
};

const csvCell = (text: string) =>
  /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;

/** The CSV `ledger.classify.bulk` reads: the two required columns and the
 * optional ones a row uses, in the contract's order. A blank cell leaves the
 * stored value as it is. */
export function bulkCsv(rows: readonly BulkRow[]): string {
  const columns = LEDGER_BULK_CLASSIFY_COLUMNS.filter(
    (column) =>
      column === "transaction_id" ||
      column === "classification" ||
      rows.some((row) => row.cells[column] !== undefined),
  );
  const lines = rows.map((row) =>
    columns.map((column) => csvCell(row.cells[column] ?? "")).join(","),
  );
  return [columns.join(","), ...lines].map((line) => `${line}\n`).join("");
}

export function bulkRequest(
  rows: readonly BulkRow[],
  outputLanguage?: OutputLanguage,
): LedgerBulkClassifyRequest {
  return {
    csv_text: bulkCsv(rows),
    ...(outputLanguage ? { output_language: outputLanguage } : {}),
  };
}

/** Cuts bulk rows into parts that each fit the payload bound, in order. A
 * row that does not fit even alone is returned apart. */
export function splitBulk(
  rows: readonly BulkRow[],
  limit = LEDGER_PAYLOAD_LIMIT,
  outputLanguage?: OutputLanguage,
): { parts: BulkRow[][]; tooLarge: BulkRow[] } {
  const parts: BulkRow[][] = [];
  const tooLarge: BulkRow[] = [];
  let part: BulkRow[] = [];
  const fits = (candidate: BulkRow[]) =>
    payloadSize(bulkRequest(candidate, outputLanguage)) <= limit;
  for (const row of rows) {
    if (fits([...part, row])) {
      part.push(row);
      continue;
    }
    if (part.length) parts.push(part);
    part = [];
    if (fits([row])) part.push(row);
    else tooLarge.push(row);
  }
  if (part.length) parts.push(part);
  return { parts, tooLarge };
}

// ---- Planning ------------------------------------------------------------------

const ACTION_RANK: Record<StagedActionKind, number> = {
  suggestion: 0,
  m210: 0,
  iva_derive: 0,
  allocate: 0,
  rule_apply: 0,
  link: 1,
  attach: 1,
  attach_file: 1,
  detach: 1,
  archive: 2,
  stash: 2,
  restore: 2,
  exclude: 2,
  split: 3,
  merge: 3,
  remove: 4,
};

function actionStep(action: StagedAction): PlanStep | null {
  switch (action.kind) {
    case "archive":
    case "stash":
    case "restore":
    case "exclude":
      return {
        kind: "action",
        action,
        definition: `ledger.${action.kind}`,
        request: {
          transaction_id: action.transactionId,
          reason: action.reason,
        },
      };
    case "link":
      return {
        kind: "action",
        action,
        definition: "ledger.link",
        request: {
          transaction_id: action.transactionId,
          invoice_id: action.invoiceId,
        },
      };
    case "attach_file":
      return {
        kind: "action",
        action,
        definition: "ledger.evidence.add",
        request: {
          source_path: action.file,
          idempotency_key: action.idempotencyKey,
        },
      };
    case "attach":
      return {
        kind: "action",
        action,
        definition: "ledger.attach",
        request: {
          transaction_id: action.transactionId,
          purchase_invoice_evidence_id: action.evidenceId,
          attachment_ids: action.attachmentIds,
        },
      };
    case "detach":
      return {
        kind: "action",
        action,
        definition: "ledger.detach",
        request: {
          transaction_id: action.transactionId,
          attachment_ids: action.attachmentIds,
        },
      };
    case "split":
      return {
        kind: "action",
        action,
        definition: "ledger.split.manual",
        request: {
          transaction_id: action.transactionId,
          children: action.children.map((child) => ({
            amount: canonicalDecimal(child.amount) ?? child.amount,
            description: child.description,
          })),
          reason: action.reason,
        },
      };
    case "merge":
      return {
        kind: "action",
        action,
        definition: "ledger.merge",
        request: { child_ids: action.childIds, reason: action.reason },
      };
    case "remove":
      return {
        kind: "action",
        action,
        definition: "ledger.remove",
        request: {
          transaction_id: action.transactionId,
          reason: action.reason,
          dry_run: false,
        },
      };
    case "suggestion":
      return { kind: "answer", action };
    case "m210":
      // Sent inside the row's single classification.
      return null;
    case "iva_derive":
      return {
        kind: "action",
        action,
        definition: "ledger.classify.iva-derive",
        request: {
          transaction_id: action.transactionId,
          iva_category: action.ivaCategory,
        },
      };
    case "allocate":
      return {
        kind: "action",
        action,
        definition: "ledger.allocate",
        request: {
          transaction_id: action.transactionId,
          business_pct:
            canonicalDecimal(action.businessPct) ?? action.businessPct,
          category_id: action.categoryId,
          usage_ratio_id: action.usageRatioId,
          prorrata_reference: action.prorrataReference,
        },
      };
    case "rule_apply":
      return {
        kind: "action",
        action,
        definition: "ledger.rule.apply",
        request: { reaffirm: action.reaffirm, dry_run: false },
      };
  }
}

/** Whether a staged rule apply meets a staged classification on a movement
 * its dry run named: the rules and the person would both decide it, so it
 * is held back until one of them is dropped. */
export function ruleApplyClashes(
  action: Extract<StagedAction, { kind: "rule_apply" }>,
  content: StagedContent,
): boolean {
  return action.transactionIds.some((id) =>
    Object.keys(content.rows[id] ?? {}).some((field) =>
      CLASSIFICATION_FIELDS.has(field as StageField),
    ),
  );
}

/** The checks one movement's staged work must pass. */
function checkRow(
  id: string,
  row: LedgerRow | undefined,
  content: StagedContent,
  actions: StagedAction[],
  context: PlanContext,
): PlanEntry {
  const changes = content.rows[id] ?? {};
  const fields = STAGE_FIELDS.filter((field) => changes[field] !== undefined);
  const entry: PlanEntry = {
    transactionId: id,
    fields,
    routes: {},
    clears: fields.filter((field) => changes[field]?.kind === "clear"),
    actions: actions.map((action) => action.id),
    blockers: [],
    notes: [],
  };
  if (!row) {
    entry.blockers.push({ kind: "gone" });
    return entry;
  }
  const facts = effectiveFacts(row, changes);
  const classified = decided(facts.business_classification);
  const m210 = actions.find((action) => action.kind === "m210");
  const edits = fields.length > 0 || m210 !== undefined;
  const cannotClear: PlanField[] = [];
  const needsClass: PlanField[] = [];
  for (const field of fields) {
    const decision = routeChange(field, changes[field]!, classified);
    if ("route" in decision) entry.routes[field] = decision.route;
    else if (decision.refused === "cannot_clear") cannotClear.push(field);
    else needsClass.push(field);
  }
  if (m210 && !classified) needsClass.push("m210_income_classification");
  if (cannotClear.length)
    entry.blockers.push({ kind: "cannot_clear", fields: cannotClear });
  if (needsClass.length)
    entry.blockers.push({ kind: "needs_classification", fields: needsClass });

  const sendsClassification =
    Object.values(entry.routes).some(
      (route) => route === "bulk" || route === "classify",
    ) ||
    (m210 !== undefined && classified);
  if (sendsClassification && facts.business_classification === "MIXED") {
    if (!facts.business_pct) entry.blockers.push({ kind: "mixed_needs_share" });
    else if (!changes.business_pct)
      entry.notes.push({
        kind: "sends_current_share",
        share: facts.business_pct,
      });
  }
  if (
    changes.business_pct?.kind === "set" &&
    facts.business_classification !== "MIXED"
  )
    entry.blockers.push({ kind: "share_needs_mixed" });
  if (
    Object.values(entry.routes).includes("bulk") &&
    !changes.business_classification
  )
    entry.notes.push({
      kind: "sends_current_classification",
      classification: facts.business_classification!,
    });

  if (
    facts.direction === "INTERNAL_TRANSFER" &&
    fields.some(
      (field) => field === "direction" || CLASSIFICATION_FIELDS.has(field),
    )
  ) {
    const found: PlanField[] = TAX_FIELDS.filter(
      (field) => facts[field] !== null && facts[field] !== undefined,
    );
    if (
      facts.business_classification === "BUSINESS" ||
      facts.business_classification === "MIXED"
    )
      found.unshift("business_classification");
    if (found.length)
      entry.blockers.push({ kind: "transfer_with_tax", fields: found });
  }

  const structural = actions.filter((action) => STRUCTURAL.has(action.kind));
  const classifying = actions.filter((action) => CLASSIFYING.has(action.kind));
  const files = actions.filter((action) => action.kind === "attach_file");
  const suggestions = actions.filter((action) => action.kind === "suggestion");
  const links = actions.filter((action) => action.kind === "link");
  if (
    row.transaction.lifecycle_state !== "ACTIVE" &&
    (edits || suggestions.length || classifying.length || files.length)
  )
    entry.blockers.push({
      kind: "not_active",
      lifecycle: row.transaction.lifecycle_state,
    });
  if (
    context.sealed?.has(id) &&
    (edits ||
      structural.length ||
      suggestions.length ||
      classifying.length ||
      files.length)
  )
    entry.blockers.push({ kind: "sealed" });
  const first = structural[0];
  if (first && edits) {
    const classifying =
      fields.some((field) => CLASSIFICATION_FIELDS.has(field)) ||
      m210 !== undefined;
    entry.blockers.push(
      first.kind === "exclude" && classifying
        ? { kind: "exclude_and_classification", action: first.id }
        : { kind: "action_and_edits", action: first.id },
    );
  }
  const derivation = classifying[0];
  if (
    derivation &&
    (fields.some((field) => CLASSIFICATION_FIELDS.has(field)) || m210)
  )
    entry.blockers.push({ kind: "action_and_edits", action: derivation.id });
  const suggestion = suggestions[0];
  if (
    suggestion &&
    (fields.some((field) => CLASSIFICATION_FIELDS.has(field)) || m210)
  )
    entry.blockers.push({
      kind: "suggestion_and_edits",
      action: suggestion.id,
    });
  for (const found of suggestions) {
    if (found.kind !== "suggestion" || found.decision !== "apply") continue;
    const writes = found.writes ?? [];
    const mixed = writes.some(
      (write) =>
        write.field === "business_classification" && write.value === "MIXED",
    );
    const share = writes.some(
      (write) => write.field === "business_pct" && write.value !== null,
    );
    if (mixed && !share)
      entry.blockers.push({ kind: "suggestion_needs_share", action: found.id });
  }
  const clashing = [
    ...(structural.length > 1 || (structural.length && suggestions.length)
      ? [...structural, ...suggestions]
      : []),
    ...(suggestions.length > 1 ? suggestions : []),
    ...(classifying.length &&
    (classifying.length > 1 || suggestions.length || structural.length)
      ? [...classifying, ...suggestions, ...structural]
      : []),
    ...(links.length > 1 ? links : []),
  ];
  if (clashing.length)
    entry.blockers.push({
      kind: "actions_conflict",
      actions: [...new Set(clashing.map((action) => action.id))],
    });

  const identity = changesIdentity(row, changes);
  if (identity.length)
    entry.notes.push({ kind: "new_identity", fields: identity });
  const before = periodOf(row.transaction.date, "quarter");
  const after = periodOf(
    facts.value_date ?? facts.booked_date ?? "",
    "quarter",
  );
  if (before && after && !samePeriod(before, after))
    entry.notes.push({ kind: "moves_period", from: before, to: after });
  return entry;
}

// The currency is asked for like the date: a new movement assumes none.
const DRAFT_REQUIRED: readonly DraftField[] = [
  "booked_date",
  "amount",
  "currency",
  "direction",
  "description",
];
const DRAFT_DECIMALS: ReadonlySet<DraftField> = new Set([
  "amount",
  "business_pct",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "recargo_amount",
]);
const DRAFT_TAX: readonly DraftField[] = [
  "business_pct",
  "category_id",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "recargo_amount",
  "deduction_fact_kind",
  "investment_asset_id",
  "counterparty_identification_state",
];

function checkDraft(draft: Draft): DraftEntry {
  const fields = draft.fields;
  const blockers: PlanBlocker[] = [];
  const missing = DRAFT_REQUIRED.filter((field) => !fields[field]);
  if (missing.length)
    blockers.push({ kind: "draft_incomplete", fields: missing });
  const classification = fields.business_classification ?? null;
  if (classification === "MIXED" && !fields.business_pct)
    blockers.push({ kind: "mixed_needs_share" });
  if (classification !== "MIXED" && fields.business_pct)
    blockers.push({ kind: "share_needs_mixed" });
  if (fields.direction === "INTERNAL_TRANSFER") {
    const found: (PlanField | DraftField)[] = DRAFT_TAX.filter(
      (field) => fields[field],
    );
    if (classification === "BUSINESS" || classification === "MIXED")
      found.unshift("business_classification");
    if (found.length)
      blockers.push({ kind: "transfer_with_tax", fields: found });
  }
  return { key: draft.key, blockers };
}

function addRequest(draft: Draft): LedgerAddRequest {
  const values: Partial<Record<DraftField, string>> = {};
  for (const [field, text] of Object.entries(draft.fields) as [
    DraftField,
    string,
  ][])
    values[field] = DRAFT_DECIMALS.has(field)
      ? (canonicalDecimal(text) ?? text)
      : text;
  return {
    ...values,
    booked_date: values.booked_date!,
    amount: values.amount!,
    direction: values.direction!,
    description: values.description!,
    idempotency_key: draft.idempotencyKey,
  };
}

function bulkRow(
  entry: PlanEntry,
  facts: MovementFacts,
  content: StagedContent,
): BulkRow | null {
  const fields = entry.fields.filter((field) => entry.routes[field] === "bulk");
  if (!fields.length) return null;
  const changes = content.rows[entry.transactionId] ?? {};
  // Every row names its classification, changed or not, and a mixed row
  // its share with it.
  const cells: Partial<Record<BulkColumn, string>> = {
    transaction_id: entry.transactionId,
    classification: facts.business_classification!,
  };
  if (facts.business_classification === "MIXED" && facts.business_pct)
    cells.business_pct = wire("business_pct", facts.business_pct);
  for (const field of fields) {
    const change = changes[field];
    const column = BULK_COLUMN[field];
    if (change?.kind === "set" && column)
      cells[column] = wire(field, change.value);
  }
  return { transactionId: entry.transactionId, fields, cells };
}

function classifyStep(
  entry: PlanEntry,
  facts: MovementFacts,
  content: StagedContent,
  m210: Extract<StagedAction, { kind: "m210" }> | undefined,
): Extract<PlanStep, { kind: "classify" }> | null {
  const fields = entry.fields.filter(
    (field) => entry.routes[field] === "classify",
  );
  if (!fields.length && !m210) return null;
  const changes = content.rows[entry.transactionId] ?? {};
  const patch: LedgerClassifyRequest["patch"] = {
    business_classification: facts.business_classification!,
  };
  const selected = new Set<LedgerClassifyField>(["business_classification"]);
  if (facts.business_classification === "MIXED" && facts.business_pct) {
    patch.business_pct = wire("business_pct", facts.business_pct);
    selected.add("business_pct");
  }
  for (const field of fields) {
    const change = changes[field]!;
    const name = field as Exclude<
      LedgerClassifyField,
      "m210_income_classification"
    >;
    patch[name] = change.kind === "set" ? wire(field, change.value) : null;
    selected.add(name);
  }
  if (m210) selected.add("m210_income_classification");
  return {
    kind: "classify",
    transactionId: entry.transactionId,
    fields,
    m210Action: m210?.id ?? null,
    request: {
      transaction_id: entry.transactionId,
      patch,
      // The contract takes the mask in sorted order only.
      patch_fields: [...selected].sort(),
      ...(m210 ? { m210: m210.options } : {}),
    },
  };
}

function updateStep(
  entry: PlanEntry,
  content: StagedContent,
): Extract<PlanStep, { kind: "update" }> | null {
  const fields = entry.fields.filter(
    (field) => entry.routes[field] === "update",
  );
  if (!fields.length) return null;
  const changes = content.rows[entry.transactionId] ?? {};
  const patch: LedgerUpdateRequest["patch"] = {};
  const mask: LedgerUpdateField[] = [];
  for (const name of LEDGER_UPDATE_FIELDS) {
    const change = changes[name];
    if (!change || !fields.includes(name)) continue;
    patch[name] = change.kind === "set" ? wire(name, change.value) : null;
    mask.push(name);
  }
  return {
    kind: "update",
    transactionId: entry.transactionId,
    fields,
    newIdentity: entry.notes.some((note) => note.kind === "new_identity"),
    request: { transaction_id: entry.transactionId, patch, patch_fields: mask },
  };
}

/** Plans an apply of everything staged against the rows read at the
 * apply. */
export function planApply(
  content: StagedContent,
  context: PlanContext,
): LedgerPlan {
  const limit = context.payloadLimit ?? LEDGER_PAYLOAD_LIMIT;
  const actionsByRow = new Map<string, StagedAction[]>();
  for (const action of content.actions)
    for (const id of actionRows(action))
      actionsByRow.set(id, [...(actionsByRow.get(id) ?? []), action]);
  const ids = [
    ...new Set([...Object.keys(content.rows), ...actionsByRow.keys()]),
  ];
  // The read's order, then whatever it no longer shows.
  const order = new Map([...context.rows.keys()].map((id, at) => [id, at]));
  const place = (id: string) => order.get(id) ?? order.size;
  ids.sort((a, b) => place(a) - place(b));

  const entries = ids.map((id) =>
    checkRow(
      id,
      context.rows.get(id),
      content,
      actionsByRow.get(id) ?? [],
      context,
    ),
  );
  const drafts = content.drafts.map(checkDraft);
  const factsOf = (entry: PlanEntry) =>
    effectiveFacts(
      context.rows.get(entry.transactionId)!,
      content.rows[entry.transactionId],
    );

  const candidates = entries
    .filter((entry) => !entry.blockers.length)
    .map((entry) => bulkRow(entry, factsOf(entry), content))
    .filter((row): row is BulkRow => row !== null);
  const split = splitBulk(candidates, limit, context.outputLanguage);
  for (const row of split.tooLarge)
    entries
      .find((entry) => entry.transactionId === row.transactionId)!
      .blockers.push({ kind: "too_large" });

  const ready = entries.filter((entry) => !entry.blockers.length);
  const classifies: Extract<PlanStep, { kind: "classify" }>[] = [];
  const updates: Extract<PlanStep, { kind: "update" }>[] = [];
  for (const entry of ready) {
    const facts = factsOf(entry);
    const m210 = (actionsByRow.get(entry.transactionId) ?? []).find(
      (action): action is Extract<StagedAction, { kind: "m210" }> =>
        action.kind === "m210",
    );
    const single = classifyStep(entry, facts, content, m210);
    const update = updateStep(entry, content);
    const oversized = [single, update].some(
      (step) => step !== null && payloadSize(step.request) > limit,
    );
    if (oversized) entry.blockers.push({ kind: "too_large" });
    if (single && !oversized) classifies.push(single);
    if (update && !oversized) updates.push(update);
  }
  const blockedRows = new Set(
    entries
      .filter((entry) => entry.blockers.length)
      .map((e) => e.transactionId),
  );
  const keepStep = (step: { transactionId: string }) =>
    !blockedRows.has(step.transactionId);

  const adds: PlanStep[] = [];
  for (const draft of content.drafts) {
    const checked = drafts.find((entry) => entry.key === draft.key)!;
    if (checked.blockers.length) continue;
    const request = addRequest(draft);
    if (payloadSize(request) > limit)
      checked.blockers.push({ kind: "too_large" });
    else adds.push({ kind: "add", draftKey: draft.key, request });
  }

  const actionSteps: PlanStep[] = [];
  const heldActions: string[] = [];
  const ranked = [...content.actions].sort(
    (a, b) => ACTION_RANK[a.kind] - ACTION_RANK[b.kind],
  );
  for (const action of ranked) {
    if (
      actionRows(action).some((id) => blockedRows.has(id)) ||
      (action.kind === "rule_apply" && ruleApplyClashes(action, content))
    ) {
      heldActions.push(action.id);
      continue;
    }
    const step = actionStep(action);
    if (!step) continue;
    if (step.kind === "action" && payloadSize(step.request) > limit) {
      heldActions.push(action.id);
      continue;
    }
    actionSteps.push(step);
  }

  // A row held back after the cut leaves its part smaller, never larger.
  const parts = split.parts
    .map((part) => part.filter((row) => !blockedRows.has(row.transactionId)))
    .filter((part) => part.length > 0);
  const bulkSteps: PlanStep[] = parts.map((rows, at) => ({
    kind: "bulk",
    part: at + 1,
    parts: parts.length,
    rows,
    request: bulkRequest(rows, context.outputLanguage),
  }));
  const steps = [
    ...bulkSteps,
    ...classifies.filter(keepStep),
    ...updates.filter(keepStep),
    ...adds,
    ...actionSteps,
  ];
  const held = {
    rows: [...blockedRows],
    drafts: drafts.filter((d) => d.blockers.length).map((d) => d.key),
    actions: heldActions,
  };
  return {
    entries,
    drafts,
    steps,
    held,
    summary: summarize(steps, entries, drafts, held),
  };
}

function summarize(
  steps: PlanStep[],
  entries: PlanEntry[],
  drafts: DraftEntry[],
  held: LedgerPlan["held"],
): PlanSummary {
  const count = (kind: PlanStep["kind"]) =>
    steps.filter((step) => step.kind === kind).length;
  const actions: Partial<Record<StagedActionKind, number>> = {};
  for (const step of steps)
    if (step.kind === "action" || step.kind === "answer")
      actions[step.action.kind] = (actions[step.action.kind] ?? 0) + 1;
  const blockers: Partial<Record<PlanBlocker["kind"], number>> = {};
  for (const blocked of [...entries, ...drafts])
    for (const kind of new Set(blocked.blockers.map((found) => found.kind)))
      blockers[kind] = (blockers[kind] ?? 0) + 1;
  const oneAtATime =
    count("classify") +
    count("update") +
    count("add") +
    count("action") +
    count("answer");
  return {
    together: steps.reduce(
      (total, step) => total + (step.kind === "bulk" ? step.rows.length : 0),
      0,
    ),
    parts: count("bulk"),
    singleClassifications: count("classify"),
    corrections: count("update"),
    newMovements: count("add"),
    actions,
    oneAtATime,
    seconds: oneAtATime * SINGLE_WRITE_SECONDS,
    permanentLinks: actions.link ?? 0,
    held: held.rows.length + held.drafts.length + held.actions.length,
    blockers,
  };
}
