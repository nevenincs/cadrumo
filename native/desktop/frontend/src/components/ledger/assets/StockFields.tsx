import { useId } from "react";
import { DateEditor } from "@/components/editors/DateEditor";
import { DecimalEditor } from "@/components/editors/DecimalEditor";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { useStrings } from "../../../shell/strings";
import { ChoiceField, FormGrid } from "../setup/SetupParts";
import { grammarText } from "../setup/setupWords";
import type { StockField } from "./stockFieldDefinitions";
import type { Problems } from "./stockModel";

const FILL_IN = "desktop.ledger.assets.write.fill_in";

type Choices = Readonly<
  Record<string, readonly { value: string; label: string }[]>
>;

/** One field of a form, on the editor its kind of value has. */
function StockEntry({
  field,
  value,
  onValue,
  error,
  autoFocus,
}: {
  field: StockField;
  value: string;
  onValue(value: string): void;
  error: string | null;
  autoFocus: boolean;
}) {
  const t = useStrings();
  const id = useId();
  const hint = field.hint ? t(field.hint) : undefined;
  const describedBy =
    [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined;
  const editor = {
    id,
    name: field.key,
    value,
    onChange: onValue,
    invalid: error ? true : undefined,
    describedBy,
    required: field.required,
    autoFocus,
  };
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{t(field.label)}</FieldLabel>
      {field.control === "date" ? (
        <DateEditor {...editor} />
      ) : field.control === "money" ? (
        <MoneyEditor {...editor} />
      ) : field.control === "quantity" ? (
        <DecimalEditor {...editor} />
      ) : field.control === "share" ? (
        <PercentEditor {...editor} unit="fraction" />
      ) : (
        <TextEditor {...editor} {...field.offers} />
      )}
      {hint && <FieldDescription id={`${id}-hint`}>{hint}</FieldDescription>}
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </Field>
  );
}

/** The fields of a form, each drawn by its control. A refused value shows its
 * reason; one still to give shows so once the person has tried to send. */
export function StockFields({
  fields,
  valueOf,
  onValue,
  choices,
  problems,
  missing,
  tried,
  at = (field) => field.key,
  autoFocus = false,
}: {
  fields: readonly StockField[];
  valueOf(field: StockField): string;
  onValue(field: StockField, value: string): void;
  choices: Choices;
  problems: Problems;
  missing: ReadonlySet<string>;
  tried: boolean;
  /** Where a field's problem is kept. */
  at?: (field: StockField) => string;
  autoFocus?: boolean;
}) {
  const t = useStrings();
  return (
    <FormGrid>
      {fields.map((field, index) => {
        const key = at(field);
        const problem = problems[key];
        const fillIn = tried && missing.has(key);
        const error = problem
          ? grammarText(t, problem)
          : fillIn
            ? t(FILL_IN)
            : null;
        return (
          <div key={field.key} data-field={field.key} className="contents">
            {field.control === "choice" ? (
              <ChoiceField
                label={t(field.label)}
                value={valueOf(field)}
                onValue={(value) => onValue(field, value)}
                placeholder={
                  field.required ? t("desktop.ledger.form.choose") : undefined
                }
                hint={field.hint ? t(field.hint) : undefined}
                error={error}
                options={choices[field.key] ?? []}
              />
            ) : (
              <StockEntry
                field={field}
                value={valueOf(field)}
                onValue={(value) => onValue(field, value)}
                error={error}
                autoFocus={autoFocus && index === 0}
              />
            )}
          </div>
        );
      })}
    </FormGrid>
  );
}
