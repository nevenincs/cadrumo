import { useMemo } from "react";
import { EntryInput } from "@/components/editors/EntryInput";
import type { EditorProps } from "@/components/editors/editorProps";
import {
  decimalReading,
  isReadDecimal,
} from "@/components/editors/numberReading";
import { cn } from "@/components/ui/cn";
import { heldDecimal } from "@/shared/numbers";
import { shiftDecimal } from "@/shell/ledgerGrammar";
import { useStrings } from "@/shell/strings";

const SHIFT = { fraction: 2, points: 0 };

/**
 * A percentage. The person always types points, `21` or `21%`, beside a visible
 * `%`. `unit` is the field's contract and says what the value holds: a
 * `fraction`, where `0.21` is 21%, or `points`, where `21` is. The model checks
 * it with `parseFractionPercent` or `parsePoints`. In `lexeme` mode the text goes
 * as typed and `unit` is the backend's to apply.
 */
export function PercentEditor({
  unit,
  className,
  ...editor
}: EditorProps & { unit: "fraction" | "points" }) {
  const locale = useStrings().locale ?? "en";
  const reading = useMemo(() => {
    const points = decimalReading(locale);
    // Unread text is shown as it came, and never moved by the unit.
    const inPoints = (value: string, draw: (held: string) => string) => {
      if (!isReadDecimal(value)) return value;
      return draw(heldDecimal(shiftDecimal(value, SHIFT[unit]) ?? value));
    };
    return {
      read(typed: string) {
        const bare = typed.replace(/\s*%\s*$/, "");
        if (bare.trim() === "") return typed.trim() === "" ? "" : null;
        const held = points.read(bare);
        if (held === null) return null;
        const value = shiftDecimal(held, -SHIFT[unit]);
        return value === null ? null : heldDecimal(value);
      },
      shown: (value: string) => inPoints(value, points.shown),
      typed: (value: string) => inPoints(value, points.typed),
    };
  }, [locale, unit]);
  return (
    <div data-slot="percent-editor" className="relative">
      <EntryInput
        inputMode="decimal"
        {...editor}
        reading={reading}
        className={cn("pr-7 text-right tabular-nums", className)}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-muted-foreground"
      >
        %
      </span>
    </div>
  );
}
