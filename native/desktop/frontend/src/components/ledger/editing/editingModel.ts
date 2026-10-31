// What editing the movements grid makes of the person's input: which field a
// column stages, why a cell takes no edit, how typed or pasted text becomes a
// staged value, what fill and copy carry, and how the page counts what is
// staged. Nothing here reads or writes the ledger. The grid draws stored
// values; this decides what would be staged and what is refused, in the
// product's one grammar.

import type { CatalogueInvoice, LedgerRow } from "../../../shell/ledger";
import {
  AMOUNT_RULE,
  TAX_AMOUNT_RULE,
  canonicalDecimal,
  compareDecimal,
  copyAmount,
  copyPercent,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  sameDecimal,
  type GrammarRefusalKey,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type { LedgerPlan } from "../../../shell/ledgerPlan";
import type {
  SinceReadConflict,
  StepOutcome,
  StepReport,
} from "../../../shell/ledgerApply";
import {
  changesIdentity,
  effectiveFacts,
  storedFieldValue,
  unchangedBy,
  type Draft,
  type DraftField,
  type StageCell,
  type StageField,
  type StagedActionKind,
  type StagedContent,
  type StagedRowChanges,
  type StagedValue,
} from "../../../shell/ledgerStage";
import {
  DIRECTIONS,
  IRPF_CATEGORIES,
  IVA_CATEGORIES,
  SPENDING_CATEGORIES,
} from "../../../shell/ledgerVocabulary";
import type { ColumnId } from "../movements/movementsModel";

// ---- Columns and fields --------------------------------------------------------

/** How a column's cell is edited. */
export type EditKind =
  | "text"
  | "amount"
  | "figure"
  | "date"
  | "percent"
  | "direction"
  | "classification"
  | "category"
  | "iva_category"
  | "irpf_category"
  | "account";

/** The columns a person edits, and how. The others are worked out by the
 * product or changed through their own actions. */
export const EDIT_KINDS: Partial<Record<ColumnId, EditKind>> = {
  date: "date",
  description: "text",
  counterparty: "text",
  direction: "direction",
  amount: "amount",
  classification: "classification",
  category: "category",
  iva_category: "iva_category",
  taxable_base: "figure",
  iva_rate: "percent",
  iva_amount: "figure",
  irpf_category: "irpf_category",
  group_label: "text",
  account: "account",
  notes: "text",
};

/** The longest text each one-line field takes, from the update contract. */
const TEXT_LIMITS: Partial<Record<StageField, number>> = {
  description: 4096,
  counterparty: 4096,
  notes: 4096,
  group_label: 64,
};

/** Points typed in a percentage field, said as the grammar reads a percent
 * that names itself: `0.5` is half a per cent, not a fraction. */
export const pointsText = (held: string): string =>
  held.trim() === "" ? held : `${held.trim()}%`;

/** The points a person typed, without the sign `pointsText` said them with:
 * what a refusal echoes and a field shows again. */
export const typedPoints = (said: string): string =>
  said.replace(/\s*%\s*$/, "");

/** The most a text field takes. */
export const textLimitOf = (field: StageField | DraftField): number =>
  TEXT_LIMITS[field as StageField] ?? 4096;

/** The columns whose value is a tax fact, which a transfer never takes. */
const TAX_COLUMNS: ReadonlySet<ColumnId> = new Set([
  "category",
  "iva_category",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "irpf_category",
]);

/** The columns whose change gives a movement a new id. */
export const IDENTITY_COLUMNS: ReadonlySet<ColumnId> = new Set([
  "date",
  "description",
  "amount",
  "account",
]);

/** The choice that binds a movement to no own account: a clear of it. */
export const NO_ACCOUNT = "none:account";

/** The field a column stages on a stored movement. The date shown is the
 * value date where there is one, else the booked date, and an edit changes
 * the one shown. */
export function columnField(
  column: ColumnId,
  row: LedgerRow,
): StageField | null {
  if (!EDIT_KINDS[column]) return null;
  if (column === "date")
    return row.transaction.value_date !== null ? "value_date" : "booked_date";
  if (column === "classification") return "business_classification";
  if (column === "account") return "own_account_id";
  if (column === "category") return "category_id";
  return column as StageField;
}

/** The field a column fills in on a new movement. A group label is set
 * once the movement is saved: an add does not take one. */
export function draftField(column: ColumnId): DraftField | null {
  if (!EDIT_KINDS[column] || column === "group_label") return null;
  if (column === "date") return "booked_date";
  if (column === "classification") return "business_classification";
  if (column === "account") return "own_account_id";
  if (column === "category") return "category_id";
  return column as DraftField;
}

/** What a cell is edited on: a stored movement, with what is staged on it,
 * or a new movement. */
export type EditSubject =
  | {
      kind: "row";
      row: LedgerRow;
      changes: StagedRowChanges | undefined;
      /** A finalized declaration cites it. */
      sealed: boolean;
    }
  | { kind: "draft"; draft: Draft };

/** Why a cell takes no edit. */
export type LockReason =
  | { kind: "not_active"; lifecycle: string }
  | { kind: "sealed" }
  | { kind: "transfer" }
  | { kind: "after_add" }
  | { kind: "derived" };

const TRANSFER = "INTERNAL_TRANSFER";

/** Why `column` of `subject` cannot be edited, or null where it can. A
 * transfer's tax fields are judged on the direction it will have. */
export function lockReason(
  column: ColumnId,
  subject: EditSubject,
): LockReason | null {
  if (column === "select") return null;
  if (!EDIT_KINDS[column]) return { kind: "derived" };
  if (subject.kind === "draft") {
    if (column === "group_label") return { kind: "after_add" };
    if (TAX_COLUMNS.has(column) && subject.draft.fields.direction === TRANSFER)
      return { kind: "transfer" };
    return null;
  }
  const state = subject.row.transaction.lifecycle_state;
  if (state !== "ACTIVE") return { kind: "not_active", lifecycle: state };
  if (subject.sealed) return { kind: "sealed" };
  if (TAX_COLUMNS.has(column)) {
    const facts = effectiveFacts(subject.row, subject.changes);
    if (facts.direction === TRANSFER) return { kind: "transfer" };
  }
  return null;
}

// ---- Typed and pasted values ---------------------------------------------------

/** Why a value was refused: the grammar's reasons, and the editor's own. */
export type EditRefusalKey =
  | GrammarRefusalKey
  | "required"
  | "cannot_clear"
  | "unknown_choice"
  | "needs_share"
  | "locked";
export type EditRefusal = {
  key: EditRefusalKey;
  raw: string;
  suggestion?: string;
  limit?: number;
};

/** The words a choice is known by in the page's language, so a pasted
 * label means the same as the token. */
export type ChoiceLabels = {
  direction: (token: string) => string;
  classification: (token: string) => string;
  category: (id: string) => string;
  ivaCategory: (id: string) => string;
  irpfCategory: (id: string) => string;
  /** An own account's label, and the ids the register holds. */
  account: (id: string) => string;
  accounts: readonly string[];
  noAccount: string;
};

/** A typed value: what it sets, with the business share a Mixed
 * classification carries. */
export type CellValue = { value: string; share?: string };
/** A typed cell: a value, nothing typed, or a refusal. */
export type CellParse =
  | { kind: "value"; value: CellValue }
  | { kind: "empty" }
  | { kind: "refused"; refusal: EditRefusal };

const DIRECTION_ALIASES: Record<string, string> = {
  IN: "INCOMING",
  OUT: "OUTGOING",
  TRANSFER: TRANSFER,
};
const DECIDED = ["BUSINESS", "PERSONAL", "MIXED"] as const;

const fold = (text: string) =>
  text.normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();

function choose(
  raw: string,
  options: readonly string[],
  label: (token: string) => string,
  aliases: Record<string, string> = {},
): CellParse {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  const upper = text.toUpperCase();
  const alias = aliases[upper];
  if (alias) return { kind: "value", value: { value: alias } };
  const wanted = fold(text);
  const found = options.find(
    (option) =>
      option.toLowerCase() === wanted || fold(label(option)) === wanted,
  );
  return found
    ? { kind: "value", value: { value: found } }
    : { kind: "refused", refusal: { key: "unknown_choice", raw } };
}

function lift(parsed: Parsed<string>): CellParse {
  if (parsed.kind === "value")
    return { kind: "value", value: { value: parsed.value } };
  return parsed;
}

/** What `raw` stages in a cell of `kind`, in the product's grammar: a
 * value, nothing typed, or a refusal that echoes it. Nothing typed is not a
 * clear. */
export function parseCell(
  kind: EditKind,
  field: StageField | DraftField,
  raw: string,
  labels: ChoiceLabels,
): CellParse {
  switch (kind) {
    case "text":
      return lift(parseLine(raw, textLimitOf(field)));
    case "amount":
      return lift(parseDecimal(raw, AMOUNT_RULE));
    case "figure":
      return lift(parseDecimal(raw, TAX_AMOUNT_RULE));
    case "date":
      return lift(parseIsoDate(raw));
    case "percent":
      return lift(parsePercent(raw));
    case "direction":
      return choose(raw, DIRECTIONS, labels.direction, DIRECTION_ALIASES);
    case "category":
      return choose(raw, SPENDING_CATEGORIES, labels.category);
    case "iva_category":
      return choose(raw, IVA_CATEGORIES, labels.ivaCategory);
    case "irpf_category":
      return choose(raw, IRPF_CATEGORIES, labels.irpfCategory);
    case "account": {
      if (raw.trim() !== "" && fold(raw) === fold(labels.noAccount))
        return { kind: "value", value: { value: NO_ACCOUNT } };
      return choose(raw, labels.accounts, labels.account);
    }
    case "classification": {
      // "Mixed 50%", as the grid writes and copies it.
      const shared = /^(.*\S)\s+(\d+(?:\.\d+)?\s*%)$/.exec(raw.trim());
      if (shared) {
        const head = choose(shared[1]!, DECIDED, labels.classification);
        if (head.kind !== "value" || head.value.value !== "MIXED")
          return head.kind === "refused"
            ? head
            : { kind: "refused", refusal: { key: "unknown_choice", raw } };
        const share = parsePercent(shared[2]!);
        if (share.kind === "refused") return share;
        if (share.kind === "empty")
          return { kind: "refused", refusal: { key: "needs_share", raw } };
        return { kind: "value", value: { value: "MIXED", share: share.value } };
      }
      return choose(raw, DECIDED, labels.classification);
    }
  }
}

/** The fields Delete never clears: the four facts every movement has, its
 * currency and classification, and notes, which no operation blanks. */
const REQUIRED: ReadonlySet<string> = new Set([
  "booked_date",
  "amount",
  "direction",
  "description",
  "currency",
]);
const NO_CLEAR: ReadonlySet<string> = new Set([
  "business_classification",
  "notes",
]);

/** Why clearing `field` is refused, or null where a clear is staged. */
export function clearRefusal(
  field: StageField | DraftField,
): EditRefusal | null {
  if (REQUIRED.has(field)) return { key: "required", raw: "" };
  if (NO_CLEAR.has(field)) return { key: "cannot_clear", raw: "" };
  return null;
}

/** The staged cells that set `value` on `row`'s `field`: a classification
 * names its share when it is Mixed and clears a stored one when it stops
 * being so. */
export function rowCells(
  id: string,
  row: LedgerRow,
  field: StageField,
  input: CellValue | null,
): StageCell[] {
  if (input?.value === NO_ACCOUNT) input = null;
  const value: StagedValue =
    input === null ? { kind: "clear" } : { kind: "set", value: input.value };
  const cells: StageCell[] = [
    { id, field, value, stored: storedFieldValue(row, field) },
  ];
  if (field !== "business_classification" || input === null) return cells;
  const storedShare = storedFieldValue(row, "business_pct");
  if (input.share !== undefined)
    cells.push({
      id,
      field: "business_pct",
      value: { kind: "set", value: input.share },
      stored: storedShare,
    });
  else if (input.value !== "MIXED" && storedShare != null)
    cells.push({
      id,
      field: "business_pct",
      value: { kind: "clear" },
      stored: storedShare,
    });
  return cells;
}

/** A new movement's field filled in or emptied. */
export type DraftEdit = {
  key: string;
  field: DraftField;
  value: string | null;
};
export function draftEdits(
  key: string,
  field: DraftField,
  input: CellValue | null,
): DraftEdit[] {
  if (input?.value === NO_ACCOUNT) input = null;
  const edits: DraftEdit[] = [{ key, field, value: input?.value ?? null }];
  if (field === "business_classification" && input) {
    if (input.share !== undefined)
      edits.push({ key, field: "business_pct", value: input.share });
    else if (input.value !== "MIXED")
      edits.push({ key, field: "business_pct", value: null });
  }
  return edits;
}

// ---- The value a cell holds, stored or staged --------------------------------

/** What a cell would hold once saved: the stored value with its staged
 * change, or what a new movement was given. Null is empty. */
export function effectiveValue(
  subject: EditSubject,
  column: ColumnId,
): { value: string | null; share: string | null } {
  if (subject.kind === "draft") {
    const field = draftField(column);
    const fields = subject.draft.fields;
    return {
      value: field ? (fields[field] ?? null) : null,
      share: fields.business_pct ?? null,
    };
  }
  const field = columnField(column, subject.row);
  const facts = effectiveFacts(subject.row, subject.changes);
  return {
    value: field ? (facts[field] ?? null) : null,
    share: facts.business_pct ?? null,
  };
}

/** The text copying a cell puts on the clipboard, which pastes back as the
 * same value: canonical figures, `50%` for a share, ISO dates and enums by
 * their label. */
export function copyCell(
  subject: EditSubject,
  column: ColumnId,
  labels: ChoiceLabels & { mixedShare: (share: string) => string },
): string {
  const kind = EDIT_KINDS[column];
  if (!kind) return "";
  const { value, share } = effectiveValue(subject, column);
  if (value === null) return kind === "account" ? labels.noAccount : "";
  switch (kind) {
    case "amount":
    case "figure":
      return copyAmount(value);
    case "percent":
      return copyPercent(value);
    case "direction":
      return labels.direction(value);
    case "classification":
      return value === "MIXED" && share !== null
        ? labels.mixedShare(copyPercent(share))
        : labels.classification(value);
    case "category":
      return labels.category(value);
    case "iva_category":
      return labels.ivaCategory(value);
    case "irpf_category":
      return labels.irpfCategory(value);
    case "account":
      return labels.account(value);
    default:
      return value;
  }
}

// ---- Tab-separated text --------------------------------------------------------

export type TsvParse =
  | { kind: "cells"; rows: string[][] }
  | { kind: "refused"; reason: "unclosed_quote" };

/** Reads a spreadsheet's tab-separated text: rows by line, cells by tab, a
 * quoted cell as written with `""` for a quote. A quote left open refuses
 * the whole text rather than guess where the cell ends. */
export function parseTsv(text: string): TsvParse {
  const source = text.replace(/\r\n?/g, "\n").replace(/\n$/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let at = 0;
  for (;;) {
    let cell = "";
    if (source[at] === '"') {
      at += 1;
      let closed = false;
      while (at < source.length) {
        const char = source[at]!;
        if (char === '"') {
          if (source[at + 1] === '"') {
            cell += '"';
            at += 2;
            continue;
          }
          at += 1;
          closed = true;
          break;
        }
        cell += char;
        at += 1;
      }
      if (!closed) return { kind: "refused", reason: "unclosed_quote" };
      // Text after the closing quote belongs to the same cell.
      while (at < source.length && source[at] !== "\t" && source[at] !== "\n")
        cell += source[at++];
    } else {
      while (at < source.length && source[at] !== "\t" && source[at] !== "\n")
        cell += source[at++];
    }
    row.push(cell);
    if (at >= source.length) {
      rows.push(row);
      return { kind: "cells", rows };
    }
    if (source[at] === "\n") {
      rows.push(row);
      row = [];
    }
    at += 1;
  }
}

// ---- Paste ---------------------------------------------------------------------

/** One cell a paste or fill refuses, said in the cell. */
export type RefusedCell = {
  key: string;
  column: ColumnId;
  refusal: EditRefusal;
};

/** What a paste would stage, before it is staged. */
export type PastePlan = {
  /** Rows of clipboard text. */
  rows: number;
  /** The target columns, in drawn order. */
  columns: ColumnId[];
  stage: StageCell[];
  drafts: DraftEdit[];
  /** Cells that change. */
  changes: number;
  refused: RefusedCell[];
  /** Cells past the last drawn row or column. */
  dropped: number;
  /** Blank cells, which leave the cell as it is. */
  blanks: number;
  /** Movements the paste gives a new id. */
  newIdentity: number;
  /** A paste of several rows, or one that touches an identity, is shown
   * before it is staged. */
  needsPreview: boolean;
};

export type GridOrder = {
  rows: readonly string[];
  columns: readonly ColumnId[];
};

/** One value set on one cell, staged or drafted, with what it refused. */
function placeValue(
  key: string,
  column: ColumnId,
  subject: EditSubject,
  input: CellParse | { kind: "clear" },
  out: { stage: StageCell[]; drafts: DraftEdit[]; refused: RefusedCell[] },
  raw: string,
): "staged" | "refused" | "blank" | "unchanged" {
  // A blank leaves any cell as it is, a locked one too.
  if (input.kind === "empty") return "blank";
  const lock = lockReason(column, subject);
  if (lock) {
    out.refused.push({ key, column, refusal: { key: "locked", raw } });
    return "refused";
  }
  if (input.kind === "refused") {
    out.refused.push({ key, column, refusal: input.refusal });
    return "refused";
  }
  const value = input.kind === "clear" ? null : input.value;
  if (subject.kind === "draft") {
    const field = draftField(column)!;
    if (value === null) {
      const refusal = clearRefusal(field);
      if (refusal) {
        out.refused.push({ key, column, refusal });
        return "refused";
      }
    }
    if ((subject.draft.fields[field] ?? null) === (value?.value ?? null))
      return "unchanged";
    out.drafts.push(...draftEdits(key, field, value));
    return "staged";
  }
  const field = columnField(column, subject.row)!;
  if (value === null) {
    const refusal = clearRefusal(field);
    if (refusal) {
      out.refused.push({ key, column, refusal });
      return "refused";
    }
  }
  const cells = rowCells(key, subject.row, field, value);
  const current = subject.changes?.[field];
  const staged: StagedValue =
    value === null ? { kind: "clear" } : { kind: "set", value: value.value };
  const same = current
    ? current.kind === staged.kind &&
      (current.kind === "clear" ||
        (staged.kind === "set" && current.value === staged.value))
    : unchangedBy(field, storedFieldValue(subject.row, field), staged);
  if (same && cells.length === 1) return "unchanged";
  out.stage.push(...cells);
  return "staged";
}

/**
 * What pasting `text` at `anchor` stages, cell by cell through each
 * column's grammar. One copied value pasted over a range fills the range;
 * otherwise the block runs right and down over the drawn rows and columns
 * from the anchor, and what falls past them is dropped. A blank cell leaves
 * the cell as it is: only Delete clears.
 */
export function planPaste(
  text: string,
  anchor: { key: string; column: ColumnId },
  range: { rows: readonly string[]; columns: readonly ColumnId[] } | null,
  order: GridOrder,
  subjectOf: (key: string) => EditSubject | undefined,
  labels: ChoiceLabels,
): PastePlan | { kind: "refused"; reason: "unclosed_quote" | "empty" } {
  const parsed = parseTsv(text);
  if (parsed.kind === "refused") return parsed;
  const block = parsed.rows;
  if (block.length === 0 || (block.length === 1 && block[0]!.join("") === ""))
    return { kind: "refused", reason: "empty" };
  const out = {
    stage: [] as StageCell[],
    drafts: [] as DraftEdit[],
    refused: [] as RefusedCell[],
  };
  let changes = 0;
  let blanks = 0;
  let dropped = 0;
  const targets: { key: string; column: ColumnId; raw: string }[] = [];
  const single = block.length === 1 && block[0]!.length === 1;
  if (single && range && (range.rows.length > 1 || range.columns.length > 1)) {
    for (const key of range.rows)
      for (const column of range.columns)
        targets.push({ key, column, raw: block[0]![0]! });
  } else {
    const top = order.rows.indexOf(anchor.key);
    const left = order.columns.indexOf(anchor.column);
    block.forEach((cells, down) => {
      cells.forEach((raw, across) => {
        const key = order.rows[top + down];
        const column = order.columns[left + across];
        if (top < 0 || left < 0 || key === undefined || column === undefined) {
          dropped += 1;
          return;
        }
        targets.push({ key, column, raw });
      });
    });
  }
  const columns: ColumnId[] = [];
  const identity = new Set<string>();
  const touched = new Map<string, StagedRowChanges>();
  let touchesIdentity = false;
  for (const { key, column, raw } of targets) {
    if (column === "select") continue;
    if (!columns.includes(column)) columns.push(column);
    const subject = subjectOf(key);
    if (!subject) {
      dropped += 1;
      continue;
    }
    const kind = EDIT_KINDS[column];
    const field =
      subject.kind === "draft"
        ? draftField(column)
        : columnField(column, subject.row);
    const input =
      kind && field
        ? parseCell(kind, field, raw, labels)
        : raw.trim() === ""
          ? ({ kind: "empty" } as const)
          : ({ kind: "refused", refusal: { key: "locked", raw } } as const);
    const before = out.stage.length;
    const placed = placeValue(key, column, subject, input, out, raw);
    if (placed === "blank") blanks += 1;
    if (placed === "staged") {
      changes += 1;
      if (IDENTITY_COLUMNS.has(column)) touchesIdentity = true;
      if (subject.kind === "row") {
        const merged = { ...(touched.get(key) ?? subject.changes) };
        for (const cell of out.stage.slice(before))
          merged[cell.field] = cell.value;
        touched.set(key, merged);
        if (changesIdentity(subject.row, merged).length) identity.add(key);
      }
    }
  }
  const rows = new Set(targets.map((target) => target.key)).size;
  return {
    rows: block.length,
    columns,
    ...out,
    changes,
    dropped,
    blanks,
    newIdentity: identity.size,
    needsPreview: block.length > 1 || rows > 1 || touchesIdentity,
  };
}

// ---- Fill down -----------------------------------------------------------------

export type FillPlan =
  | {
      kind: "fill";
      stage: StageCell[];
      drafts: DraftEdit[];
      /** Cells left as they were: locked, or with nothing to fill from. */
      kept: number;
      refused: RefusedCell[];
      changes: number;
    }
  | { kind: "too_short" };

/** What filling the range down stages: each column's top value, as it
 * would be saved, on every row below it. An empty top cell fills
 * nothing. */
export function planFill(
  range: { rows: readonly string[]; columns: readonly ColumnId[] },
  subjectOf: (key: string) => EditSubject | undefined,
): FillPlan {
  if (range.rows.length < 2) return { kind: "too_short" };
  const out = {
    stage: [] as StageCell[],
    drafts: [] as DraftEdit[],
    refused: [] as RefusedCell[],
  };
  let kept = 0;
  let changes = 0;
  const top = subjectOf(range.rows[0]!);
  for (const column of range.columns) {
    if (!EDIT_KINDS[column] || !top) {
      kept += range.rows.length - 1;
      continue;
    }
    const source = effectiveValue(top, column);
    for (const key of range.rows.slice(1)) {
      const subject = subjectOf(key);
      if (!subject || source.value === null || lockReason(column, subject)) {
        kept += 1;
        continue;
      }
      const input: CellValue =
        column === "classification" &&
        source.value === "MIXED" &&
        source.share !== null
          ? { value: source.value, share: source.share }
          : { value: source.value };
      const placed = placeValue(
        key,
        column,
        subject,
        { kind: "value", value: input },
        out,
        source.value,
      );
      if (placed === "staged") changes += 1;
      else kept += 1;
    }
  }
  return { kind: "fill", ...out, kept, changes };
}

// ---- Counting what is staged ---------------------------------------------------

/** What is staged, in the page's one unit: movements changed, plus actions,
 * plus new movements. Edits are counted apart, for the tray's detail. */
export type StageTally = {
  units: number;
  movements: number;
  edits: number;
  drafts: number;
  actions: number;
  byAction: Partial<Record<StagedActionKind, number>>;
};
export function stageTally(content: StagedContent): StageTally {
  let edits = 0;
  for (const changes of Object.values(content.rows))
    edits += Object.keys(changes).length;
  const byAction: Partial<Record<StagedActionKind, number>> = {};
  for (const action of content.actions)
    byAction[action.kind] = (byAction[action.kind] ?? 0) + 1;
  const movements = Object.keys(content.rows).length;
  return {
    units: movements + content.actions.length + content.drafts.length,
    movements,
    edits,
    drafts: content.drafts.length,
    actions: content.actions.length,
    byAction,
  };
}

/** How many of the staged units the plan holds back, in the same unit:
 * a movement whose edits are held, an action not sent, a new movement held. */
export function heldUnits(content: StagedContent, plan: LedgerPlan): number {
  const heldRows = new Set(plan.held.rows);
  const rows = Object.keys(content.rows).filter((id) => heldRows.has(id));
  const sent = new Set<string>();
  for (const step of plan.steps) {
    if (step.kind === "action" || step.kind === "answer")
      sent.add(step.action.id);
    if (step.kind === "classify" && step.m210Action) sent.add(step.m210Action);
  }
  const actions = content.actions.filter((action) => !sent.has(action.id));
  return rows.length + actions.length + plan.held.drafts.length;
}

// ---- The review ----------------------------------------------------------------

/** One kind of change, as the review's summary lists it: the field, what
 * is stored and what is staged, and on which movements. */
export type ChangeGroup = {
  field: StageField;
  from: string | null;
  to: StagedValue;
  ids: string[];
};
export function changeGroups(
  content: StagedContent,
  rows: ReadonlyMap<string, LedgerRow>,
): ChangeGroup[] {
  const groups = new Map<string, ChangeGroup>();
  for (const [id, changes] of Object.entries(content.rows)) {
    const row = rows.get(id);
    for (const [field, to] of Object.entries(changes) as [
      StageField,
      StagedValue,
    ][]) {
      const from = row ? (storedFieldValue(row, field) ?? null) : null;
      const key = JSON.stringify([field, from, to]);
      const group = groups.get(key);
      if (group) group.ids.push(id);
      else groups.set(key, { field, from, to, ids: [id] });
    }
  }
  return [...groups.values()].sort((a, b) => b.ids.length - a.ids.length);
}

/** A staged movement changed elsewhere in a field the person also changed:
 * the review asks which to keep. A change to other fields is no
 * question. */
export type AskedConflict =
  | {
      kind: "changed";
      transactionId: string;
      before: LedgerRow;
      after: LedgerRow;
      fields: StageField[];
    }
  | { kind: "gone"; transactionId: string; before: LedgerRow | null };

const DECIMAL_FIELDS: ReadonlySet<StageField> = new Set([
  "amount",
  "business_pct",
  "taxable_base",
  "iva_rate",
  "iva_amount",
]);
const sameStored = (
  field: StageField,
  left: string | null | undefined,
  right: string | null | undefined,
) =>
  left === right ||
  (DECIMAL_FIELDS.has(field) &&
    left != null &&
    right != null &&
    sameDecimal(left, right));

export function askedConflicts(
  conflicts: readonly SinceReadConflict[],
  content: StagedContent,
): AskedConflict[] {
  const asked: AskedConflict[] = [];
  for (const conflict of conflicts) {
    if (conflict.kind === "gone") {
      asked.push(conflict);
      continue;
    }
    const staged = Object.keys(
      content.rows[conflict.transactionId] ?? {},
    ) as StageField[];
    const fields = staged.filter(
      (field) =>
        !sameStored(
          field,
          storedFieldValue(conflict.before, field),
          storedFieldValue(conflict.after, field),
        ),
    );
    if (fields.length) asked.push({ ...conflict, fields });
  }
  return asked;
}

// ---- Permanent links -----------------------------------------------------------

/** Why a staged link may join the wrong pair: the review asks for a second
 * tick for any of them. */
export type LinkMismatch =
  | { kind: "amount"; difference: string }
  /** The movement is in one currency and the invoice in another. */
  | { kind: "currency"; movement: string; invoice: string }
  | { kind: "counterparty" }
  | { kind: "linked_elsewhere"; count: number };

function exact(text: string): { units: bigint; scale: number } | null {
  const found = /^(\d+)(?:\.(\d+))?$/.exec(text.trim());
  if (!found) return null;
  const fraction = found[2] ?? "";
  return { units: BigInt(`${found[1]}${fraction}`), scale: fraction.length };
}
/** The magnitude of `left` minus `right`, in canonical spelling. */
export function decimalDistance(left: string, right: string): string | null {
  const a = exact(left);
  const b = exact(right);
  if (!a || !b) return null;
  const scale = Math.max(a.scale, b.scale);
  const units =
    a.units * 10n ** BigInt(scale - a.scale) -
    b.units * 10n ** BigInt(scale - b.scale);
  const magnitude = (units < 0n ? -units : units)
    .toString()
    .padStart(scale + 1, "0");
  const whole = magnitude.slice(0, magnitude.length - scale);
  const fraction = magnitude.slice(magnitude.length - scale);
  return canonicalDecimal(fraction ? `${whole}.${fraction}` : whole);
}

const LEGAL_FORMS = /\b(s\.?l\.?u?|s\.?a\.?|s\.?coop|sll|slp|cb|scp)\b\.?/g;
const party = (text: string) =>
  fold(text)
    .replace(LEGAL_FORMS, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

export function linkMismatches(
  row: LedgerRow,
  invoice: CatalogueInvoice,
): LinkMismatch[] {
  const found: LinkMismatch[] = [];
  const total = invoice.grand_total.decimal;
  const movementCurrency = row.transaction.currency.trim().toUpperCase();
  const invoiceCurrency = invoice.currency.trim().toUpperCase();
  // Amounts in two currencies have no difference to state.
  if (movementCurrency !== invoiceCurrency)
    found.push({
      kind: "currency",
      movement: movementCurrency,
      invoice: invoiceCurrency,
    });
  else if (compareDecimal(row.transaction.amount, total) !== 0) {
    const difference = decimalDistance(row.transaction.amount, total);
    if (difference !== null) found.push({ kind: "amount", difference });
  }
  const mine = party(
    row.transaction.counterparty || row.transaction.description,
  );
  const theirs = party(invoice.counterparty_name);
  if (mine && theirs && !mine.includes(theirs) && !theirs.includes(mine))
    found.push({ kind: "counterparty" });
  const elsewhere = invoice.linked_transaction_ids.filter(
    (id) => id !== row.transaction.transaction_id,
  ).length;
  if (elsewhere > 0) found.push({ kind: "linked_elsewhere", count: elsewhere });
  return found;
}

// ---- Ticks and outcomes ------------------------------------------------------

export type LinkTicks = Record<string, { sure: boolean; differ: boolean }>;

/** Whether every permanent link to be sent is ticked, and a second time
 * where its two sides differ. */
export function linksReady(
  links: readonly { id: string; mismatches: readonly LinkMismatch[] }[],
  ticks: LinkTicks,
): boolean {
  return links.every(
    (link) =>
      ticks[link.id]?.sure === true &&
      (link.mismatches.length === 0 || ticks[link.id]?.differ === true),
  );
}

/** How many movements, new movements and actions came to each outcome. */
export function outcomeTally(
  reports: readonly StepReport[],
): Partial<Record<StepOutcome["kind"], number>> {
  const tally: Partial<Record<StepOutcome["kind"], number>> = {};
  const add = (kind: StepOutcome["kind"]) => {
    tally[kind] = (tally[kind] ?? 0) + 1;
  };
  for (const report of reports) {
    if (report.step.kind === "bulk")
      for (const row of report.rows) add(row.outcome.kind);
    else add(report.outcome.kind);
  }
  return tally;
}

// ---- New movements in the grid --------------------------------------------------

/** A new movement drawn as a grid row: nothing filled in is assumed, and its
 * cells are drawn from the draft itself, never from these blanks. */
export function draftRow(draft: Draft): LedgerRow {
  const fields = draft.fields;
  return {
    transaction: {
      transaction_id: draft.key,
      date: fields.value_date ?? fields.booked_date ?? "",
      booked_date: fields.booked_date ?? "",
      value_date: fields.value_date ?? null,
      amount: fields.amount ?? "",
      currency: fields.currency ?? "",
      direction: fields.direction ?? "",
      counterparty: fields.counterparty ?? "",
      description: fields.description ?? "",
      business_classification: fields.business_classification ?? "",
      business_pct: fields.business_pct ?? null,
      category_id: fields.category_id ?? null,
      taxable_base: fields.taxable_base ?? null,
      iva_rate: fields.iva_rate ?? null,
      iva_amount: fields.iva_amount ?? null,
      iva_category: fields.iva_category ?? null,
      counterparty_country: null,
      counterparty_identification_state: null,
      irpf_category: fields.irpf_category ?? null,
      m210_income_classification: null,
      usage_ratio_id: null,
      prorrata_reference: null,
      purchase_invoice_evidence_id: null,
      invoice_id: null,
      attachment_ids: [],
      notes: fields.notes ?? "",
      lifecycle_state: "ACTIVE",
      classified_by: "",
      classified_at: null,
      classification_reason: "",
      classification_confidence: null,
      source_jurisdiction: null,
      value_in_eur: null,
      fx_rate: null,
      created_at: "",
      modified_at: "",
    },
    review_status: "pending",
    group_label: null,
    own_account_id: fields.own_account_id ?? null,
  };
}

/** The fields a new movement still needs before it can be added. */
export const DRAFT_REQUIRED: readonly DraftField[] = [
  "booked_date",
  "amount",
  "currency",
  "direction",
  "description",
];
export const draftMissing = (draft: Draft): DraftField[] =>
  DRAFT_REQUIRED.filter((field) => !draft.fields[field]);
