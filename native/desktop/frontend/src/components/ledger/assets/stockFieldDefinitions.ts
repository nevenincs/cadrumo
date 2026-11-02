import type { SuggestionProps } from "@/components/editors/editorProps";
import type { ProofSlotKey } from "./stockVocabulary";

// ---- The fields a form draws -------------------------------------------------

export type FieldControl =
  "text" | "choice" | "money" | "quantity" | "share" | "date";

/** One field of a form: what it is called, how it is typed and whether the
 * request cannot be made without it. A field's key is where its text and its
 * problem are kept; no field names a reference the window mints. */
export type StockField = {
  key: string;
  label: string;
  hint?: string;
  control: FieldControl;
  required: boolean;
  /** The text the field offers as it is typed in, where the form holds any. */
  offers?: SuggestionProps;
};

export const BOOK_FIELDS: readonly StockField[] = [
  {
    key: "name",
    label: "desktop.ledger.stock.field.name",
    hint: "desktop.ledger.stock.field.name_hint",
    control: "text",
    required: true,
  },
  {
    key: "method",
    label: "desktop.ledger.inventory.method_label",
    control: "choice",
    required: true,
  },
  {
    key: "opening",
    label: "desktop.ledger.inventory.opening",
    control: "money",
    required: true,
  },
];

/** What every movement states. */
export const MOVEMENT_FIELDS: readonly StockField[] = [
  {
    key: "date",
    label: "desktop.ledger.inventory.date",
    control: "date",
    required: true,
  },
  {
    key: "kind",
    label: "desktop.ledger.inventory.kind_label",
    control: "choice",
    required: true,
  },
  {
    key: "quantity",
    label: "desktop.ledger.inventory.quantity",
    control: "quantity",
    required: true,
  },
];

/** What a movement other than a purchase can state about its cost. */
export const COST_FIELDS: readonly StockField[] = [
  {
    key: "unit_cost",
    label: "desktop.ledger.inventory.unit_cost",
    hint: "desktop.ledger.stock.field.cost_hint",
    control: "money",
    required: false,
  },
  {
    key: "total_cost",
    label: "desktop.ledger.stock.field.total_cost",
    control: "money",
    required: false,
  },
];

/** What a purchase states about its price. */
export const PRICE_FIELDS: readonly StockField[] = [
  {
    key: "price",
    label: "desktop.ledger.stock.field.price",
    control: "money",
    required: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.field.iva",
    control: "money",
    required: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.field.share",
    control: "share",
    required: true,
  },
];

/** What each extra cost of a purchase states. */
export const EXTRA_FIELDS: readonly StockField[] = [
  {
    key: "kind",
    label: "desktop.ledger.stock.extra.kind",
    control: "choice",
    required: true,
  },
  {
    key: "price",
    label: "desktop.ledger.stock.extra.price",
    control: "money",
    required: true,
  },
  {
    key: "iva",
    label: "desktop.ledger.stock.extra.iva",
    control: "money",
    required: true,
  },
  {
    key: "share",
    label: "desktop.ledger.stock.extra.share",
    control: "share",
    required: true,
  },
];

/** What a change to a book's details states. */
export const DESCRIBE_FIELDS: readonly StockField[] = [
  {
    key: "label",
    label: "desktop.ledger.stock.field.label",
    hint: "desktop.ledger.stock.field.label_hint",
    control: "text",
    required: true,
  },
  {
    key: "description",
    label: "desktop.ledger.stock.field.description",
    control: "text",
    required: false,
  },
];

/** The reason every correction and reversal states. */
export const REASON_FIELD: StockField = {
  key: "reason",
  label: "desktop.ledger.stock.field.reason",
  control: "choice",
  required: true,
};

/** What a correction of the opening stock or the method states. */
export const CORRECT_FIELDS: readonly StockField[] = [
  REASON_FIELD,
  {
    key: "opening",
    label: "desktop.ledger.stock.field.opening_new",
    hint: "desktop.ledger.stock.field.keep_hint",
    control: "money",
    required: false,
  },
  {
    key: "method",
    label: "desktop.ledger.stock.field.method_new",
    control: "choice",
    required: false,
  },
];

/** A file the purchase rests on. */
export type ProofSlot = {
  key: ProofSlotKey;
  label: string;
  hint?: string;
};

export const PROOF_SLOTS: readonly ProofSlot[] = [
  { key: "price", label: "desktop.ledger.stock.proof.price" },
  {
    key: "cost_check",
    label: "desktop.ledger.stock.proof.cost_check",
    hint: "desktop.ledger.stock.proof.check_hint",
  },
  {
    key: "iva_check",
    label: "desktop.ledger.stock.proof.iva_check",
    hint: "desktop.ledger.stock.proof.check_hint",
  },
];

/** What a closing value states. */
export const CLOSING_FIELDS: readonly StockField[] = [
  {
    key: "authority",
    label: "desktop.ledger.stock.closing.authority",
    control: "choice",
    required: true,
  },
  {
    key: "reason",
    label: "desktop.ledger.stock.closing.reason",
    hint: "desktop.ledger.stock.closing.reason_hint",
    control: "text",
    required: true,
  },
];

/** What a count states, when the closing value is the count's. */
export const COUNT_FIELDS: readonly StockField[] = [
  {
    key: "observed_on",
    label: "desktop.ledger.stock.closing.counted_on",
    control: "date",
    required: true,
  },
  {
    key: "closing_value",
    label: "desktop.ledger.stock.closing.value",
    control: "money",
    required: true,
  },
  {
    key: "basis",
    label: "desktop.ledger.stock.closing.basis",
    control: "choice",
    required: true,
  },
];
