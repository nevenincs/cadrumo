// Named display formats shared by calendar faces and date labels. Date-only
// callers supply local calendar dates; timestamps keep the user's time zone.
const makeFormats = (locale: string) => ({
  short: new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }),
  medium: new Intl.DateTimeFormat(locale, { dateStyle: "medium" }),
  full: new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
  month: new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }),
  weekday: new Intl.DateTimeFormat(locale, { weekday: "short" }),
  weekdayNarrow: new Intl.DateTimeFormat(locale, { weekday: "narrow" }),
  dateTime: new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }),
  relative: new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
  // An ISO date read at midnight UTC and drawn in UTC: no local clock change
  // or skipped local date can move it.
  isoDay: new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone: "UTC",
  }),
  // The same day in the figures a person types it in.
  isoDayFigures: new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }),
  monthName: new Intl.DateTimeFormat(locale, { month: "long" }),
  isoDayNoYear: new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }),
});

/** The value held under `key`, made if absent; the least recently used goes
 * once `limit` is passed. */
function reuse<Value>(
  held: Map<string, Value>,
  limit: number,
  key: string,
  make: () => Value,
): Value {
  const found = held.get(key);
  const value = found ?? make();
  held.delete(key);
  held.set(key, value);
  if (held.size > limit) {
    const oldest = held.keys().next().value;
    if (oldest !== undefined) held.delete(oldest);
  }
  return value;
}

// A bounded cache also serves hosts whose locale list changes during a launch.
const CACHE_LIMIT = 16;
const formats = new Map<string, ReturnType<typeof makeFormats>>();

export function dateFormats(locale: string): ReturnType<typeof makeFormats> {
  return reuse(formats, CACHE_LIMIT, locale, () => makeFormats(locale));
}

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Midnight UTC of an ISO date, or null when the text names no real day. */
function utcDay(iso: string): Date | null {
  const found = ISO_DAY.exec(iso);
  if (!found) return null;
  const month = Number(found[2]) - 1;
  const day = Number(found[3]);
  const date = new Date(0);
  date.setUTCFullYear(Number(found[1]), month, day);
  return date.getUTCMonth() === month && date.getUTCDate() === day
    ? date
    : null;
}

/** How many drawn dates are kept: a few periods' worth. */
const DAYS_KEPT = 4096;
const days = new Map<string, string>();

/** A calendar date, with its year unless `withYear` is false. Text that names
 * no real day is returned as it came. */
export function formatDay(
  locale: string,
  iso: string,
  { withYear = true }: { withYear?: boolean } = {},
): string {
  const date = utcDay(iso);
  if (!date) return iso;
  const key = `${locale} ${withYear ? "y" : "-"} ${iso}`;
  return reuse(days, DAYS_KEPT, key, () => {
    const named = dateFormats(locale);
    return (withYear ? named.isoDay : named.isoDayNoYear).format(date);
  });
}

/** A calendar date in the figures a person types it in, in the locale's order.
 * Text that names no real day is returned as it came. */
export function formatDayFigures(locale: string, iso: string): string {
  const date = utcDay(iso);
  return date ? dateFormats(locale).isoDayFigures.format(date) : iso;
}

type DayPart = "day" | "month" | "year";

/** The order the locale writes a date's parts in. */
export function dayOrderOf(locale: string): DayPart[] {
  return dateFormats(locale)
    .isoDayFigures.formatToParts(0)
    .flatMap((part): DayPart[] =>
      part.type === "day" || part.type === "month" || part.type === "year"
        ? [part.type]
        : [],
    );
}

const TYPED_DAY = /^(\d+)[-/.\s]+(\d+)[-/.\s]+(\d+)[.\s]*$/;

/** The ISO day a typed date names: in the locale's order, or year first as ISO
 * writes it. Null when it names no real day, or leaves the century to a guess
 * by giving fewer than four year digits. */
export function readLocaleDay(locale: string, raw: string): string | null {
  const found = TYPED_DAY.exec(raw.trim());
  if (!found) return null;
  const figures = [found[1], found[2], found[3]] as string[];
  const order: DayPart[] =
    figures[0]?.length === 4 ? ["year", "month", "day"] : dayOrderOf(locale);
  const at = (part: DayPart) => figures[order.indexOf(part)] ?? "";
  const [year, month, day] = [at("year"), at("month"), at("day")];
  if (year.length !== 4 || month.length > 2 || day.length > 2) return null;
  const iso = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  return utcDay(iso) ? iso : null;
}

/** A moment, as the person's clock reads it. A date without a time is not a
 * moment, so it stays that calendar date. Unreadable text comes back as it
 * came. */
export function formatTime(locale: string, instant: string): string {
  if (ISO_DAY.test(instant)) return formatDay(locale, instant);
  const time = Date.parse(instant);
  return Number.isNaN(time)
    ? instant
    : dateFormats(locale).dateTime.format(new Date(time));
}
