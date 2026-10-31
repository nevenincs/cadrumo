import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { decimalReading } from "@/components/editors/numberReading";
import { cn } from "@/components/ui/cn";
import { useStrings } from "@/shell/strings";

/** A whole number, typed in the window's marks. It holds digits as text; a
 * fraction stays as typed for the model to refuse. */
export function IntegerEditor({ className, ...editor }: EditorProps) {
  const locale = useStrings().locale ?? "en";
  const reading = useMemo(() => {
    const decimal = decimalReading(locale);
    return {
      ...decimal,
      read(typed: string) {
        const held = decimal.read(typed);
        return held !== null && /^-?\d*$/.test(held) ? held : null;
      },
    };
  }, [locale]);
  return (
    <EntryInput
      inputMode="numeric"
      {...editor}
      reading={reading}
      className={cn("text-right tabular-nums", className)}
    />
  );
}
