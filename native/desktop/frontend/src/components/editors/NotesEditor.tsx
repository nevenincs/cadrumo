import type { EditorProps } from "@/components/editors/editorProps";
import { Textarea } from "@/components/ui/textarea";

/** Free text over several lines. Text has nothing to read, so `mode` changes
 * nothing: the value is what was typed, and the model checks it. */
export function NotesEditor({
  value,
  onChange,
  id,
  invalid,
  describedBy,
  disabled,
  controlSize,
  maxLength,
  rows,
}: EditorProps & { maxLength?: number; rows?: number }) {
  return (
    <Textarea
      id={id}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      controlSize={controlSize}
      disabled={disabled}
      maxLength={maxLength}
      rows={rows}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
    />
  );
}
