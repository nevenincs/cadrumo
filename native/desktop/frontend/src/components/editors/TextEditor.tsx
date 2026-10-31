import type { EditorProps } from "@/components/editors/editorProps";
import { cn } from "@/components/ui/cn";
import { Input } from "@/components/ui/input";

/** One line of free text. Text has nothing to read, so `mode` changes nothing:
 * the value is what was typed, and the model checks it. */
export function TextEditor({
  value,
  onChange,
  id,
  invalid,
  describedBy,
  disabled,
  controlSize,
  maxLength,
  mono,
  type = "text",
  autoComplete = "off",
}: EditorProps & {
  maxLength?: number;
  mono?: boolean;
  type?: "text" | "email" | "tel" | "url";
  autoComplete?: string;
}) {
  return (
    <Input
      id={id}
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      controlSize={controlSize}
      disabled={disabled}
      maxLength={maxLength}
      autoComplete={autoComplete}
      spellCheck={false}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={cn(mono && "font-mono")}
    />
  );
}
