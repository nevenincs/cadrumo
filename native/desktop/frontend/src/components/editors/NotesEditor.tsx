import type { NotesEditorProps } from "@/components/editors/editorProps";
import { Textarea } from "@/components/ui/textarea";

/** Free text over several lines. Text has nothing to read, so `mode` changes
 * nothing: the value is what was typed, and the model checks it. */
export function NotesEditor({
  value,
  onChange,
  invalid,
  required,
  describedBy,
  controlSize,
  ...native
}: NotesEditorProps) {
  return (
    <Textarea
      {...native}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      controlSize={controlSize}
      aria-invalid={invalid || undefined}
      aria-required={required || undefined}
      aria-describedby={describedBy}
    />
  );
}
