// How one stored movement's field becomes an inspector field: what it
// shows, the stored value a staged change replaces, why it cannot change,
// how it is edited, and the cells a new value stages. The values are read
// and refused in the grid's own grammar, so the inspector and the grid
// stage the same thing for the same typing.

import type { ComboboxOption } from "@/components/ui/combobox";
import type { Suggestion } from "@/components/ui/suggestions";
import type { LedgerRow } from "../../../shell/ledger";
import { parseFractionPercent } from "../../../shell/ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StageEvent,
  type StageField,
  type StagedRowChanges,
} from "../../../shell/ledgerStage";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import type { Translate } from "../../../shell/strings";
import { heldDecimal } from "../../../shared/numbers";
import {
  clearRefusal,
  parseCell,
  rowCells,
  type CellParse,
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
import type { ServedVocabulary } from "../../../shell/ledgerServedVocabulary";
import type {
  FieldControl,
  FieldEditor,
  FieldParse,
  FieldSuggest,
} from "./InspectorField";
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

const CONTROL_OF: Partial<Record<FieldKind, FieldControl>> = {
  date: "date",
  amount: "money",
  figure: "money",
  percent: "percent",
  country: "country",
  currency: "currency",
};
/** What the page's records offer as a field is typed in. A group label is a
 * short list, so it opens before anything is typed. */
const OFFERED: Partial<Record<StageField, FieldSuggest>> = {
  description: { kind: "description" },
  counterparty: { kind: "counterparty" },
  counterparty_country: { kind: "country" },
  counterparty_identification_state: { kind: "state" },
  currency: { kind: "currency" },
  group_label: { kind: "group", opensEmpty: true },
  investment_asset_id: { kind: "investment_asset" },
};
const COUNTRY = /^[A-Z]{2}$/;
const CURRENCY = /^[A-Z]{3}$/;

/** A stored value as its editor holds it: a decimal in the spelling the
 * editor reads back. */
function heldAs(kind: FieldKind, stored: string): string {
  return CONTROL_OF[kind] === "money" || CONTROL_OF[kind] === "percent"
    ? heldDecimal(stored)
    : stored;
}

/** What typing in the editor of `kind` stages. A percent editor holds the
 * fraction the product stores, so it is read as one. */
function parseEntry(
  kind: EditKind,
  field: StageField,
  raw: string,
  labels: Parameters<typeof parseCell>[3],
): CellParse {
  if (kind !== "percent") return parseCell(kind, field, raw, labels);
  const fraction = parseFractionPercent(raw);
  return fraction.kind === "value"
    ? { kind: "value", value: { value: fraction.value } }
    : fraction;
}

export type FieldScope = {
  t: Translate;
  locale: string;
  row: LedgerRow;
  changes: StagedRowChanges | undefined;
  /** A finalized declaration cites the movement. */
  sealed: boolean;
  /** What the ledger answers cannot change on the movement as staged; null
   * until it has answered about this movement. */
  transferLocked: readonly string[] | null;
  accounts: readonly OwnAccountChoice[] | null;
  /** The registry's lists, once served; empty until then. */
  vocabulary: ServedVocabulary;
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
  const { t, row, sealed, transferLocked } = scope;
  const state = row.transaction.lifecycle_state;
  if (state !== "ACTIVE")
    return lockText(t, { kind: "not_active", lifecycle: state });
  if (sealed) return lockText(t, { kind: "sealed" });
  if (transferLocked === null) return t("desktop.ledger.apply.reading");
  if (transferLocked.includes(field)) return lockText(t, { kind: "transfer" });
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

/** A field the backend serves a closed list for, worded from that list. While
 * the list cannot be read the field stays typed, and the backend still decides.
 * A stored value outside the list stays on offer, so it is never lost. */
export function servedChoiceField(
  scope: FieldScope,
  field: StageField,
  options: readonly { value: string; label: string }[] | null,
): InspectorFieldProps {
  const base = stagedField(scope, field, "token");
  if (options === null) return base;
  const { t, row, changes } = scope;
  const current = effectiveFacts(row, changes)[field] ?? null;
  const stored = storedFieldValue(row, field);
  const word = (value: string) =>
    options.find((option) => option.value === value)?.label ?? value;
  const held = new Set(
    [current, stored].filter(
      (value): value is string =>
        !!value && !options.some((option) => option.value === value),
    ),
  );
  return {
    ...base,
    ...(current ? { shown: word(current) } : {}),
    ...(base.was != null && stored ? { was: word(stored) } : {}),
    editor: {
      kind: "choice",
      value: current,
      options: [
        ...[...held].map((value) => ({ value, label: value })),
        ...options,
      ],
      ...(clearRefusal(field) === null
        ? { clear: t("desktop.ledger.inspector.clear") }
        : {}),
    },
  };
}

/** The inspector field for one movement field. `onPick` is called when a
 * suggestion is chosen, to fill the fields beside it. */
export function stagedField(
  scope: FieldScope,
  field: StageField,
  kind: FieldKind,
  onPick?: (picked: Suggestion) => void,
): InspectorFieldProps {
  const { t, row, changes, accounts, vocabulary, onStage } = scope;
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
      editor = choice(categoryOptions(t, vocabulary), clear);
      break;
    case "iva_category":
      editor = choice(ivaCategoryOptions(t, vocabulary), clear);
      break;
    case "irpf_category":
      editor = choice(irpfCategoryOptions(t, vocabulary), clear);
      break;
    case "account":
      editor = choice(
        accountOptions(accounts ?? []),
        accountLabel(t, accounts, null),
      );
      break;
    default: {
      const labels = choiceLabels(t, accounts, vocabulary);
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
        const parsed = parseEntry(kind, field, raw, labels);
        if (parsed.kind === "refused")
          return {
            kind: "refused",
            message: refusalText(t, parsed.refusal),
            ...(parsed.refusal.suggestion
              ? { suggestion: parsed.refusal.suggestion }
              : {}),
          };
        if (parsed.kind === "empty") return { kind: "clear" };
        return { kind: "value", value: parsed.value.value };
      };
      const offered = OFFERED[field];
      editor = {
        kind: "input",
        control: CONTROL_OF[kind] ?? "text",
        initial: current == null ? "" : heldAs(kind, current),
        parse,
        ...(offered
          ? { suggest: { ...offered, ...(onPick ? { onPick } : {}) } }
          : {}),
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
