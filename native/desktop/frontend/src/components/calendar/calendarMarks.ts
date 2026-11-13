import type { IconName } from "@/components/ui/icon";
import { closeUnknown } from "@/shell/calendarEntries";
import type { Translate } from "@/shell/strings";
import type { OverviewPeriodState } from "@/shell/calendarContract";
import type { CalendarEntry, CalendarEvent } from "@/shell/views";

export const STATE_TONE: Record<
  OverviewPeriodState,
  "neutral" | "danger" | "success" | "warning"
> = { due: "neutral", late: "danger", filed: "success", unknown: "warning" };

/**
 * How what was observed is marked on its day: a filing made is a filled
 * mark and a message a hollow one, told apart by shape, with or without
 * colour.
 */
export const EVENT_MARK: Record<CalendarEvent["event_type"], string> = {
  filing: "bg-success forced-colors:bg-[CanvasText]",
  message: "border-(length:--mark-edge) border-muted-foreground",
};

/**
 * The mark each of the product's readings of an obligation carries wherever
 * it is drawn, so that it is never told by colour alone. What is simply due
 * carries none: it is the reading the others are set against.
 */
export const STATE_MARK: Record<OverviewPeriodState, IconName | null> = {
  due: null,
  late: "alert",
  filed: "check",
  unknown: "info",
};

/**
 * What an obligation's reading is called. A close the product does not know
 * is called that, in the product's own words for it, rather than by the
 * general reading it shares with what could not be placed at all.
 */
export const stateWords = (t: Translate, entry: CalendarEntry) =>
  closeUnknown(entry)
    ? t("workspace.declarations.calendar.legal.unknown")
    : t(`desktop.calendar.state.${entry.user_state}`);
