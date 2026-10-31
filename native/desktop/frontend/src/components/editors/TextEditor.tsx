import type { EditorProps } from "@/components/editors/editorProps";
import { EntryInput } from "@/components/editors/EntryInput";
import { cn } from "@/components/ui/cn";

const PLAIN = {
  read: (typed: string) => typed,
  shown: (value: string) => value,
  typed: (value: string) => value,
};

/** One line of free text. Text has nothing to read, so `mode` changes nothing:
 * the value is what was typed, and the model checks it. */
export function TextEditor({
  mono,
  type = "text",
  className,
  ...editor
}: EditorProps & {
  mono?: boolean;
  type?: "text" | "email" | "tel" | "url";
}) {
  return (
    <EntryInput
      {...editor}
      reading={PLAIN}
      type={type}
      className={cn(mono && "font-mono", className)}
    />
  );
}
