import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { yearAdmitted, type LedgerPeriod } from "../../shell/ledgerGrammar";
import {
  ledgerPeriod,
  neighbourPeriod,
  servedYear,
  usePeriods,
} from "../../shell/ledgerPeriods";
import type { LedgerServedPeriod } from "../../shell/ledgerSetup";
import { useStrings } from "../../shell/strings";
import { periodText } from "./ledgerWords";

const ARROWS: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

/** Arrow keys move between the items of the grid by where they are drawn:
 * along a row, or to the nearest item of the row above or below. */
function moveInGrid(event: KeyboardEvent<HTMLElement>) {
  const direction = ARROWS[event.key];
  if (!direction || event.altKey || event.ctrlKey || event.metaKey) return;
  const items = [
    ...event.currentTarget.querySelectorAll<HTMLElement>("[data-period-item]"),
  ];
  const at = items.indexOf(document.activeElement as HTMLElement);
  if (at < 0) return;
  event.preventDefault();
  const [across, down] = direction;
  if (down === 0) {
    items[Math.max(0, Math.min(items.length - 1, at + across))]?.focus();
    return;
  }
  const from = items[at]!.getBoundingClientRect();
  const centre = from.left + from.width / 2;
  const rows = items
    .map((element) => ({ element, box: element.getBoundingClientRect() }))
    .filter(({ box }) =>
      down > 0 ? box.top > from.top + 1 : box.top < from.top - 1,
    );
  if (rows.length === 0) return;
  const top =
    down > 0
      ? Math.min(...rows.map(({ box }) => box.top))
      : Math.max(...rows.map(({ box }) => box.top));
  const row = rows.filter(({ box }) => Math.abs(box.top - top) < 1);
  row
    .sort(
      (a, b) =>
        Math.abs(a.box.left + a.box.width / 2 - centre) -
        Math.abs(b.box.left + b.box.width / 2 - centre),
    )[0]
    ?.element.focus();
}

type SelectorProps = {
  /** What the period is of, named for the group and its dropdown. */
  label: string;
  /** The years that have movements, as read from the ledger, or null while
   * they are not known. */
  years: readonly number[] | null;
  /** The key of the words naming the years offered, where they are not the
   * years that have movements. */
  yearsKey?: string;
  locale: string;
  /** The year the dropdown opens on while every period is shown. */
  fallbackYear: number;
  open?: boolean;
  onOpenChange?(open: boolean): void;
  className?: string;
};

/**
 * One dropdown for a period, any year the period grammar admits, with the
 * previous and next period beside it. Inside, the year is moved by its own
 * buttons, then a whole year, a quarter, a month or every period is chosen,
 * and the years that have movements jump the dropdown to themselves. The
 * periods, their names and their neighbours are the backend's, served for
 * the year shown. In the year mode only a year is chosen.
 */
