// How staged editing says what it does: why a value was refused, why a cell
// takes no edit, a field's name and a value before and after, in the chrome
// language and the product's terms. Nothing here decides anything.

import type { DraftField, StageField } from "../../../shell/ledgerStage";
import type { Translate } from "../../../shell/strings";
import type { ColumnId } from "../movements/movementsModel";
import {
  accountLabel,
  amountText,
  categoryLabel,
  classificationLabel,
  dateText,
  directionLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
  lifecycleLabel,
  percentText,
} from "../movements/movementWords";
import type { ChoiceLabels, EditRefusal, LockReason } from "./editingModel";

/** A refused value, said with what was typed and what it most likely
 * meant. */
export function refusalText(t: Translate, refusal: EditRefusal): string {
  return t(`desktop.ledger.edit.refusal.${refusal.key}`, {
    raw: refusal.raw,
    suggestion: refusal.suggestion ?? "",
    limit: refusal.limit ?? "",
  });
}

/** Why a cell takes no edit. */
export function lockText(t: Translate, lock: LockReason): string {
  if (lock.kind === "not_active")
    return t("desktop.ledger.edit.lock.not_active", {
      state: lifecycleLabel(t, lock.lifecycle),
    });
  return t(`desktop.ledger.edit.lock.${lock.kind}`);
}

/** The column a field is shown in, where it has one. */
const FIELD_COLUMN: Partial<Record<StageField | DraftField, ColumnId>> = {
  booked_date: "date",
  value_date: "date",
  amount: "amount",
  direction: "direction",
  counterparty: "counterparty",
  description: "description",
  group_label: "group_label",
  business_classification: "classification",
  category_id: "category",
  taxable_base: "taxable_base",
  iva_rate: "iva_rate",
  iva_amount: "iva_amount",
  iva_category: "iva_category",
  irpf_category: "irpf_category",
  notes: "notes",
};

/** A field's name: its column's where it has one. */
export function fieldName(
  t: Translate,
  field: StageField | DraftField,
): string {
  if (field === "booked_date" || field === "value_date")
    return t(`desktop.ledger.field.${field}`);
  const column = FIELD_COLUMN[field];
  return column
    ? t(`desktop.ledger.column.${column}`)
    : t(`desktop.ledger.field.${field}`);
}

const PERCENT: ReadonlySet<string> = new Set(["business_pct", "iva_rate"]);
const FIGURES: ReadonlySet<string> = new Set([
  "amount",
  "taxable_base",
  "iva_amount",
  "recargo_amount",
]);

/** A field's value as the review writes it: figures grouped, shares as
 * percentages, dates with their year, enums by label. Empty says so. */
export function valueText(
  t: Translate,
  locale: string,
  field: StageField | DraftField,
  value: string | null,
): string {
  if (value === null || value === "") return t("desktop.ledger.edit.empty");
  if (FIGURES.has(field)) return amountText(locale, value);
  if (PERCENT.has(field)) return percentText(locale, value);
  switch (field) {
    case "booked_date":
    case "value_date":
      return dateText(locale, value, true);
    case "direction":
      return directionLabel(t, value);
    case "business_classification":
      return classificationLabel(t, value);
    case "category_id":
      return categoryLabel(t, value);
    case "iva_category":
      return ivaCategoryLabel(t, value);
    case "irpf_category":
      return irpfCategoryLabel(t, value);
    default:
      return value;
  }
}

/** The labels a pasted choice may be written in. */
export function choiceLabels(
  t: Translate,
  accounts: readonly { id: string; label: string }[] | null,
): ChoiceLabels & {
  mixedShare: (share: string) => string;
} {
  return {
    account: (id) => accountLabel(t, accounts, id),
    accounts: (accounts ?? []).map((account) => account.id),
    noAccount: accountLabel(t, accounts, null),
    direction: (token) => directionLabel(t, token),
    classification: (token) => classificationLabel(t, token),
    category: (id) => categoryLabel(t, id),
    ivaCategory: (id) => ivaCategoryLabel(t, id),
    irpfCategory: (id) => irpfCategoryLabel(t, id),
    mixedShare: (share) =>
      t("desktop.ledger.classification.mixed_share", { share }),
  };
}
