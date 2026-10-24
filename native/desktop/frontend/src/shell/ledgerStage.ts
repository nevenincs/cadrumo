// The changes the person has staged on the Ledger page and not yet saved:
// field changes per movement, new movements, and actions. They live in this
// reducer's state only, never in storage, and nothing is written until an
// apply. The page draws stored values; the effective row here exists to
// check a staged change against the others before anything is sent.

import type {
  LedgerAddRequest,
  LedgerClassifyRequest,
  LedgerDecision,
  LedgerRow,
} from "./ledger";
import { sameDecimal } from "./ledgerGrammar";

/** Every movement field the page can stage a change to. */
export const STAGE_FIELDS = [
  "booked_date",
  "value_date",
  "amount",
  "direction",
  "currency",
  "counterparty",
  "description",
  "group_label",
  "own_account_id",
  "business_classification",
  "business_pct",
  "category_id",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "notes",
  "deduction_fact_kind",
  "investment_asset_id",
  "counterparty_country",
  "counterparty_identification_state",
] as const;
export type StageField = (typeof STAGE_FIELDS)[number];

const DECIMAL_FIELDS: ReadonlySet<StageField> = new Set([
  "amount",
  "business_pct",
  "taxable_base",
  "iva_rate",
  "iva_amount",
]);

/** A staged value: a canonical value to set, or a clear. A blank paste is
 * neither: it stages nothing. */
export type StagedValue = { kind: "set"; value: string } | { kind: "clear" };
export type StagedRowChanges = Partial<Record<StageField, StagedValue>>;

/** The fields a new movement can carry when it is added. */
export type DraftField = Exclude<
  keyof LedgerAddRequest,
  "actor" | "idempotency_key" | "attachment_ids"
>;
/** A new movement. Its idempotency key is drawn once and kept until the add
 * settles, so an add sent again after an unknown outcome is the same add. */
export type Draft = {
  key: string;
  idempotencyKey: string;
  fields: Partial<Record<DraftField, string>>;
};

export type M210Options = NonNullable<LedgerClassifyRequest["m210"]>;
export type LifecycleKind = "archive" | "stash" | "restore" | "exclude";
/** An action on one or more movements, each sent through its own
 * operation. */
export type StagedAction =
  | { id: string; kind: LifecycleKind; transactionId: string; reason: string }
  | { id: string; kind: "link"; transactionId: string; invoiceId: string }
  | {
      id: string;
      kind: "attach";
      transactionId: string;
      evidenceId: string | null;
      attachmentIds: string[];
    }
  | {
      id: string;
      kind: "detach";
      transactionId: string;
      attachmentIds: string[];
    }
  | {
      id: string;
      kind: "split";
      transactionId: string;
      children: { amount: string; description: string }[];
      reason: string;
    }
  | { id: string; kind: "merge"; childIds: string[]; reason: string }
  | { id: string; kind: "remove"; transactionId: string; reason: string }
  | {
      /** The answer to a model's suggestion: the pending review of
       * `ledger.classify.review`, bound to the digest the page showed. */
      id: string;
      kind: "suggestion";
      transactionId: string;
      operationId: string;
      reviewDigest: string;
      decision: LedgerDecision;
      reason: string;
    }
  | {
      id: string;
      kind: "m210";
      transactionId: string;
      options: M210Options;
    }
  | {
      /** The stored rules run over the ledger through `ledger.rule.apply`:
       * on every movement still to classify, and with `reaffirm` on those
       * a rule classified too. The rules decide at the apply; the
       * movements its dry run named are kept for showing it and for
       * checking it against staged classifications only. */
      id: string;
      kind: "rule_apply";
      reaffirm: boolean;
      transactionIds: string[];
    };
export type StagedActionKind = StagedAction["kind"];

/** The movements an action names. */
export function actionRows(action: StagedAction): string[] {
  // The rules decide their movements at the apply, anywhere in the ledger.
  if (action.kind === "rule_apply") return [];
  return action.kind === "merge" ? action.childIds : [action.transactionId];
}

