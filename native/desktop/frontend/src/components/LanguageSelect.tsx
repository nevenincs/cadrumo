import { useId } from "react";
import { Field, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import { useStrings } from "../shell/strings";

export type LanguageControl = {
  value: string;
  languages: readonly string[];
  pending?: boolean;
  failed?: boolean;
  onChange: (language: string) => void;
};

function languageName(code: string): string {
  try {
    const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
    return name ? name.charAt(0).toLocaleUpperCase(code) + name.slice(1) : code;
  } catch {
    return code;
  }
}

export function LanguageSelect({
  value,
  languages,
  pending,
  failed,
  onChange,
}: LanguageControl) {
  const t = useStrings();
  const id = useId();
  return (
    <Field>
      <FieldLabel htmlFor={id}>{t("desktop.settings.language")}</FieldLabel>
      <NativeSelect
        id={id}
        controlSize="sm"
        value={value}
        disabled={pending}
        onChange={(event) => onChange(event.target.value)}
      >
        {languages.map((code) => (
          <option key={code} value={code} lang={code}>
            {languageName(code)}
          </option>
        ))}
      </NativeSelect>
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          {t("desktop.messages.failed", { code: "language_change_failed" })}
        </p>
      )}
    </Field>
  );
}
