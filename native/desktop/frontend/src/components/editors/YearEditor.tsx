import { EntryInput, PLAIN_READING } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { cn } from "@/components/ui/cn";

/** A year: four digits as text, never grouped. The model checks it with
 * `parseYear` and sends the number where the contract takes one. */
export function YearEditor({ className, ...editor }: EditorProps) {
  return (
    <EntryInput
      inputMode="numeric"
      {...editor}
      reading={PLAIN_READING}
      className={cn("tabular-nums", className)}
    />
  );
}
