import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { deadlineDistance } from "@/shell/calendar";
import { daysBetween, isoDay as day } from "@/shared/dates";
import { dateFormats } from "@/shared/dateFormats";
import { entryKey } from "@/shell/calendarEntries";
import { useStrings } from "@/shell/strings";
import type { CalendarEntry } from "@/shell/views";
import { STATE_TONE } from "./calendarMarks";

// A row is drawn again only when it changes: choosing one obligation does
// not redraw the others.
export const CalendarEntryRow = memo(function CalendarEntryRow({
  entry,
  locale,
  selected,
  onSelect,
  onOpen,
}: {
  entry: CalendarEntry;
  locale: string;
  /** Chosen, here or in the months beside the list. */
  selected: boolean;
  onSelect: (key: string) => void;
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const closes = day(entry.adjusted_closes_on);
  const { short, full, weekday, relative: distance } = dateFormats(locale);
  // How far the binding date is from the day the product evaluated: the
  // product's own count where it gives one.
  const away =
    entry.days_overdue !== null
      ? -entry.days_overdue
      : daysBetween(entry.evaluated_on, entry.adjusted_closes_on);
  // A filed obligation has no distance left to say.
  const { value, unit } = deadlineDistance(away, entry.days_overdue !== null);
  const relative =
    entry.user_state === "filed" ? null : distance.format(value, unit);
  const name = t("desktop.calendar.modelo", { modelo: entry.modelo });
  const notes = [
    t(`desktop.calendar.local.${entry.local_filing_state}`),
    t(`desktop.calendar.aeat.${entry.aeat_submission_state}`),
    entry.adjusted_closes_on !== entry.closes_on
      ? t("desktop.calendar.moved", {
          date: short.format(day(entry.closes_on)),
        })
      : null,
    entry.payment_cutoff_on
      ? t("desktop.calendar.payment_cutoff", {
          date: short.format(day(entry.payment_cutoff_on)),
        })
      : null,
  ].filter((note): note is string => note !== null);
  return (
    <li
      data-entry={entryKey(entry)}
      aria-current={selected || undefined}
      // The chosen row carries a bar as well as a surface, as a chosen item
      // does everywhere in the window.
      className="grid scroll-mt-[calc(var(--calendar-head)+--spacing(8))] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-l-(length:--selection-edge) border-l-transparent px-4 py-2 hover:bg-accent aria-[current=true]:border-l-ring aria-[current=true]:bg-selected forced-colors:border-l-[Canvas] forced-colors:aria-[current=true]:border-l-[Highlight]"
    >
      <time
        dateTime={entry.adjusted_closes_on}
        className="grid w-10 justify-items-center"
      >
        {/* The eye has the month in the heading above; read aloud, a day
            and a weekday alone are not a date, so the whole date is said. */}
        <span className="sr-only">{full.format(closes)}</span>
        <span
          aria-hidden="true"
          className="text-md leading-tight font-semibold tabular-nums"
        >
          {closes.getDate()}
        </span>
        <span aria-hidden="true" className="text-xs text-muted-foreground">
          {weekday.format(closes)}
        </span>
      </time>
      <div className="grid min-w-0 gap-0.5">
        {/* The row's name is what chooses it: the same obligation is then
            shown among the months. */}
        <button
          type="button"
          aria-pressed={selected}
          className="flex min-h-control-xs cursor-pointer flex-wrap items-center gap-x-2 justify-self-start rounded-sm text-left hover:underline"
          onClick={() => onSelect(entryKey(entry))}
        >
          <span className="font-medium">{name}</span>
          <span className="text-muted-foreground">{entry.period}</span>
        </button>
        <span className="text-sm text-muted-foreground">
          {notes.join(" · ")}
        </span>
        {/* In a narrow pane the distance moves under the notes: it is what
            the person came for, and is never the thing left out. */}
        {relative && (
          <span className="calendar-distance text-sm text-muted-foreground @md:hidden">
            {relative}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="grid justify-items-end gap-0.5">
          <Badge variant={STATE_TONE[entry.user_state]}>
            {t(`desktop.calendar.state.${entry.user_state}`)}
          </Badge>
          {relative && (
            <span className="calendar-distance text-xs text-muted-foreground @max-md:hidden">
              {relative}
            </span>
          )}
        </span>
        {onOpen && (
          <IconButton
            label={t("desktop.calendar.open_tui")}
            accessibleName={`${t("desktop.calendar.open_tui")}: ${name} ${entry.period}`}
            side="left"
            onClick={() => onOpen(entry)}
          >
            <Icon name="arrow" />
          </IconButton>
        )}
      </div>
    </li>
  );
});
