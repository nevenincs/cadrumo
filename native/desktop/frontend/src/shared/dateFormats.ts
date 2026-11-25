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
  // A month named by its number, so it is read in UTC like an ISO day.
  isoMonth: new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }),
  monthShortWord: new Intl.DateTimeFormat(locale, {
    month: "short",
    timeZone: "UTC",
  }),
  monthLongWord: new Intl.DateTimeFormat(locale, {
    month: "long",
    timeZone: "UTC",
  }),
  clock: new Intl.DateTimeFormat(locale, { timeStyle: "short" }),
  dayClock: new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }),
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

/** The calendar day an instant falls on where the person is, as a medium
 * date. A date without a time is not an instant, so it stays that calendar
 * date. Unreadable text comes back as it came. */
export function formatInstantDay(locale: string, instant: string): string {
  if (ISO_DAY.test(instant)) return formatDay(locale, instant);
  const time = Date.parse(instant);
  return Number.isNaN(time)
    ? instant
    : dateFormats(locale).medium.format(new Date(time));
}

/** The time of day of a moment, as the person's clock reads it, with its
 * short date first when `withDay` is set. A date without a time has no clock
 * to read, and unreadable text has none either: both come back as they
 * came. */
export function formatClock(
  locale: string,
  instant: string | number | Date,
  { withDay = false }: { withDay?: boolean } = {},
): string {
  if (typeof instant === "string" && ISO_DAY.test(instant)) return instant;
  const at = instant instanceof Date ? instant : new Date(instant);
  if (Number.isNaN(at.getTime())) return String(instant);
  const named = dateFormats(locale);
  return (withDay ? named.dayClock : named.clock).format(at);
}

const MONTH = /^(\d{4})-(\d{2})$/;

/** A month with its year, the month in full. `YYYY-MM` names a calendar
 * month and a `Date` is read on the person's clock. Text that names no real
 * month comes back as it came. */
export function formatMonth(locale: string, month: string | Date): string {
  const named = dateFormats(locale);
  if (month instanceof Date) return named.month.format(month);
  const found = MONTH.exec(month);
  const number = Number(found?.[2]);
  if (!found || number < 1 || number > 12) return month;
  const date = new Date(0);
  date.setUTCFullYear(Number(found[1]), number - 1, 1);
  return named.isoMonth.format(date);
}

const NAMES_KEPT = 8;
const names = new Map<string, string[]>();

/** The twelve months' names in `locale`, January first. */
export function monthNames(
  locale: string,
  width: "short" | "long" = "short",
): string[] {
  return reuse(names, NAMES_KEPT, `${locale} ${width}`, () => {
    const named = dateFormats(locale);
    const format =
      width === "short" ? named.monthShortWord : named.monthLongWord;
    // Any year names the months; the epoch's is the one with no meaning.
    return Array.from({ length: 12 }, (_, month) =>
      format.format(new Date(Date.UTC(1970, month, 1))),
    );
  });
}

/** The seven weekdays' letters in `locale`, from the week's first day, where
 * 0 is Sunday. */
export function weekdayLetters(locale: string, weekStart: number): string[] {
  const { weekdayNarrow } = dateFormats(locale);
  // 4 January 1970 was a Sunday.
  return Array.from({ length: 7 }, (_, column) =>
    weekdayNarrow.format(new Date(1970, 0, 4 + weekStart + column)),
  );
}

/** A distance in time in words, where `0` and `-1` of a day are `today` and
 * `yesterday` in the locale. */
export function formatRelative(
  locale: string,
  value: number,
  unit: Intl.RelativeTimeFormatUnit,
): string {
  return dateFormats(locale).relative.format(value, unit);
}
