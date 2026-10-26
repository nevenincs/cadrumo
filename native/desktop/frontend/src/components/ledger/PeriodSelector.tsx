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
import {
  LEDGER_YEAR_MAX,
  LEDGER_YEAR_MIN,
  MONTH_CODES,
  QUARTER_CODES,
  stepPeriod,
  yearAdmitted,
  type LedgerPeriod,
  type LedgerPeriodCode,
} from "../../shell/ledgerGrammar";
import { useStrings } from "../../shell/strings";
import { monthNames, periodText } from "./ledgerWords";

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

/**
 * One dropdown for a period, any year the period grammar admits, with the
 * previous and next period beside it. Inside, the year is moved by its own
 * buttons, then a whole year, a quarter, a month or every period is chosen,
 * and the years that have movements jump the dropdown to themselves. In the
 * year mode only a year is chosen.
 */
export function PeriodSelector({
  value,
  onChange,
  label,
  years,
  locale,
  fallbackYear,
  mode = "period",
  allowAll = true,
  open: openProp,
  onOpenChange,
  className,
}: {
  /** The period shown; null is every period. */
  value: LedgerPeriod | null;
  onChange(next: LedgerPeriod | null): void;
  /** What the period is of, named for the group and its dropdown. */
  label: string;
  /** The years that have movements, as read from the ledger, or null while
   * they are not known. */
  years: readonly number[] | null;
  locale: string;
  /** The year the dropdown opens on while every period is shown. */
  fallbackYear: number;
  mode?: "period" | "year";
  allowAll?: boolean;
  open?: boolean;
  onOpenChange?(open: boolean): void;
  className?: string;
}) {
  const t = useStrings();
  const [ownOpen, setOwnOpen] = useState(false);
  const open = openProp ?? ownOpen;
  const setOpen = (next: boolean) => {
    setOwnOpen(next);
    onOpenChange?.(next);
  };
  const yearMode = mode === "year";
  const [shownYear, setShownYear] = useState(value?.year ?? fallbackYear);
  const content = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const shown = periodText(t, locale, value, mode);

  const step = (by: number) => {
    if (value === null) return;
    const next = yearMode
      ? yearAdmitted(value.year + by)
        ? { ...value, year: value.year + by }
        : null
      : stepPeriod(value, by);
    if (next) onChange(next);
  };
  const apply = (next: LedgerPeriod | null) => {
    onChange(next);
    setOpen(false);
  };
  const choose = (code: LedgerPeriodCode) =>
    apply({ year: shownYear, code: yearMode ? (value?.code ?? "0A") : code });
  const chosen = (code: LedgerPeriodCode) =>
    !yearMode && value?.code === code && value.year === shownYear;
  const months = monthNames(locale);
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
        disabled={value === null || (yearMode && value.year <= LEDGER_YEAR_MIN)}
        onClick={() => step(-1)}
      >
        <Icon name="back" />
      </IconButton>
      <Popover
        open={open}
        onOpenChange={(next) => {
          if (next) setShownYear(value?.year ?? fallbackYear);
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
              disabled={shownYear <= LEDGER_YEAR_MIN}
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
                aria-pressed={value?.year === shownYear}
                onClick={() => choose("0A")}
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
              disabled={shownYear >= LEDGER_YEAR_MAX}
              onClick={() => setShownYear((year) => year + 1)}
            >
              <Icon name="forward" />
            </IconButton>
          </div>
          {!yearMode && (
            <div
              role="group"
              aria-label={t("desktop.ledger.period.of_year", {
                year: shownYear,
              })}
              className="grid gap-2"
              onKeyDown={moveInGrid}
            >
              <div className="grid grid-cols-5 gap-1">
                <Button
                  variant="outline"
                  size="xs"
                  data-period-item=""
                  className="px-1"
                  aria-pressed={chosen("0A")}
                  onClick={() => choose("0A")}
                >
                  {t("desktop.ledger.period.year")}
                </Button>
                {QUARTER_CODES.map((code) => (
                  <Button
                    key={code}
                    variant="outline"
                    size="xs"
                    data-period-item=""
                    className={item}
                    aria-pressed={chosen(code)}
                    onClick={() => choose(code)}
                  >
                    {code}
                  </Button>
                ))}
              </div>
              <div className="grid grid-cols-4 gap-1">
                {MONTH_CODES.map((code, at) => (
                  <Button
                    key={code}
                    variant="ghost"
                    size="xs"
                    data-period-item=""
                    aria-pressed={chosen(code)}
                    onClick={() => choose(code)}
                  >
                    {months[at]}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {allowAll && !yearMode && (
            <Button
              variant="ghost"
              size="xs"
              className="ledger-period-all"
              aria-pressed={value === null}
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
                {t("desktop.ledger.period.years_with_movements")}
              </span>
              <div className="h-control-xs" />
            </div>
          ) : (
            years.length > 0 && (
              <div
                role="group"
                aria-label={t("desktop.ledger.period.years_with_movements")}
                className="grid gap-1"
              >
                <span
                  aria-hidden="true"
                  className="text-xs text-muted-foreground"
                >
                  {t("desktop.ledger.period.years_with_movements")}
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
                        yearMode
                          ? apply({ year, code: value?.code ?? "0A" })
                          : setShownYear(year)
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
        disabled={value === null || (yearMode && value.year >= LEDGER_YEAR_MAX)}
        onClick={() => step(1)}
      >
        <Icon name="forward" />
      </IconButton>
    </div>
  );
}
