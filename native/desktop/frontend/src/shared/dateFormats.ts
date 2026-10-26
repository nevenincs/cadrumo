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
});

// A bounded cache also serves hosts whose locale list changes during a launch.
const CACHE_LIMIT = 16;
const formats = new Map<string, ReturnType<typeof makeFormats>>();

export function dateFormats(locale: string): ReturnType<typeof makeFormats> {
  const held = formats.get(locale);
  const value = held ?? makeFormats(locale);
  formats.delete(locale);
  formats.set(locale, value);
  if (formats.size > CACHE_LIMIT) {
    const oldest = formats.keys().next().value;
    if (oldest !== undefined) formats.delete(oldest);
  }
  return value;
}
