import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { yearSteps } from "../../shell/calendar";
import type { OverviewCalendarSupport } from "../../shell/calendarContract";
import { useStrings } from "../../shell/strings";

/**
 * Which filing year the calendar looks at. A page opens on the range around
 * today, which names no year; the arrows step to the year before or after
 * the one asked for, and the way back appears once a year is chosen. Which
 * years the product can answer for is the product's: a year it cannot read
 * is said, and what was shown stays. The arrows stop at the bounds the read
 * was served under: a step is not offered into a year the product has said it
 * does not support. A stopped arrow stays in the tab order, so focus is not
 * lost when it is the one just pressed.
 */
export function CalendarYear({
  year,
  failed,
  support,
  onStep,
  onCurrent,
}: {
  /** The year on screen; null while it is the range around today. */
  year: number | null;
  failed: boolean;
  /** The envelope the read on screen was served under; null where none. */
  support?: OverviewCalendarSupport | null;
  onStep: (by: -1 | 1) => void;
  onCurrent: () => void;
}) {
  const t = useStrings();
  const steps = yearSteps(support, year ?? new Date().getFullYear());
  return (
    <>
      <div
        role="group"
        aria-label={t("desktop.calendar.year")}
        className="calendar-year flex items-center gap-1"
      >
        <IconButton
          label={t("desktop.calendar.year_previous")}
          aria-disabled={!steps.previous || undefined}
          onClick={() => steps.previous && onStep(-1)}
        >
          <Icon name="back" />
        </IconButton>
        {year !== null && (
          <span className="min-w-12 text-center text-sm font-medium tabular-nums">
            {year}
          </span>
        )}
        <IconButton
          label={t("desktop.calendar.year_next")}
          aria-disabled={!steps.next || undefined}
          onClick={() => steps.next && onStep(1)}
        >
          <Icon name="forward" />
        </IconButton>
        {year !== null && (
          <Button variant="ghost" size="sm" onClick={onCurrent}>
            {t("desktop.calendar.year_current")}
          </Button>
        )}
      </div>
      {failed && (
        <p role="status" className="text-xs text-muted-foreground">
          {t("desktop.calendar.year_failed")}
        </p>
      )}
    </>
  );
}
