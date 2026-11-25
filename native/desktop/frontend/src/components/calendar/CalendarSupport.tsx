import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import type { OverviewCalendarSupport } from "../../shell/calendarContract";
import { useStrings } from "../../shell/strings";

/** Whether the read says its whole range lies outside the filing years the
 * product supports: there is then nothing to draw, and no reading of that
 * as "nothing due". A read that carries no support is a supported one. */
export function outsideEnvelope(
  support: OverviewCalendarSupport | null | undefined,
): boolean {
  return support?.state === "below_floor" || support?.state === "above_ceiling";
}

/**
 * The page for a range wholly outside the supported filing years. It names
 * the bound the product served and says that no dates is not the same as
 * nothing due; the year control stays beside it so the person can go back.
 */
export function CalendarUnsupported({
  support,
}: {
  support: OverviewCalendarSupport;
}) {
  const t = useStrings();
  const below = support.state === "below_floor";
  return (
    <EmptyState
      role="status"
      icon="calendar"
      data-calendar-support={support.state}
      description={
        below
          ? t("desktop.calendar.support_below_floor", { floor: support.floor })
          : t("desktop.calendar.support_above_ceiling", {
              ceiling: support.hard_ceiling ?? support.horizon,
            })
      }
    />
  );
}

/**
 * A line above rows that are shown but not all filing-grade: those above the
 * newest edition are projected, and a range that straddles the envelope has
 * a part that is not supported and shows no dates. Nothing for a supported
 * read or one that says nothing.
 */
export function CalendarSupportNote({
  support,
}: {
  support: OverviewCalendarSupport | null | undefined;
}) {
  const t = useStrings();
  if (!support) return null;
  if (support.state === "projected")
    return (
      <Alert
        data-calendar-support="projected"
        icon={<Icon name="info" />}
        className="mx-4 mt-3 w-auto"
      >
        {t("desktop.calendar.support_projected", { horizon: support.horizon })}
      </Alert>
    );
  if (support.state === "partial")
    return (
      <Alert
        tone="warning"
        data-calendar-support="partial"
        icon={<Icon name="alert" />}
        className="mx-4 mt-3 w-auto"
      >
        {support.hard_ceiling === null
          ? t("desktop.calendar.support_partial", { floor: support.floor })
          : t("desktop.calendar.support_partial_bounded", {
              floor: support.floor,
              ceiling: support.hard_ceiling,
            })}
      </Alert>
    );
  return null;
}
