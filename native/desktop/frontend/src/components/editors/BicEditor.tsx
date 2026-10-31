import { CodeEditor, type SecretProps } from "@/components/editors/CodeEditor";
import type { EditorProps } from "@/components/editors/editorProps";

/** A bank's SWIFT/BIC code: capitals and no spaces. */
export function BicEditor(editor: EditorProps & SecretProps) {
  return <CodeEditor {...editor} />;
}
