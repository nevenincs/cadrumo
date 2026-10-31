import { TextEditor } from "@/components/editors/TextEditor";
import { TypedField } from "@/components/editors/TypedField";
import type { FieldSpec } from "@/shared/fieldKind";
import { profileInput } from "../../shell/profileInput";
import type { ProfileField } from "../../shell/userProfile";

const SPECS: Readonly<Record<string, FieldSpec>> = {
  date: { kind: "date" },
  integer: { kind: "integer" },
  decimal: { kind: "decimal" },
  money: { kind: "money" },
  tax_id: { kind: "taxId" },
};

/** The editor a profile detail is entered in, by what the detail holds. The
 * value is the canonical text the profile saves, or the text typed while it
 * is not yet readable. */
export function ProfileValueEditor({
  field,
  value,
  onChange,
  ...rest
}: {
  field: ProfileField;
  value: string;
  onChange(value: string): void;
  id: string;
  disabled: boolean;
  required?: boolean;
  invalid?: boolean;
  describedBy?: string;
  onBlur?(): void;
}) {
  const { name, autoComplete, kind, type } = profileInput(field);
  const spec = SPECS[kind];
  if (spec)
    return (
      <TypedField
        field={spec}
        {...rest}
        name={name}
        value={value}
        onChange={onChange}
      />
    );
  return (
    <TextEditor
      {...rest}
      name={name}
      value={value}
      onChange={onChange}
      type={type}
      autoComplete={autoComplete}
      maxLength={4096}
    />
  );
}
