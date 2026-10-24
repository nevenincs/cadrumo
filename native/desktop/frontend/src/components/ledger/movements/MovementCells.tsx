import { memo, useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { DataGridText } from "@/components/ui/data-grid";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { LedgerRow } from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import {
  amountText,
  directionLabel,
  lifecycleLabel,
  statusLabel,
  statusWord,
  type StatusWord,
} from "./movementWords";

const STATUS_ICONS: Record<StatusWord, IconName> = {
  pending: "pending",
  needs_fixing: "alert",
  done: "check",
  skipped: "forward",
  excluded: "eyeOff",
};

/** The stored review status: a glyph and the count of what readiness
 * found, with the word shown only where the rows have room for it. A
 * movement that is not active carries its state as a badge. */
export const StatusCell = memo(function StatusCell({
  row,
  issues,
  wordy,
}: {
  row: LedgerRow;
  issues: number;
  wordy: boolean;
}) {
  const t = useStrings();
  const word = statusWord(row.review_status, issues);
  const label = statusLabel(t, word, issues);
  const state = row.transaction.lifecycle_state;
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <span
        data-status={word}
        className={cn(
          "inline-flex min-w-0 items-center gap-1",
          word === "needs_fixing" ? "text-foreground" : "text-muted-foreground",
        )}
      >
        <Icon
          name={STATUS_ICONS[word]}
          size="xs"
          className={cn(
            word === "needs_fixing" && "text-warning",
            word === "done" && "text-success",
          )}
        />
        {word === "needs_fixing" && (
          <span aria-hidden="true" className="tabular-nums">
            {issues}
          </span>
        )}
        {wordy ? (
          <span className="min-w-0 truncate">
            {word === "needs_fixing"
              ? t("desktop.ledger.status.needs_fixing")
              : label}
          </span>
        ) : (
          <span className="sr-only">{label}</span>
        )}
      </span>
      {state !== "ACTIVE" && <Badge>{lifecycleLabel(t, state)}</Badge>}
    </span>
  );
});

/** The direction, as an arrow and a word: never a sign on the amount. */
export const DirectionCell = memo(function DirectionCell({
  direction,
}: {
  direction: string;
}) {
  const t = useStrings();
  const icon: IconName =
    direction === "INCOMING"
      ? "directionIn"
      : direction === "OUTGOING"
        ? "directionOut"
        : "swap";
  return (
    <span className="inline-flex min-w-0 items-center gap-1">
      <Icon name={icon} size="xs" className="text-muted-foreground" />
      <span className="truncate">{directionLabel(t, direction)}</span>
    </span>
  );
});

/** A magnitude in the chrome language's grouping, with its currency where
 * it is not the euro. */
export const AmountCell = memo(function AmountCell({
  amount,
  currency,
  locale,
}: {
  amount: string;
  currency: string;
  locale: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1 tabular-nums">
      {amountText(locale, amount)}
      {currency !== "EUR" && (
        <span className="text-xs text-muted-foreground">{currency}</span>
      )}
    </span>
  );
});

/** The euro value of a foreign movement. Without a rate it is a refusal
 * that says so, never a zero. */
export const EuroCell = memo(function EuroCell({
  row,
  locale,
}: {
  row: LedgerRow;
  locale: string;
}) {
  const t = useStrings();
  const { currency, value_in_eur: euros } = row.transaction;
  if (currency === "EUR") return null;
  if (euros !== null)
    return <span className="tabular-nums">{amountText(locale, euros)}</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          data-no-rate=""
          className="inline-flex items-center gap-1 text-foreground"
        >
          <Icon name="noRate" size="xs" className="text-warning" />
          {t("desktop.ledger.no_rate")}
        </span>
      </TooltipTrigger>
      <TooltipContent>{t("desktop.ledger.no_rate_detail")}</TooltipContent>
    </Tooltip>
  );
});

/** Text that may not fit: the full text shows when it is cut short. Empty
 * text draws nothing. */
export const TextCell = memo(function TextCell({
  text,
  quiet = false,
}: {
  text: string | null;
  quiet?: boolean;
}) {
  if (!text) return null;
  return (
    <DataGridText className={quiet ? "text-muted-foreground" : undefined}>
      {text}
    </DataGridText>
  );
});

/** A count beside its icon, with what it counts in its name. */
export const CountCell = memo(function CountCell({
  icon,
  count,
  label,
}: {
  icon: IconName;
  count: number;
  label: string;
}) {
  if (count === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <Icon name={icon} size="xs" className="text-muted-foreground" />
      <span aria-hidden="true">{count}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
});

/**
 * The header's selection box. A click makes the shown movements the
 * selection; with Ctrl or Command it adds them to it. When every shown
 * movement is selected a plain click takes them out.
 */
export function SelectShownBox({
  label,
  extent,
  onSelect,
}: {
  label: string;
  /** How many of the shown movements are selected. */
  extent: "none" | "some" | "all";
  onSelect: (how: "replace" | "add" | "remove") => void;
}) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = extent === "some";
  }, [extent]);
  return (
    <Checkbox
      ref={box}
      tabIndex={-1}
      aria-label={label}
      checked={extent === "all"}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        event.preventDefault();
        const adding = event.ctrlKey || event.metaKey;
        onSelect(adding ? "add" : extent === "all" ? "remove" : "replace");
      }}
      onChange={() => undefined}
    />
  );
}
