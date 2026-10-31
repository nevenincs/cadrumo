import { useCallback } from "react";
import { CodeEditor, type SecretProps } from "@/components/editors/CodeEditor";
import type { EditorProps } from "@/components/editors/editorProps";
import { countryName } from "@/shared/codeNames";
import { useStrings } from "@/shell/strings";

/** A two-letter country code, typed, and shown with its name in the window's
 * language. Which codes are offered is served: pass them as `suggestions`. */
export function CountryEditor(editor: EditorProps & SecretProps) {
  const locale = useStrings().locale ?? "en";
  const shown = useCallback(
    (code: string) => {
      const name = countryName(locale, code);
      return name ? `${code} · ${name}` : code;
    },
    [locale],
  );
  return <CodeEditor {...editor} shown={shown} />;
}
