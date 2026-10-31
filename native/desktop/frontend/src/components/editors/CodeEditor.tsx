import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { cn } from "@/components/ui/cn";
import { ibanText } from "@/shared/iban";

export type SecretProps = {
  /** Masks what is typed. A masked field shows nothing but the dots: no name
   * and no grouping. */
  secret?: boolean;
};

/**
 * What every code takes: capitals and no spaces, whatever was typed, in a
 * fixed-width face. `shown` draws a held code while the field is not being
 * typed in. The model checks the shape.
 */
export function CodeEditor({
  shown,
  secret,
  className,
  suggestions,
  onPick,
  onSuggestionsWanted,
  opensEmpty,
  commitsOnPick,
  ...editor
}: EditorProps & SecretProps & { shown?: (code: string) => string }) {
  const reading = useMemo(
    () => ({
      read: ibanText,
      shown: (code: string) => (secret || !shown ? code : shown(code)),
      typed: (code: string) => code,
    }),
    [secret, shown],
  );
  return (
    <EntryInput
      autoCapitalize="characters"
      {...editor}
      // A secret is never offered, whichever kind of code it is.
      {...(secret
        ? {}
        : {
            // A code typed out in full is answered: the names that merely
            // mention it are not offered over what follows the field.
            suggestions: suggestions?.some(
              (option) => option.value === editor.value.trim().toUpperCase(),
            )
              ? []
              : suggestions,
            onPick,
            onSuggestionsWanted,
            opensEmpty,
            commitsOnPick,
          })}
      type={secret ? "password" : "text"}
      reading={reading}
      className={cn("font-mono", className)}
    />
  );
}
