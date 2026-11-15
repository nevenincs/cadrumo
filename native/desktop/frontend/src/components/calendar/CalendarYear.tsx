import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { useStrings } from "../../shell/strings";

/**
 * Which filing year the calendar looks at. A page opens on the range around
 * today, which names no year; the arrows step to the year before or after
 * the one asked for, and the way back appears once a year is chosen. Which
 * years the product can answer for is the product's: a year it cannot read
 * is said, and what was shown stays.
 */
export function CalendarYear({
  year,
  failed,
  onStep,
  onCurrent,
}: {
  /** The year on screen; null while it is the range around today. */
  year: number | null;
  failed: boolean;
  onStep: (by: -1 | 1) => void;
  onCurrent: () => void;
}) {
  const t = useStrings();
  return (
    <>
      <div
        role="group"
        aria-label={t("desktop.calendar.year")}
        className="calendar-year flex items-center gap-1"
      >
        <IconButton
          label={t("desktop.calendar.year_previous")}
          onClick={() => onStep(-1)}
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
          onClick={() => onStep(1)}
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