export type StagedContent = {
  rows: Record<string, StagedRowChanges>;
  drafts: Draft[];
  actions: StagedAction[];
};

/** What an undo step undoes, for the page to say. */
export type StageLabel =
  | "set"
  | "clear"
  | "paste"
  | "fill"
  | "bulk_set"
  | "revert_cell"
  | "revert_movement"
  | "discard"
  | "add_draft"
  | "edit_draft"
  | "remove_draft"
  | "stage_action"
  | "drop_action";
export type StageHistoryEntry = { content: StagedContent; label: StageLabel };

export type StageState = {
  content: StagedContent;
  undo: StageHistoryEntry[];
  redo: StageHistoryEntry[];
  /** An apply cleared the history: undo has nothing saved to take back. */
  applied: boolean;
};

/** One cell staged. `stored` is the field's stored value, null when it is
 * empty and undefined when the read does not show it. */
export type StageCell = {
  id: string;
  field: StageField;
  value: StagedValue;
  stored: string | null | undefined;
};

/** What the apply leaves staged: refused, unknown and not-sent work. */
export type StageKeep = {
  rows: Record<string, StageField[]>;
  drafts: string[];
  actions: string[];
};

export type StageEvent =
  | { type: "stage"; label: StageLabel; cells: StageCell[] }
  | { type: "revert_cell"; id: string; field: StageField }
  | { type: "revert_movement"; id: string; keepActions?: boolean }
  | { type: "add_draft"; draft: Draft }
  | { type: "edit_draft"; key: string; field: DraftField; value: string | null }
  | { type: "remove_draft"; key: string }
  | { type: "stage_action"; action: StagedAction }
  | { type: "drop_action"; id: string }
  | { type: "discard" }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "apply_started" }
  | { type: "rebase"; keep: StageKeep }
  | { type: "rekey"; from: string; to: string };

/** How many undo steps are kept. */
export const STAGE_HISTORY_LIMIT = 300;

export const EMPTY_CONTENT: StagedContent = {
  rows: {},
  drafts: [],
  actions: [],
};
export const EMPTY_STAGE: StageState = {
  content: EMPTY_CONTENT,
  undo: [],
  redo: [],
  applied: false,
};

/** Whether staging `value` over `stored` would change nothing. */
export function unchangedBy(
  field: StageField,
  stored: string | null | undefined,
  value: StagedValue,
): boolean {
  if (stored === undefined) return false;
  if (value.kind === "clear") return stored === null;
  if (stored === null) return false;
  return DECIMAL_FIELDS.has(field)
    ? sameDecimal(stored, value.value)
    : stored === value.value;
}

function committed(
  state: StageState,
  content: StagedContent,
  label: StageLabel,
): StageState {
  if (content === state.content) return state;
  return {
    content,
    undo: [...state.undo, { content: state.content, label }].slice(
      -STAGE_HISTORY_LIMIT,
    ),
    redo: [],
    applied: false,
  };
}

function withoutField(
  rows: Record<string, StagedRowChanges>,
  id: string,
  field: StageField,
): Record<string, StagedRowChanges> {
  const changes = rows[id];
  if (!changes || !(field in changes)) return rows;
  const rest = { ...changes };
  delete rest[field];
  const next = { ...rows };
  if (Object.keys(rest).length) next[id] = rest;
  else delete next[id];
  return next;
}

