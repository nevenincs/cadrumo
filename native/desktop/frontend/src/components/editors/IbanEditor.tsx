import { CodeEditor, type SecretProps } from "@/components/editors/CodeEditor";
import type { EditorProps } from "@/components/editors/editorProps";
import { ibanGroups } from "@/shared/iban";

/** An account number: held in capitals with no spaces, shown in groups of four.
 * The host checks it with `ibanProblem`. */
export function IbanEditor(editor: EditorProps & SecretProps) {
  return <CodeEditor {...editor} shown={ibanGroups} />;
}
