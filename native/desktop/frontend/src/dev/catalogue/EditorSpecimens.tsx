import { useMemo, useState } from "react";
import { TypedField } from "@/components/editors/TypedField";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Specimen } from "@/dev/catalogue/Frame";
import type { FieldSpec } from "@/shared/fieldKind";
import { StringsContext, translator } from "@/shell/strings";

const LOCALES = ["en", "es", "ca", "hu"];

function Held({
  id,
  field,
  label,
  initial,
  error,
  disabled,
}: {
  id: string;
  field: FieldSpec;
  label: string;
  initial: string;
  error?: string;
  disabled?: boolean;
}) {
  const [value, setValue] = useState(initial);
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <TypedField
        id={id}
        field={field}
        value={value}
        onChange={setValue}
        disabled={disabled}
        invalid={Boolean(error)}
        describedBy={error ? `${id}-error` : undefined}
      />
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </Field>
  );
}

function InLocale({
  locale,
  children,
}: {
  locale: string;
  children: React.ReactNode;
}) {
  const translate = useMemo(() => translator(locale), [locale]);
  return (
    <StringsContext.Provider value={translate}>
      {children}
    </StringsContext.Provider>
  );
}

/** One editor in every state a story must show: empty, filled, invalid,
 * disabled and in each language. */
export function EditorSpecimens({
  field,
  label,
  filled,
  invalid,
  error,
}: {
  field: FieldSpec;
  label: string;
  filled: string;
  invalid: string;
  error: string;
}) {
  return (
    <div className="max-w-80">
      <Specimen title="Empty" className="grid">
        <Held id="empty" field={field} label={label} initial="" />
      </Specimen>
      <Specimen title="Filled" className="grid">
        <Held id="filled" field={field} label={label} initial={filled} />
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Held
          id="invalid"
          field={field}
          label={label}
          initial={invalid}
          error={error}
        />
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Held
          id="disabled"
          field={field}
          label={label}
          initial={filled}
          disabled
        />
      </Specimen>
      {LOCALES.map((locale) => (
        <Specimen key={locale} title={locale} className="grid">
          <InLocale locale={locale}>
            <Held
              id={`in-${locale}`}
              field={field}
              label={label}
              initial={filled}
            />
          </InLocale>
        </Specimen>
      ))}
    </div>
  );
}