export function reduceStage(state: StageState, event: StageEvent): StageState {
  const content = state.content;
  switch (event.type) {
    case "stage": {
      let rows = content.rows;
      for (const cell of event.cells) {
        if (unchangedBy(cell.field, cell.stored, cell.value)) {
          rows = withoutField(rows, cell.id, cell.field);
          continue;
        }
        const current = rows[cell.id]?.[cell.field];
        if (
          current &&
          current.kind === cell.value.kind &&
          (current.kind === "clear" ||
            (cell.value.kind === "set" && current.value === cell.value.value))
        )
          continue;
        rows = {
          ...rows,
          [cell.id]: { ...rows[cell.id], [cell.field]: cell.value },
        };
      }
      return rows === content.rows
        ? state
        : committed(state, { ...content, rows }, event.label);
    }
    case "revert_cell": {
      const rows = withoutField(content.rows, event.id, event.field);
      return rows === content.rows
        ? state
        : committed(state, { ...content, rows }, "revert_cell");
    }
    case "revert_movement": {
      const actions = event.keepActions
        ? content.actions
        : content.actions.filter(
            (action) => !actionRows(action).includes(event.id),
          );
      if (
        !(event.id in content.rows) &&
        actions.length === content.actions.length
      )
        return state;
      const rows = { ...content.rows };
      delete rows[event.id];
      return committed(state, { ...content, rows, actions }, "revert_movement");
    }
    case "add_draft":
      return committed(
        state,
        { ...content, drafts: [event.draft, ...content.drafts] },
        "add_draft",
      );
    case "edit_draft": {
      const draft = content.drafts.find((found) => found.key === event.key);
      if (!draft || (draft.fields[event.field] ?? null) === event.value)
        return state;
      const fields = { ...draft.fields };
      if (event.value === null) delete fields[event.field];
      else fields[event.field] = event.value;
      // The key stays: an add that may have reached the ledger keeps its
      // name, and a changed add under the same name is refused, not doubled.
      return committed(
        state,
        {
          ...content,
          drafts: content.drafts.map((found) =>
            found === draft ? { ...draft, fields } : found,
          ),
        },
        "edit_draft",
      );
    }
    case "remove_draft": {
      const drafts = content.drafts.filter((draft) => draft.key !== event.key);
      return drafts.length === content.drafts.length
        ? state
        : committed(state, { ...content, drafts }, "remove_draft");
    }
    case "stage_action":
      return committed(
        state,
        {
          ...content,
          actions: [
            ...content.actions.filter(
              (action) => action.id !== event.action.id,
            ),
            event.action,
          ],
        },
        "stage_action",
      );
    case "drop_action": {
      const actions = content.actions.filter(
        (action) => action.id !== event.id,
      );
      return actions.length === content.actions.length
        ? state
        : committed(state, { ...content, actions }, "drop_action");
    }
    case "discard":
      return stagedCount(content) === 0
        ? state
        : committed(state, EMPTY_CONTENT, "discard");
    case "undo": {
      const last = state.undo[state.undo.length - 1];
      if (!last) return state;
      return {
        ...state,
        content: last.content,
        undo: state.undo.slice(0, -1),
        redo: [...state.redo, { content, label: last.label }],
      };
    }
    case "redo": {
      const next = state.redo[state.redo.length - 1];
      if (!next) return state;
      return {
        ...state,
        content: next.content,
        redo: state.redo.slice(0, -1),
        undo: [...state.undo, { content, label: next.label }],
      };
    }
    case "apply_started":
      // What an apply saves cannot be unstaged here.
      return { content, undo: [], redo: [], applied: true };
    case "rebase":
      return {
        content: keptContent(content, event.keep),
        undo: [],
        redo: [],
        applied: true,
      };
    case "rekey":
      return event.from === event.to
        ? state
        : { ...state, content: rekeyContent(content, event.from, event.to) };
  }
}

function keptContent(content: StagedContent, keep: StageKeep): StagedContent {
  const rows: Record<string, StagedRowChanges> = {};
  for (const [id, fields] of Object.entries(keep.rows)) {
    const changes = content.rows[id];
    if (!changes) continue;
    const kept: StagedRowChanges = {};
    for (const field of fields)
      if (changes[field]) kept[field] = changes[field];
    if (Object.keys(kept).length) rows[id] = kept;
  }
  return {
    rows,
    drafts: content.drafts.filter((draft) => keep.drafts.includes(draft.key)),
    actions: content.actions.filter((action) =>
      keep.actions.includes(action.id),
    ),
  };
}

