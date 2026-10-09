import { evaluatedLabel } from "@/shell/calendar";

/**
 * Where the past ends: a line across the list at the day the product worked
 * the states out for, so what is behind and what is ahead are told apart at
 * a glance. It is said in the language's own word for today where that day
 * is today here; a calendar worked out for another day says the day alone.
 */
export function CalendarTodayMarker({
  on,
  today,
  locale,
}: {
  on: string;
  /** The local day. */
  today: string;
  locale: string;
}) {
  const label = evaluatedLabel(on, today, locale);
  return (
    <div
      role="separator"
      aria-label={label}
      className="calendar-today flex items-center gap-2 px-4 py-1.5 text-xs font-semibold text-brand"
    >
      <span aria-hidden="true">{label}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-current opacity-40" />
    </div>
  );
}
