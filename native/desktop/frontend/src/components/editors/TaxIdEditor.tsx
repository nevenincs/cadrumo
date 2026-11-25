import { CodeEditor } from "@/components/editors/CodeEditor";
import type { EditorProps } from "@/components/editors/editorProps";

/** A tax id: capitals and no spaces. Whether it is a real one is the backend's
 * to say, so it checks nothing here. */
export function TaxIdEditor(editor: EditorProps) {
  return <CodeEditor {...editor} />;
}
