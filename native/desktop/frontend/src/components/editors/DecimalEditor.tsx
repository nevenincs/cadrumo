import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { decimalReading } from "@/components/editors/numberReading";
import { cn } from "@/components/ui/cn";
import { useStrings } from "@/shell/strings";

/** A quantity or other plain decimal, typed in the window's marks. It holds
 * plain decimal text and never rounds; the model's rule limits its digits.
 * Seed a stored value through `heldDecimal`. */
export function DecimalEditor({ className, ...editor }: EditorProps) {
  const locale = useStrings().locale ?? "en";
  const reading = useMemo(() => decimalReading(locale), [locale]);
  return (
    <EntryInput
      inputMode="decimal"
      {...editor}
      reading={reading}
      className={cn("text-right tabular-nums", className)}
    />
  );
}
