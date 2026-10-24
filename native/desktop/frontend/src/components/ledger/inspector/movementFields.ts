// How one stored movement's field becomes an inspector field: what it
// shows, the stored value a staged change replaces, why it cannot change,
// how it is edited, and the cells a new value stages. The values are read
// and refused in the grid's own grammar, so the inspector and the grid
// stage the same thing for the same typing.

import type { ComboboxOption } from "@/components/ui/combobox";
import type { LedgerRow } from "../../../shell/ledger";
import { percentOf } from "../../../shell/ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StageEvent,
  type StageField,
  type StagedRowChanges,
} from "../../../shell/ledgerStage";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import type { Translate } from "../../../shell/strings";
import {
  clearRefusal,
  parseCell,
  rowCells,
  type EditKind,
} from "../editing/editingModel";
import {
  choiceLabels,
  fieldName,
  lockText,
  refusalText,
  valueText,
} from "../editing/editingWords";
import { accountLabel } from "../movements/movementWords";
import type { FieldEditor, FieldParse } from "./InspectorField";
import {
  accountOptions,
  categoryOptions,
  directionOptions,
  irpfCategoryOptions,
  ivaCategoryOptions,
} from "./inspectorWords";

/** How a field is edited in the inspector: the grid's kinds, and the
 * classification facts the grid has no column for. */
export type FieldKind = EditKind | "country" | "token" | "currency";

const TAX_FIELDS: ReadonlySet<StageField> = new Set([
  "category_id",
  "iva_category",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "irpf_category",
  "deduction_fact_kind",
  "investment_asset_id",
  "counterparty_identification_state",
]);
const COUNTRY = /^[A-Z]{2}$/;
const CURRENCY = /^[A-Z]{3}$/;

export type FieldScope = {
  t: Translate;
  locale: string;
  row: LedgerRow;
  changes: StagedRowChanges | undefined;
  /** A finalized declaration cites the movement. */
  sealed: boolean;
  accounts: readonly OwnAccountChoice[] | null;
  onStage: (event: StageEvent) => void;
};

export type InspectorFieldProps = {
  label: string;
  field: string;
  shown: string;
  was?: string | null;
  lock: string | null;
  editor?: FieldEditor;
  onCommit?: (value: string | null) => void;
};

/** Why `field` cannot change on the movement, or null. */
export function fieldLock(scope: FieldScope, field: StageField): string | null {
  const { t, row, changes, sealed } = scope;
  const state = row.transaction.lifecycle_state;
  if (state !== "ACTIVE")
    return lockText(t, { kind: "not_active", lifecycle: state });
  if (sealed) return lockText(t, { kind: "sealed" });
  if (
    TAX_FIELDS.has(field) &&
    effectiveFacts(row, changes).direction === "INTERNAL_TRANSFER"
  )
    return lockText(t, { kind: "transfer" });
  return null;
}

function shownValue(
  scope: FieldScope,
  field: StageField,
  value: string | null | undefined,
): string {
  const { t, locale, accounts } = scope;
  if (field === "own_account_id")
    return accountLabel(t, accounts, value ?? null);
  if (value === undefined) return t("desktop.ledger.inspector.not_read");
  if (
    value === null &&
    (field === "counterparty_country" ||
      field === "counterparty_identification_state")
  )
    return t("desktop.ledger.inspector.not_stated");
  if (value === null || value === "")
    return t("desktop.ledger.inspector.not_set");
  return valueText(t, locale, field, value);
}

/** The inspector field for one movement field. */
export function stagedField(
  scope: FieldScope,
  field: StageField,
  kind: FieldKind,
): InspectorFieldProps {
  const { t, row, changes, accounts, onStage } = scope;
  const id = row.transaction.transaction_id;
  const stored = storedFieldValue(row, field);
  const facts = effectiveFacts(row, changes);
  const current = facts[field];
  const staged = changes?.[field] !== undefined;
  const lock = fieldLock(scope, field);
  const clearable = clearRefusal(field) === null;
  const commit = (value: string | null) => {
    const cells = rowCells(id, row, field, value === null ? null : { value });
    onStage({ type: "stage", label: value === null ? "clear" : "set", cells });
  };
  const choice = (options: ComboboxOption[], clear?: string): FieldEditor => ({
    kind: "choice",
    value: current ?? null,
    options,
    ...(clearable && clear ? { clear } : {}),
  });
  const clear = t("desktop.ledger.inspector.clear");
  let editor: FieldEditor;
  switch (kind) {
    case "direction":
      editor = choice(directionOptions(t));
      break;
    case "category":
      editor = choice(categoryOptions(t), clear);
      break;
    case "iva_category":
      editor = choice(ivaCategoryOptions(t), clear);
      break;
    case "irpf_category":
      editor = choice(irpfCategoryOptions(t), clear);
      break;
    case "account":
      editor = choice(
        accountOptions(accounts ?? []),
        accountLabel(t, accounts, null),
      );
      break;
    default: {
      const labels = choiceLabels(t, accounts);
      const parse = (raw: string): FieldParse => {
        const text = raw.trim();
        if (text === "") {
          const refused = clearRefusal(field);
          return refused
            ? { kind: "refused", message: refusalText(t, refused) }
            : { kind: "clear" };
        }
        if (kind === "country" || kind === "currency") {
          const upper = text.toUpperCase();
          return (kind === "country" ? COUNTRY : CURRENCY).test(upper)
            ? { kind: "value", value: upper }
            : {
                kind: "refused",
                message:
                  kind === "country"
                    ? t("desktop.ledger.inspector.refused.country")
                    : t("desktop.ledger.inspector.refused.currency"),
              };
        }
        if (kind === "token")
          return text.length <= 128
            ? { kind: "value", value: text }
            : {
                kind: "refused",
                message: refusalText(t, {
                  key: "too_long",
                  raw,
                  limit: 128,
                }),
              };
        const parsed = parseCell(kind, field, raw, labels);
        if (parsed.kind === "refused")
          return { kind: "refused", message: refusalText(t, parsed.refusal) };
        if (parsed.kind === "empty") return { kind: "clear" };
        return { kind: "value", value: parsed.value.value };
      };
      const percent = kind === "percent";
      editor = {
        kind: "input",
        initial:
          current == null
            ? ""
            : percent
              ? (percentOf(current) ?? current)
              : current,
        parse,
        inputMode:
          kind === "amount" || kind === "figure" || percent
            ? "decimal"
            : "text",
      };
    }
  }
  return {
    label: fieldName(t, field),
    field,
    shown: shownValue(scope, field, current),
    ...(staged
      ? { was: stored == null ? null : shownValue(scope, field, stored) }
      : {}),
    lock,
    editor,
    onCommit: commit,
  };
}
