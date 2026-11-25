import type { OverviewCalendarSupport } from "../../shell/calendarContract";
import type { FilingCalendarServed } from "../../shell/calendarContract";
import { fixtureYear } from "../fixtureDates";
import { EMPTY_CALENDAR, FIXTURE_CALENDAR } from "./calendar";

// The fixture calendar served under each filing-year envelope state the
// product reports. The bounds stand a whole number of years from the
// fixture's horizon; below and above the envelope the product serves no
// registry rows, so those shapes carry none.

const support = (
  state: OverviewCalendarSupport["state"],
  bounds: Pick<OverviewCalendarSupport, "floor" | "horizon" | "hard_ceiling">,
): OverviewCalendarSupport => ({ ...bounds, state });

/** Years the envelope reaches back from the fixture's year. */
const BACK = 2;

/** The envelope the supported, projected and bounded shapes are served under. */
export const SUPPORT_OPEN: Pick<
  OverviewCalendarSupport,
  "floor" | "horizon" | "hard_ceiling"
> = { floor: fixtureYear - BACK, horizon: fixtureYear, hard_ceiling: null };

/** An envelope with a hard ceiling a year past the fixture's year. */
export const SUPPORT_BOUNDED: Pick<
  OverviewCalendarSupport,
  "floor" | "horizon" | "hard_ceiling"
> = {
  floor: fixtureYear - 1,
  horizon: fixtureYear,
  hard_ceiling: fixtureYear + 1,
};

export const SUPPORTED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  support: support("supported", SUPPORT_OPEN),
};

export const BOUNDED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  support: support("supported", SUPPORT_BOUNDED),
};

/** The bounds a projected read serves: the horizon stands behind the day. */
export const SUPPORT_PROJECTED: Pick<
  OverviewCalendarSupport,
  "floor" | "horizon" | "hard_ceiling"
> = { ...SUPPORT_OPEN, horizon: fixtureYear - 1 };

export const PROJECTED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  support: support("projected", SUPPORT_PROJECTED),
};

export const PARTIAL_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  support: support("partial", SUPPORT_OPEN),
};

export const PARTIAL_BOUNDED_CALENDAR: FilingCalendarServed = {
  ...FIXTURE_CALENDAR,
  support: support("partial", SUPPORT_BOUNDED),
};

export const BELOW_FLOOR_CALENDAR: FilingCalendarServed = {
  ...EMPTY_CALENDAR,
  support: support("below_floor", SUPPORT_OPEN),
};

export const ABOVE_CEILING_CALENDAR: FilingCalendarServed = {
  ...EMPTY_CALENDAR,
  support: support("above_ceiling", SUPPORT_BOUNDED),
};
