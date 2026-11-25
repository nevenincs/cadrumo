import { useCallback } from "react";
import { CodeEditor } from "@/components/editors/CodeEditor";
import type { EditorProps } from "@/components/editors/editorProps";
import { currencyName } from "@/shared/codeNames";
import { useStrings } from "@/shell/strings";

/** A three-letter currency code, typed, and shown with its name in the window's
 * language. Which codes are offered is served: pass them as `suggestions`. */
export function CurrencyEditor(editor: EditorProps) {
  const locale = useStrings().locale ?? "en";
  const shown = useCallback(
    (code: string) => {
      const name = currencyName(locale, code);
      return name ? `${code} · ${name}` : code;
    },
    [locale],
  );
  return <CodeEditor {...editor} shown={shown} />;
}
