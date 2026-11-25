import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import { EntrySuffix, suffixRoom } from "@/components/editors/EntrySuffix";
import type { EditorProps } from "@/components/editors/editorProps";
import { decimalReading } from "@/components/editors/numberReading";
import { cn } from "@/components/ui/cn";
import { currencyMark, formatDecimal, writtenPlaces } from "@/shared/numbers";
import { useStrings } from "@/shell/strings";

/**
 * An amount, typed in the window's marks and shown to `decimals` places, two by
 * default. It holds plain decimal text. More digits than `decimals` are shown
 * whole, never rounded, for the model to refuse. Seed a stored value through
 * `heldDecimal`. Where the amount's currency is known, `currency` writes its
 * mark at the box's end, as `%` stands beside a percentage; it is not typed
 * and not held.
 */
export function MoneyEditor({
  decimals = 2,
  currency,
  className,
  ...editor
}: EditorProps & { decimals?: number; currency?: string }) {
  const locale = useStrings().locale ?? "en";
  const reading = useMemo(
    () =>
      decimalReading(locale, (value) =>
        formatDecimal(locale, value, {
          minFraction: Math.max(writtenPlaces(value), decimals),
        }),
      ),
    [locale, decimals],
  );
  const mark = currency ? currencyMark(locale, currency) : null;
  const input = (
    <EntryInput
      inputMode="decimal"
      {...editor}
      reading={reading}
      className={cn(
        mark !== null && suffixRoom(mark),
        "text-right tabular-nums",
        className,
      )}
    />
  );
  return mark === null ? (
    input
  ) : (
    <EntrySuffix mark={mark} slot="money-editor">
      {input}
    </EntrySuffix>
  );
}
