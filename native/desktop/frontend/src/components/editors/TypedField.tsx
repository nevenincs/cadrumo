import { BicEditor } from "@/components/editors/BicEditor";
import { CountryEditor } from "@/components/editors/CountryEditor";
import { CurrencyEditor } from "@/components/editors/CurrencyEditor";
import { DateEditor } from "@/components/editors/DateEditor";
import { DecimalEditor } from "@/components/editors/DecimalEditor";
import type {
  EditorProps,
  SuggestionProps,
} from "@/components/editors/editorProps";
import { IbanEditor } from "@/components/editors/IbanEditor";
import { IntegerEditor } from "@/components/editors/IntegerEditor";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { NotesEditor } from "@/components/editors/NotesEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { YearEditor } from "@/components/editors/YearEditor";
import { NativeSelect } from "@/components/ui/native-select";
import type { FieldSpec } from "@/shared/fieldKind";

/** The attributes every kind can take, a textarea and a select included. */
export type TypedFieldProps = Pick<
  EditorProps,
  | "value"
  | "onChange"
  | "id"
  | "name"
  | "invalid"
  | "required"
  | "describedBy"
  | "disabled"
  | "controlSize"
  | "mode"
  | "className"
  | "aria-label"
  | "autoFocus"
> & {
  field: FieldSpec;
  onBlur?(): void;
  /** Called when a kind that can be picked from has a value picked. */
  onPicked?(value: string): void;
} & SuggestionProps;

/** The one dispatch from a field's kind to its editor. */
export function TypedField({
  field,
  onBlur,
  onPicked,
  suggestions,
  onPick,
  onSuggestionsWanted,
  opensEmpty,
  commitsOnPick,
  mode,
  ...common
}: TypedFieldProps) {
  const blur = onBlur && (() => onBlur());
  const unoffered = { ...common, mode, onBlur: blur };
  const editor = {
    ...unoffered,
    suggestions,
    onPick,
    onSuggestionsWanted,
    opensEmpty,
    commitsOnPick,
  };
  switch (field.kind) {
    case "text":
      return (
        <TextEditor {...editor} mono={field.mono} maxLength={field.maxLength} />
      );
    case "notes":
      return (
        <NotesEditor {...common} onBlur={blur} maxLength={field.maxLength} />
      );
    case "date":
      return (
        <DateEditor
          {...editor}
          min={field.min}
          max={field.max}
          onPicked={onPicked}
        />
      );
    case "year":
      return <YearEditor {...editor} />;
    case "money":
      return <MoneyEditor {...editor} decimals={field.decimals} />;
    case "decimal":
      return <DecimalEditor {...editor} />;
    case "integer":
      return <IntegerEditor {...editor} />;
    case "percent":
      return <PercentEditor {...editor} unit={field.unit} />;
    case "taxId":
      return <TaxIdEditor {...editor} />;
    case "iban":
      return <IbanEditor {...unoffered} secret={field.secret} />;
    case "bic":
      return <BicEditor {...unoffered} secret={field.secret} />;
    case "country":
      return <CountryEditor {...editor} secret={field.secret} />;
    case "currency":
      return <CurrencyEditor {...editor} />;
    case "choice": {
      const { value, onChange, invalid, describedBy, required, ...select } =
        common;
      return (
        <NativeSelect
          {...select}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={blur}
          aria-invalid={invalid || undefined}
          aria-required={required || undefined}
          aria-describedby={describedBy}
        >
          {field.choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </NativeSelect>
      );
    }
  }
}
