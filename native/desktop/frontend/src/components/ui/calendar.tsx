import { ca } from "date-fns/locale/ca";
import { enUS } from "date-fns/locale/en-US";
import { es } from "date-fns/locale/es";
import { hu } from "date-fns/locale/hu";
import { useEffect, useRef, type ComponentProps } from "react";
import {
  DayPicker,
  getDefaultClassNames,
  type DayButton,
} from "react-day-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { dateFormats } from "@/shared/dateFormats";
import { isoDay, localDay } from "@/shared/dates";

const WEEKS = { en: enUS, es, ca, hu };

function weeksOf(locale: string) {
  const language = locale.split("-")[0] ?? "";
  return Object.hasOwn(WEEKS, language)
    ? WEEKS[language as keyof typeof WEEKS]
    : enUS;
}

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const readDay = (text: string | undefined) =>
  text !== undefined && ISO_DAY.test(text) ? isoDay(text) : undefined;

// How far the year list reaches around today, or around a day outside that. A
// picker's reach is no limit on what can be entered: dates can still be typed.
const YEARS_BACK = 100;
const YEARS_AHEAD = 10;

export type CalendarLabels = {
  previousMonth: string;
  nextMonth: string;
  month: string;
  year: string;
};

function CalendarChevron({
  orientation,
  className,
}: {
  orientation?: "up" | "down" | "left" | "right";
  className?: string;
}) {
  const name =
    orientation === "left"
      ? "back"
      : orientation === "right"
        ? "forward"
        : orientation === "up"
          ? "chevronUp"
          : "chevronDown";
  return <Icon name={name} className={className} />;
}

function CalendarDayButton({
  className,
  day,
  modifiers,
  ...props
}: ComponentProps<typeof DayButton>) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (modifiers.focused) ref.current?.focus();
  }, [modifiers.focused]);
  return (
    <Button
      ref={ref}
      data-day={localDay(day.date)}
      variant={modifiers.selected ? "primary" : "ghost"}
      size="icon-sm"
      className={cn("font-normal tabular-nums", className)}
      {...props}
    />
  );
}

/**
 * A month grid for choosing one day. It speaks ISO days at its edge: a local
 * date, which has no time for a zone to move, stays inside. Week start, month
 * and weekday names follow `locale`. Arrow keys move by day and week, Page keys
 * by month, Shift+Page by year, Home and End within the week.
 */
function Calendar({
  locale,
  value,
  onSelect,
  min,
  max,
  labels,
  className,
}: {
  locale: string;
  /** The chosen ISO day. Text that is no ISO day chooses nothing. */
  value: string;
  onSelect(iso: string): void;
  /** The first and last ISO day that can be chosen. */
  min?: string;
  max?: string;
  labels: CalendarLabels;
  className?: string;
}) {
  const named = dateFormats(locale);
  const defaults = getDefaultClassNames();
  const selected = readDay(value);
  const first = readDay(min);
  const last = readDay(max);
  const shown = selected ?? new Date();
  const year = shown.getFullYear();
  const thisYear = new Date().getFullYear();
  return (
    <DayPicker
      mode="single"
      required
      autoFocus
      showOutsideDays
      captionLayout="dropdown"
      locale={weeksOf(locale)}
      selected={selected}
      onSelect={(day: Date) => onSelect(localDay(day))}
      defaultMonth={shown}
      startMonth={
        first ?? new Date(Math.min(year, thisYear - YEARS_BACK), 0, 1)
      }
      endMonth={last ?? new Date(Math.max(year, thisYear + YEARS_AHEAD), 11, 1)}
      disabled={[
        ...(first ? [{ before: first }] : []),
        ...(last ? [{ after: last }] : []),
      ]}
      labels={{
        labelPrevious: () => labels.previousMonth,
        labelNext: () => labels.nextMonth,
        labelMonthDropdown: () => labels.month,
        labelYearDropdown: () => labels.year,
      }}
      formatters={{
        formatCaption: (month: Date) => named.month.format(month),
        formatMonthDropdown: (month: Date) => named.monthName.format(month),
        formatWeekdayName: (day: Date) => named.weekday.format(day),
      }}
      data-slot="calendar"
      className={cn("w-fit", className)}
      classNames={{
        root: cn("w-fit", defaults.root),
        months: cn("relative flex flex-col", defaults.months),
        month: cn("flex flex-col gap-2", defaults.month),
        nav: cn(
          "absolute inset-x-0 top-0 flex items-center justify-between",
          defaults.nav,
        ),
        button_previous: cn(
          buttonVariants({ variant: "ghost", size: "icon-sm" }),
          defaults.button_previous,
        ),
        button_next: cn(
          buttonVariants({ variant: "ghost", size: "icon-sm" }),
          defaults.button_next,
        ),
        month_caption: cn(
          "flex h-control-sm items-center justify-center px-8",
          defaults.month_caption,
        ),
        dropdowns: cn(
          "flex items-center justify-center gap-1 text-sm font-medium",
          defaults.dropdowns,
        ),
        dropdown_root: cn(
          "relative rounded-md has-focus:ring-2 has-focus:ring-ring",
          defaults.dropdown_root,
        ),
        dropdown: cn(
          "absolute inset-0 cursor-pointer bg-popover opacity-0",
          defaults.dropdown,
        ),
        caption_label: cn(
          "flex h-control-sm items-center gap-1 rounded-md px-1.5 text-sm font-medium select-none",
          defaults.caption_label,
        ),
        month_grid: cn("border-collapse", defaults.month_grid),
        weekdays: cn("flex", defaults.weekdays),
        weekday: cn(
          "w-control-sm text-center text-xs font-normal text-muted-foreground select-none",
          defaults.weekday,
        ),
        week: cn("mt-0.5 flex", defaults.week),
        day: cn("p-0 text-center select-none", defaults.day),
        today: cn("rounded-md font-semibold text-primary", defaults.today),
        outside: cn("text-muted-foreground", defaults.outside),
        disabled: cn("opacity-50", defaults.disabled),
        hidden: cn("invisible", defaults.hidden),
      }}
      components={{ Chevron: CalendarChevron, DayButton: CalendarDayButton }}
    />
  );
}

export { Calendar };
