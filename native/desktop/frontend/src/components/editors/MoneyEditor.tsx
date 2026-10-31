import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import { decimalReading } from "@/components/editors/numberReading";
import { cn } from "@/components/ui/cn";
import { formatDecimal } from "@/shared/numbers";
import { useStrings } from "@/shell/strings";

/**
 * An amount, typed in the window's marks and shown to `decimals` places, two by
 * default. It holds plain decimal text. More digits than `decimals` are shown
 * whole, never rounded, for the model to refuse. Seed a stored value through
 * `heldDecimal`.
 */
export function MoneyEditor({
  decimals = 2,
  className,
  ...editor
}: EditorProps & { decimals?: number }) {
  const locale = useStrings().locale ?? "en";
  const reading = useMemo(
    () =>
      decimalReading(locale, (value) => {
        const typed = value.replace(/0+$/, "").split(".")[1]?.length ?? 0;
        const places = value.includes(".") ? typed : 0;
        return formatDecimal(
          locale,
          value,
          places > decimals ? {} : { minFraction: decimals },
        );
      }),
    [locale, decimals],
  );
  return (
    <EntryInput
      inputMode="decimal"
      {...editor}
      reading={reading}
      className={cn("text-right tabular-nums", className)}
    />
  );
}
