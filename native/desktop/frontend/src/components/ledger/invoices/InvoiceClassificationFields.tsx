import { NotesEditor } from "@/components/editors/NotesEditor";
import { NativeSelect } from "@/components/ui/native-select";
import { OPERATION_TYPES } from "../../../shell/ledgerContract";
import { useStrings } from "../../../shell/strings";
import { ivaCategoryLabel } from "../movements/movementWords";
import { ServedOptions } from "../suggestions/ServedOptions";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { FormField, wired } from "./InvoiceFields";

export function IvaCategoryField({
  value,
  onChange,
  unset,
}: {
  value: string;
  onChange(value: string): void;
  unset: string;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  return (
    <FormField label={t("desktop.ledger.invoices.field.iva_category")}>
      {(control) => (
        <NativeSelect
          {...control}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{unset}</option>
          <ServedOptions
            values={vocabulary.ivaCategories}
            stored={value}
            label={(category) => ivaCategoryLabel(t, category)}
          />
        </NativeSelect>
      )}
    </FormField>
  );
}

export function OperationTypeField({
  value,
  onChange,
}: {
  value: string;
  onChange(value: string): void;
}) {
  const t = useStrings();
  return (
    <FormField label={t("desktop.ledger.invoices.field.operation_type")}>
      {(control) => (
        <NativeSelect
          {...control}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">{t("desktop.ledger.invoices.none")}</option>
          {OPERATION_TYPES.map((key) => (
            <option key={key} value={key}>
              {t("desktop.ledger.invoices.operation_key", { key })}
            </option>
          ))}
        </NativeSelect>
      )}
    </FormField>
  );
}

export function NotesField({
  value,
  onChange,
}: {
  value: string;
  onChange(value: string): void;
}) {
  const t = useStrings();
  return (
    <FormField label={t("desktop.ledger.invoices.field.notes")}>
      {(control) => (
        <NotesEditor
          {...wired(control)}
          rows={3}
          value={value}
          onChange={onChange}
        />
      )}
    </FormField>
  );
}
