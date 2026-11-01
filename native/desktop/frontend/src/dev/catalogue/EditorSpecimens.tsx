import { useMemo, useState } from "react";
import { TypedField } from "@/components/editors/TypedField";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import type { Suggestion } from "@/components/ui/suggestions";
import { Specimen } from "@/dev/catalogue/Frame";
import type { FieldSpec } from "@/shared/fieldKind";
import { StringsContext, translator, useStrings } from "@/shell/strings";

const LOCALES = ["en", "es", "ca", "hu"];

/** The list a field offers, worded in the window's language. */
export type Offers = (locale: string) => readonly Suggestion[];

/** Codes as the ledger offers them: each noted with its name in the language. */
export const namedCodes =
  (
    codes: readonly string[],
    name: (locale: string, code: string) => string | null,
  ): Offers =>
  (locale) =>
    codes.map((code) => ({
      value: code,
      label: code,
      note: name(locale, code) ?? undefined,
    }));

function Held({
  id,
  field,
  label,
  initial,
  error,
  disabled,
  offers,
}: {
  id: string;
  field: FieldSpec;
  label: string;
  initial: string;
  error?: string;
  disabled?: boolean;
  offers?: Offers;
}) {
  const [value, setValue] = useState(initial);
  const locale = useStrings().locale ?? "en";
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <TypedField
        id={id}
        field={field}
        value={value}
        onChange={setValue}
        suggestions={offers?.(locale)}
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
  offers,
}: {
  field: FieldSpec;
  label: string;
  filled: string;
  invalid: string;
  error: string;
  /** What a field offers for typing, where the kind has a served list. */
  offers?: Offers;
}) {
  return (
    <div className="max-w-80">
      <Specimen title="Empty" className="grid">
        <Held
          id="empty"
          field={field}
          label={label}
          initial=""
          offers={offers}
        />
      </Specimen>
      <Specimen title="Filled" className="grid">
        <Held
          id="filled"
          field={field}
          label={label}
          initial={filled}
          offers={offers}
        />
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Held
          id="invalid"
          field={field}
          label={label}
          initial={invalid}
          error={error}
          offers={offers}
        />
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Held
          id="disabled"
          field={field}
          label={label}
          initial={filled}
          disabled
          offers={offers}
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
              offers={offers}
            />
          </InLocale>
        </Specimen>
      ))}
    </div>
  );
}
