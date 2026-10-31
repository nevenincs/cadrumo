import { CodeEditor, type SecretProps } from "@/components/editors/CodeEditor";
import type {
  EditorProps,
  SuggestionProps,
} from "@/components/editors/editorProps";
import { ibanGroups } from "@/shared/iban";

/** An account number: held in capitals with no spaces, shown in groups of four.
 * The host checks it with `ibanProblem`. */
export function IbanEditor(
  editor: Omit<EditorProps, keyof SuggestionProps> & SecretProps,
) {
  return <CodeEditor {...editor} shown={ibanGroups} />;
}
