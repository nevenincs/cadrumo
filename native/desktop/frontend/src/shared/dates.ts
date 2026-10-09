/** Calendar dates carry no time zone. Local dates are for display; UTC
 * ordinals are for arithmetic across clock changes. */
export const DAY_MS = 86_400_000;

const parts = (iso: string): [number, number, number] => {
  const [year = 1970, month = 1, day = 1] = iso.split("-").map(Number);
  return [year, month, day];
};

export const isoDate = (year: number, month: number, day: number): string =>
  `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

/** The local calendar day, as an ISO date. */
export const localDay = (now: Date = new Date()): string =>
  isoDate(now.getFullYear(), now.getMonth() + 1, now.getDate());

/** An ISO date as a local calendar day: no time, so no zone can move it. */
export function isoDay(iso: string): Date {
  const [year, month, day] = parts(iso);
  return new Date(year, month - 1, day);
}

export function dayOrdinal(iso: string): number {
  const [year, month, day] = parts(iso);
  return Math.round(Date.UTC(year, month - 1, day) / DAY_MS);
}

/** Signed whole calendar days, independent of daylight-saving time. */
export const daysBetween = (from: string, to: string): number =>
  dayOrdinal(to) - dayOrdinal(from);
