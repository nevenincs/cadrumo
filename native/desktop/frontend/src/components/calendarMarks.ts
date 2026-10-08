import type { IconName } from "@/components/ui/icon";
import type { CalendarEvent, CalendarUserState } from "../shell/views";

/**
 * How what was observed is marked on its day: a filing made is a filled
 * mark and a message a hollow one, told apart by shape, with or without
 * colour.
 */
export const EVENT_MARK: Record<CalendarEvent["event_type"], string> = {
  filing: "bg-success forced-colors:bg-[CanvasText]",
  message: "border-2 border-muted-foreground",
};

/**
 * The mark each of the product's readings of an obligation carries wherever
 * it is drawn, so that it is never told by colour alone. What is simply due
 * carries none: it is the reading the others are set against.
 */
export const STATE_MARK: Record<CalendarUserState, IconName | null> = {
  due: null,
  late: "alert",
  filed: "check",
  unknown: "info",
};
