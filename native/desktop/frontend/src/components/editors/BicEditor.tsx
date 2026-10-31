import { CodeEditor, type SecretProps } from "@/components/editors/CodeEditor";
import type {
  EditorProps,
  SuggestionProps,
} from "@/components/editors/editorProps";

/** A bank's SWIFT/BIC code: capitals and no spaces. */
export function BicEditor(
  editor: Omit<EditorProps, keyof SuggestionProps> & SecretProps,
) {
  return <CodeEditor {...editor} />;
}
