import { useMemo } from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { NativeSelect } from "@/components/ui/native-select";
import { useStrings } from "../../../shell/strings";
import { ASSET_KEYS } from "./assetsWords";

/** The offered year next to `value` in `options`, already sorted: the nearest
 * one before or after it, which is the first or last where nothing is chosen
 * or the choice is not offered. Null where there is none. */
function neighbour(
  options: readonly number[],
  value: number | null,
  by: -1 | 1,
): number | null {
  if (by < 0) {
    for (let at = options.length - 1; at >= 0; at -= 1) {
      const year = options[at]!;
      if (value === null || year < value) return year;
    }
    return null;
  }
  for (const year of options) if (value === null || year > value) return year;
  return null;
}

/**
 * One dropdown of years with a step either side. It offers only the years it
 * is given and imposes no bounds of its own: a year the person may not use is
 * the backend's to refuse. The list may span decades, and no year can be typed.
 */
export function YearStepper({
  value,
  years,
  onChange,
  className,
}: {
  /** The chosen year; null while none is, or while it is not offered. */
  value: number | null;
  /** The years on offer, in any order. */
  years: readonly number[];
  onChange: (year: number) => void;
  className?: string;
}) {
  const t = useStrings();
  const options = useMemo(
    () => [...new Set(years)].sort((a, b) => a - b),
    [years],
  );
  const chosen = value !== null && options.includes(value) ? value : null;
  const before = neighbour(options, value, -1);
  const after = neighbour(options, value, 1);
  return (
    <div
      role="group"
      aria-label={t(ASSET_KEYS.year)}
      className={cn("flex shrink-0 items-center gap-0.5", className)}
    >
      <IconButton
        label={t("desktop.ledger.period.year_previous")}
        disabled={before === null}
        onClick={() => before !== null && onChange(before)}
      >
        <Icon name="back" />
      </IconButton>
      <NativeSelect
        controlSize="sm"
        aria-label={t(ASSET_KEYS.year)}
        className="min-w-20 tabular-nums"
        disabled={options.length === 0}
        value={chosen ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        {chosen === null && <option value="" hidden />}
        {options.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </NativeSelect>
      <IconButton
        label={t("desktop.ledger.period.year_next")}
        disabled={after === null}
        onClick={() => after !== null && onChange(after)}
      >
        <Icon name="forward" />
      </IconButton>
    </div>
  );
}