export function PeriodSelector(
  props: SelectorProps &
    (
      | {
          mode?: "period";
          /** The period shown; null is every period. */
          value: LedgerPeriod | null;
          onChange(next: LedgerPeriod | null): void;
          /** The period is not yet known: it is said to be being read, and
           * is not stepped from. */
          pending?: boolean;
          allowAll?: boolean;
        }
      | { mode: "year"; year: number; onYear(year: number): void }
    ),
) {
  const { label, years, locale, fallbackYear, onOpenChange, className } = props;
  const t = useStrings();
  const yearsWords = t(
    props.yearsKey ?? "desktop.ledger.period.years_with_movements",
  );
  const [ownOpen, setOwnOpen] = useState(false);
  const open = props.open ?? ownOpen;
  const setOpen = (next: boolean) => {
    setOwnOpen(next);
    onOpenChange?.(next);
  };
  const yearMode = props.mode === "year";
  const value = props.mode === "year" ? null : props.value;
  const chosenYear = props.mode === "year" ? props.year : (value?.year ?? null);
  const allowAll = props.mode === "year" ? false : (props.allowAll ?? true);
  const [shownYear, setShownYear] = useState(chosenYear ?? fallbackYear);
  const content = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  // The periods are the backend's: the year shown, and the one chosen.
  usePeriods({
    years: chosenYear === null ? [shownYear] : [shownYear, chosenYear],
  });
  const pending = props.mode !== "year" && props.pending === true;
  const shown =
    props.mode === "year"
      ? String(props.year)
      : pending
        ? t("desktop.ledger.form.reading")
        : periodText(t, locale, props.value);
  const table = servedYear(shownYear);
  const rowsOf = (kind: LedgerServedPeriod["kind"]) =>
    table?.filter((row) => row.kind === kind) ?? [];
  // The step either way: a year, or the neighbour the period serves.
  const steppedYear = (by: -1 | 1): number | null =>
    chosenYear !== null && yearAdmitted(chosenYear + by)
      ? chosenYear + by
      : null;
  const steppedPeriod = (by: -1 | 1): LedgerPeriod | null =>
    value === null || pending ? null : neighbourPeriod(value, by);
  const canStep = (by: -1 | 1) =>
    (yearMode ? steppedYear(by) : steppedPeriod(by)) !== null;
  const step = (by: -1 | 1) => {
    if (props.mode === "year") {
      const next = steppedYear(by);
      if (next !== null) props.onYear(next);
      return;
    }
    const next = steppedPeriod(by);
    if (next) props.onChange(next);
  };
  const apply = (next: LedgerPeriod | null) => {
    if (props.mode !== "year") props.onChange(next);
    setOpen(false);
  };
  const chooseYear = (year: number) => {
    if (props.mode === "year") props.onYear(year);
    setOpen(false);
  };
  const choose = (row: LedgerServedPeriod) => {
    const next = ledgerPeriod(row.period);
    if (next) apply(next);
  };
  const chosen = (row: LedgerServedPeriod) =>
    !pending &&
    value?.code === row.period.code &&
    value.year === row.period.filing_year;
  const item = "tabular-nums";

  return (
    <div
      role="group"
      aria-label={label}
      className={cn("flex shrink-0 items-center gap-0.5", className)}
    >
      <IconButton
        label={t(
          yearMode
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.previous",
        )}
        disabled={!canStep(-1)}
        onClick={() => step(-1)}
      >
        <Icon name="back" />
      </IconButton>
      <Popover
        open={open}
        onOpenChange={(next) => {
          if (next) setShownYear(chosenYear ?? fallbackYear);
          setOpen(next);
        }}
      >
        <PopoverTrigger asChild>
          <Button
            ref={trigger}
            variant="outline"
            size="xs"
            className="ledger-period gap-1 tabular-nums"
            aria-label={t("desktop.ledger.period.named", {
              label,
              period: shown,
            })}
          >
            {shown}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          ref={content}
          align="end"
          aria-label={t(
            yearMode
              ? "desktop.ledger.period.choose_year"
              : "desktop.ledger.period.choose",
          )}
          className="ledger-period-menu grid w-menu gap-3 p-2"
          // A choice can draw the page anew under the menu: the focus goes
          // back to the trigger as it is drawn now, never to the page.
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            requestAnimationFrame(() => trigger.current?.focus());
          }}
          onOpenAutoFocus={(event) => {
            // The chosen item takes focus, else the year, else the first.
            event.preventDefault();
            const root = content.current;
            (
              root?.querySelector<HTMLElement>(
                "[data-period-item][aria-pressed=true]",
              ) ?? root?.querySelector<HTMLElement>("[data-period-item]")
            )?.focus();
          }}
        >
          <div className="flex items-center gap-1">
            <IconButton
              label={t("desktop.ledger.period.year_previous")}
              disabled={!yearAdmitted(shownYear - 1)}
              onClick={() => setShownYear((year) => year - 1)}
            >
              <Icon name="back" />
            </IconButton>
            {yearMode ? (
              <Button
                variant="ghost"
                size="xs"
                data-period-item=""
                className="flex-1 font-semibold tabular-nums"
                aria-pressed={chosenYear === shownYear}
                onClick={() => chooseYear(shownYear)}
              >
                {shownYear}
              </Button>
            ) : (
              <span
                className="flex-1 text-center font-semibold text-foreground tabular-nums"
                aria-live="polite"
              >
                {shownYear}
              </span>
            )}
            <IconButton
              label={t("desktop.ledger.period.year_next")}
              disabled={!yearAdmitted(shownYear + 1)}
              onClick={() => setShownYear((year) => year + 1)}
            >
              <Icon name="forward" />
            </IconButton>
          </div>
          {!yearMode &&
            (table === null ? (
              // The row keeps its height while the year is read.
              <div
                className="ledger-period-reading h-control-xs"
                aria-hidden="true"
              />
            ) : (
              <div
                role="group"
                aria-label={t("desktop.ledger.period.of_year", {
                  year: shownYear,
                })}
                className="grid gap-2"
                onKeyDown={moveInGrid}
              >
                <div className="grid grid-cols-5 gap-1">
                  {rowsOf("annual").map((row) => (
                    <Button
                      key={row.period.code}
                      variant="outline"
                      size="xs"
                      data-period-item=""
                      className="px-1"
                      aria-pressed={chosen(row)}
                      onClick={() => choose(row)}
                    >
                      {row.name_words}
                    </Button>
                  ))}
                  {rowsOf("quarterly").map((row) => (
                    <Button
                      key={row.period.code}
                      variant="outline"
                      size="xs"
                      data-period-item=""
                      className={item}
                      aria-pressed={chosen(row)}
                      onClick={() => choose(row)}
                    >
                      {row.name_words}
                    </Button>
                  ))}
                </div>
                <div className="grid grid-cols-3 gap-1">
                  {rowsOf("monthly").map((row) => (
                    <Button
                      key={row.period.code}
                      variant="ghost"
                      size="xs"
                      data-period-item=""
                      aria-pressed={chosen(row)}
                      onClick={() => choose(row)}
                    >
                      {row.name_words}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          {allowAll && !yearMode && (
            <Button
              variant="ghost"
              size="xs"
              className="ledger-period-all"
              aria-pressed={!pending && value === null}
              onClick={() => apply(null)}
            >
              {t("desktop.ledger.period.all")}
            </Button>
          )}
          {/* The row keeps its height while the years are read, so the list
              does not grow under the pointer. */}
          {years === null ? (
            <div
              className="ledger-period-years-reading grid gap-1"
              aria-hidden="true"
            >
              <span className="text-xs text-muted-foreground">
                {yearsWords}
              </span>
              <div className="h-control-xs" />
            </div>
          ) : (
            years.length > 0 && (
              <div role="group" aria-label={yearsWords} className="grid gap-1">
                <span
                  aria-hidden="true"
                  className="text-xs text-muted-foreground"
                >
                  {yearsWords}
                </span>
                <div className="ledger-period-years flex flex-wrap gap-1">
                  {years.map((year) => (
                    <Button
                      key={year}
                      variant="pill"
                      size="xs"
                      className={item}
                      aria-pressed={year === shownYear}
                      onClick={() =>
                        yearMode ? chooseYear(year) : setShownYear(year)
                      }
                    >
                      {year}
                    </Button>
                  ))}
                </div>
              </div>
            )
          )}
        </PopoverContent>
      </Popover>
      <IconButton
        label={t(
          yearMode
            ? "desktop.ledger.period.year_next"
            : "desktop.ledger.period.next",
        )}
        disabled={!canStep(1)}
        onClick={() => step(1)}
      >
        <Icon name="forward" />
      </IconButton>
    </div>
  );
}
