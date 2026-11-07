// The dates the fixtures stand on, built from the served year authority: the
// year is the horizon the backend serves, or a whole number of years from it,
// and each caller keeps its own month, day and time. Nothing here decides a
// year: it reads the recording and writes ISO text.

import { servedSupport } from "./servedYearAuthority";

/** The year a fixture's "today" falls in: the supported horizon the backend serves. */
export const fixtureYear: number = servedSupport.horizon;

const two = (value: number): string => String(value).padStart(2, "0");

/** A fixture year the given number of years after the horizon, or before it when negative. */
export const fixtureYearFrom = (yearsFromHorizon: number): number =>
  fixtureYear + yearsFromHorizon;

/** ISO month text (`YYYY-MM`) in the year that many years from the horizon. */
export const fixtureMonth = (month: number, yearsFromHorizon = 0): string =>
  `${fixtureYearFrom(yearsFromHorizon)}-${two(month)}`;

/** ISO day text (`YYYY-MM-DD`) in the year that many years from the horizon. */
export const fixtureDay = (
  month: number,
  day: number,
  yearsFromHorizon = 0,
): string => `${fixtureMonth(month, yearsFromHorizon)}-${two(day)}`;

/** ISO instant text: a fixture day, `T`, then the time as the caller writes it (with its zone, if any). */
export const fixtureInstant = (
  month: number,
  day: number,
  time: string,
  yearsFromHorizon = 0,
): string => `${fixtureDay(month, day, yearsFromHorizon)}T${time}`;