/** Follows a movement's new id everywhere it is named. */
function rekeyContent(
  content: StagedContent,
  from: string,
  to: string,
): StagedContent {
  const rows = { ...content.rows };
  const moved = rows[from];
  if (moved) {
    delete rows[from];
    rows[to] = { ...moved, ...rows[to] };
  }
  const swap = (id: string) => (id === from ? to : id);
  return {
    rows,
    drafts: content.drafts,
    actions: content.actions.map((action) =>
      action.kind === "merge"
        ? { ...action, childIds: action.childIds.map(swap) }
        : action.kind === "rule_apply"
          ? { ...action, transactionIds: action.transactionIds.map(swap) }
          : { ...action, transactionId: swap(action.transactionId) },
    ),
  };
}

/** How many changes are staged: cells, new movements and actions. */
export function stagedCount(content: StagedContent): number {
  let cells = 0;
  for (const changes of Object.values(content.rows))
    cells += Object.keys(changes).length;
  return cells + content.drafts.length + content.actions.length;
}

/** The movements with anything staged on them. */
export function stagedMovements(content: StagedContent): Set<string> {
  const ids = new Set(Object.keys(content.rows));
  for (const action of content.actions)
    for (const id of actionRows(action)) ids.add(id);
  return ids;
}

/** A movement field as the read shows it: null when empty, undefined when
 * the read does not carry it. */
export function storedFieldValue(
  row: LedgerRow,
  field: StageField,
): string | null | undefined {
  const t = row.transaction;
  switch (field) {
    case "group_label":
      return row.group_label;
    case "own_account_id":
    case "deduction_fact_kind":
    case "investment_asset_id":
      return undefined;
    case "counterparty":
    case "notes":
      return t[field] === "" ? null : t[field];
    default:
      return t[field];
  }
}

export type MovementFacts = Record<StageField, string | null | undefined>;

/** The movement as it would be once its staged changes are saved. The page
 * draws the stored row; this is for checking staged changes only. */
export function effectiveFacts(
  row: LedgerRow,
  changes: StagedRowChanges | undefined,
): MovementFacts {
  const facts = {} as MovementFacts;
  for (const field of STAGE_FIELDS) {
    const change = changes?.[field];
    facts[field] = change
      ? change.kind === "set"
        ? change.value
        : null
      : storedFieldValue(row, field);
  }
  return facts;
}

/** The fields whose change gives a movement a new id: its amount, its
 * description, its effective date and its own account. A booked date
 * behind a value date is not its effective date. */
export function changesIdentity(
  row: LedgerRow,
  changes: StagedRowChanges | undefined,
): StageField[] {
  if (!changes) return [];
  const before = effectiveFacts(row, undefined);
  const after = effectiveFacts(row, changes);
  const found: StageField[] = [];
  if (changes.amount && !sameDecimal(after.amount ?? "", before.amount ?? ""))
    found.push("amount");
  if (changes.description && after.description !== before.description)
    found.push("description");
  const effective = (facts: MovementFacts) =>
    facts.value_date ?? facts.booked_date ?? null;
  if (
    (changes.booked_date || changes.value_date) &&
    effective(after) !== effective(before)
  )
    found.push(changes.value_date ? "value_date" : "booked_date");
  if (changes.own_account_id) found.push("own_account_id");
  return found;
}

/** A fresh, unguessable idempotency key for a new movement. */
export function newIdempotencyKey(
  random: (bytes: Uint8Array<ArrayBuffer>) => Uint8Array = (bytes) =>
    crypto.getRandomValues(bytes),
): string {
  const bytes = random(new Uint8Array(16));
  return `desktop-add-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

/** A new movement with nothing filled in: no direction, no account, no
 * classification is assumed. */
export function newDraft(
  random?: (bytes: Uint8Array<ArrayBuffer>) => Uint8Array,
): Draft {
  const idempotencyKey = newIdempotencyKey(random);
  return {
    key: `draft-${idempotencyKey.slice(-12)}`,
    idempotencyKey,
    fields: {},
  };
}
