import { expect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import {
  dayOrdinal,
  daysBetween,
  isoDay,
  localDay,
} from "../../src/shared/dates";
import {
  dateFormats,
  dayOrderOf,
  formatDay,
  formatClock,
  formatDayFigures,
  formatInstantDay,
  formatMonth,
  formatRelative,
  monthNames,
  readLocaleDay,
  formatTime,
  weekdayLetters,
} from "../../src/shared/dateFormats";
import { evaluatedLabel, evaluatedWord } from "../../src/shell/calendar";

// The translator the shell builds reads the generated catalogue, which a
// plain test has no build for; this one joins the pieces as English does.
const words = Object.assign(
  (key: string, values?: Record<string, string | number>) =>
    key === "desktop.compose.facts" ? `${values?.head} · ${values?.tail}` : key,
  { locale: "en-US" },
);

test("local date conversion keeps the day and discards the time", () => {
  for (const iso of ["2026-01-01", "2028-02-29", "2026-12-31"]) {
    const date = isoDay(iso);
    expect(localDay(date)).toBe(iso);
    expect(date.getHours()).toBe(0);
    date.setHours(23, 59, 59);
    expect(localDay(date)).toBe(iso);
  }
});

test("calendar arithmetic crosses leap days, years and clock changes", () => {
  for (const [from, to, count] of [
    ["2028-02-28", "2028-03-01", 2],
    ["2026-12-31", "2027-01-01", 1],
    ["2026-03-01", "2026-04-01", 31],
    ["2026-10-01", "2026-11-01", 31],
    // Samoa skipped a local date in 2011; ISO dates still differ by two days.
    ["2011-12-29", "2011-12-31", 2],
  ] as const) {
    expect(daysBetween(from, to)).toBe(count);
    expect(daysBetween(to, from)).toBe(-count);
  }
  expect(dayOrdinal("1970-01-01")).toBe(0);
});

test("the owning date parser and arithmetic work in distinct process time zones", () => {
  const module = pathToFileURL(resolve("src/shared/dates.ts")).href;
  for (const zone of ["Europe/Madrid", "America/Los_Angeles", "Pacific/Apia"]) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { isoDay, localDay, daysBetween } from ${JSON.stringify(module)};
      process.stdout.write(JSON.stringify([
        localDay(isoDay("2026-10-09")),
        daysBetween("2026-03-28", "2026-03-30"),
        daysBetween("2011-12-29", "2011-12-31")
      ]));
    `,
      ],
      { env: { ...process.env, TZ: zone }, encoding: "utf8" },
    );
    expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual(["2026-10-09", 2, 2]);
  }
});

test("named date formats preserve localized dates and distinct label lengths", () => {
  const date = isoDay("2026-10-09");
  const formats = dateFormats("en-US");
  expect(formats.short.format(date)).toBe("Oct 9");
  expect(formats.medium.format(date)).toBe("Oct 9, 2026");
  expect(formats.full.format(date)).toBe("Friday, October 9, 2026");
  expect(formats.month.format(date)).toBe("October 2026");
  expect(formats.weekday.format(date)).toBe("Fri");
  expect(formats.weekdayNarrow.format(date)).toBe("F");
  expect(dateFormats("es-ES").month.format(date)).toBe("octubre de 2026");
  expect(evaluatedWord("2026-10-09", "2026-10-09", "en-US")).toBe("Today");
  expect(evaluatedLabel(words, "2026-10-09", "2026-10-09", "en-US")).toBe(
    "Today · Oct 9",
  );
  expect(evaluatedLabel(words, "2026-10-09", "2026-10-10", "en-US")).toBe(
    "Oct 9, 2026",
  );
  expect(evaluatedLabel(words, "2026-10-09", "2026-10-10", "en-US", true)).toBe(
    "Friday, October 9, 2026",
  );
});

test("a calendar date reads the same in every locale's form", () => {
  expect(formatDay("en-US", "2026-10-09")).toBe("Oct 9, 2026");
  expect(formatDay("en-US", "2026-10-09", { withYear: false })).toBe("Oct 9");
  expect(formatDay("es", "2026-10-09")).toBe("9 oct 2026");
  expect(formatDay("hu", "2026-10-09")).toBe("2026. okt. 9.");
  // The named local-clock format is the independent reading of each locale.
  for (const locale of ["en", "es", "ca", "hu"]) {
    const date = isoDay("2026-10-09");
    const formats = dateFormats(locale);
    expect(formatDay(locale, "2026-10-09")).toBe(formats.medium.format(date));
    expect(formatDay(locale, "2026-10-09", { withYear: false })).toBe(
      formats.short.format(date),
    );
  }
});

test("text that names no real day comes back as it came", () => {
  for (const raw of ["", "soon", "2026-13-01", "2026-02-30", "2027-02-29"]) {
    expect(formatDay("en-US", raw)).toBe(raw);
  }
  expect(formatDay("en-US", "2028-02-29")).toBe("Feb 29, 2028");
  // A two-digit year is that year, not one in the nineteen hundreds.
  expect(formatDay("en-US", "0099-03-04")).not.toContain("1999");
  expect(formatTime("en-US", "soon")).toBe("soon");
});

test("days and moments in distinct process time zones", () => {
  const module = pathToFileURL(resolve("src/shared/dateFormats.ts")).href;
  // Moments: 2026-01-01T00:30Z on each zone's clock, with the winter offset.
  // Days: both ends of a year, a date the Apia clock skipped, and one whose
  // midnight the Sao Paulo clock skipped.
  for (const [zone, moment] of [
    ["UTC", "Jan 1, 2026, 12:30 AM"],
    ["Europe/Madrid", "Jan 1, 2026, 1:30 AM"],
    ["America/Los_Angeles", "Dec 31, 2025, 4:30 PM"],
    ["Pacific/Kiritimati", "Jan 1, 2026, 2:30 PM"],
    ["Pacific/Apia", "Jan 1, 2026, 1:30 PM"],
    ["America/Sao_Paulo", "Dec 31, 2025, 9:30 PM"],
  ] as const) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { formatDay, formatTime } from ${JSON.stringify(module)};
      process.stdout.write(JSON.stringify([
        formatDay("en-US", "2026-01-01"),
        formatDay("en-US", "2025-12-31"),
        formatDay("en-US", "2011-12-30"),
        formatDay("en-US", "2017-10-15"),
        formatDay("en-US", "2026-01-01", { withYear: false }),
        formatTime("en-US", "2026-01-01"),
        formatTime("en-US", "2026-01-01T00:30:00Z"),
      ]));
    `,
      ],
      { env: { ...process.env, TZ: zone }, encoding: "utf8" },
    );
    expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
    const drawn = JSON.parse(result.stdout) as string[];
    // Newer ICU data separates the clock's AM or PM with a narrow space.
    const spaced = drawn.map((text) => text.replace(/\s/g, " "));
    expect(spaced, zone).toEqual([
      "Jan 1, 2026",
      "Dec 31, 2025",
      "Dec 30, 2011",
      "Oct 15, 2017",
      "Jan 1",
      "Jan 1, 2026",
      moment,
    ]);
  }
});

test("formatter reuse is bounded and keeps recently used locales", () => {
  const held = dateFormats("en-US");
  expect(dateFormats("en-US")).toBe(held);
  for (let index = 0; index < 15; index++) dateFormats(`en-x-cache-${index}`);
  expect(dateFormats("en-US")).toBe(held);
  dateFormats("en-x-cache-15");
  expect(dateFormats("en-US")).toBe(held);
  for (let index = 16; index < 33; index++) dateFormats(`en-x-cache-${index}`);
  expect(dateFormats("en-US")).not.toBe(held);
  expect(() => dateFormats("not_a_locale")).toThrow(RangeError);
});

test("typed dates read in each language's order", () => {
  expect(dayOrderOf("en")).toEqual(["month", "day", "year"]);
  expect(dayOrderOf("es")).toEqual(["day", "month", "year"]);
  expect(dayOrderOf("hu")).toEqual(["year", "month", "day"]);
  expect(readLocaleDay("en", "10/11/2026")).toBe("2026-10-11");
  expect(readLocaleDay("es", "10/11/2026")).toBe("2026-11-10");
  expect(readLocaleDay("ca", "1.2.2026")).toBe("2026-02-01");
  expect(readLocaleDay("hu", "2026. 10. 31.")).toBe("2026-10-31");
  // Year first is ISO's order in any language.
  expect(readLocaleDay("en", "2026-10-31")).toBe("2026-10-31");
  expect(readLocaleDay("es", "2026/1/2")).toBe("2026-01-02");
  // A century is never guessed, and no day is invented.
  expect(readLocaleDay("es", "31/10/26")).toBeNull();
  expect(readLocaleDay("es", "31/02/2026")).toBeNull();
  expect(readLocaleDay("en", "31/10/2026")).toBeNull();
  expect(readLocaleDay("es", "abc")).toBeNull();
  expect(readLocaleDay("es", "")).toBeNull();
  expect(readLocaleDay("es", "29/02/2028")).toBe("2028-02-29");
});

test("a date is drawn in the figures it is typed in", () => {
  expect(formatDayFigures("en", "2026-10-31")).toBe("10/31/2026");
  expect(formatDayFigures("es", "2026-10-31")).toBe("31/10/2026");
  expect(formatDayFigures("es", "31/13/2026")).toBe("31/13/2026");
  for (const locale of ["en", "es", "ca", "hu"])
    expect(readLocaleDay(locale, formatDayFigures(locale, "2026-03-09"))).toBe(
      "2026-03-09",
    );
});

// Newer ICU data separates a clock's AM or PM with a narrow space.
const plain = (text: string) => text.replace(/\s/g, " ");

test("a clock reads the time of day in each language", () => {
  const at = new Date(2026, 9, 9, 14, 5);
  expect(plain(formatClock("en-US", at))).toBe("2:05 PM");
  expect(formatClock("es", at)).toBe("14:05");
  expect(formatClock("hu", at)).toBe("14:05");
  expect(plain(formatClock("en-US", at, { withDay: true }))).toBe(
    "Oct 9, 2:05 PM",
  );
  expect(formatClock("es", at, { withDay: true })).toBe("9 oct, 14:05");
  // A number is a moment in milliseconds, as a Date is.
  expect(formatClock("es", at.getTime())).toBe("14:05");
  // A date has no clock, and unreadable text has none to read.
  expect(formatClock("en-US", "2026-10-09")).toBe("2026-10-09");
  expect(formatClock("en-US", "soon")).toBe("soon");
});

test("the day an instant falls on is the day where the person is", () => {
  const late = new Date(2026, 9, 9, 23, 30).toISOString();
  const early = new Date(2026, 9, 10, 0, 30).toISOString();
  expect(formatInstantDay("en-US", late)).toBe("Oct 9, 2026");
  expect(formatInstantDay("en-US", early)).toBe("Oct 10, 2026");
  expect(formatInstantDay("es", late)).toBe("9 oct 2026");
  // A date without a time stays that date, whatever the zone.
  expect(formatInstantDay("en-US", "2026-10-09")).toBe("Oct 9, 2026");
  expect(formatInstantDay("en-US", "soon")).toBe("soon");
});

test("an instant's day follows the process time zone", () => {
  const module = pathToFileURL(resolve("src/shared/dateFormats.ts")).href;
  // 2026-01-01T00:30Z is 16:30 on 31 December at UTC-8, 21:30 at UTC-3 and
  // already the afternoon of 1 January at UTC+13 and UTC+14.
  for (const [zone, day] of [
    ["UTC", "Jan 1, 2026"],
    ["America/Los_Angeles", "Dec 31, 2025"],
    ["America/Sao_Paulo", "Dec 31, 2025"],
    ["Pacific/Apia", "Jan 1, 2026"],
    ["Pacific/Kiritimati", "Jan 1, 2026"],
  ] as const) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { formatInstantDay } from ${JSON.stringify(module)};
      process.stdout.write(formatInstantDay("en-US", "2026-01-01T00:30:00Z"));
    `,
      ],
      { env: { ...process.env, TZ: zone }, encoding: "utf8" },
    );
    expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
    expect(result.stdout, zone).toBe(day);
  }
});

test("a month is named in full with its year", () => {
  expect(formatMonth("en-US", "2026-10")).toBe("October 2026");
  expect(formatMonth("es", "2026-01")).toBe("enero de 2026");
  expect(formatMonth("hu", "2026-10")).toBe("2026. október");
  expect(formatMonth("en-US", new Date(2026, 9, 31))).toBe("October 2026");
  // Text that names no month comes back as it came.
  for (const raw of ["", "2026", "2026-00", "2026-13", "soon"]) {
    expect(formatMonth("en-US", raw)).toBe(raw);
  }
});

test("the twelve month names run from January", () => {
  const long = monthNames("en-US", "long");
  expect(long).toHaveLength(12);
  expect([long[0], long[5], long[11]]).toEqual(["January", "June", "December"]);
  const short = monthNames("en-US");
  expect([short[0], short[9], short[11]]).toEqual(["Jan", "Oct", "Dec"]);
  expect(monthNames("es", "long")[0]).toBe("enero");
  expect(monthNames("es")[9]).toBe("oct");
  expect(monthNames("hu", "long")[9]).toBe("október");
  // Held names are the same list, and a width keeps its own.
  expect(monthNames("en-US")).toBe(short);
  expect(monthNames("en-US", "long")).toBe(long);
});

test("the weekday letters start on the week's first day", () => {
  expect(weekdayLetters("en-US", 0)).toEqual([
    "S",
    "M",
    "T",
    "W",
    "T",
    "F",
    "S",
  ]);
  expect(weekdayLetters("en-US", 1)).toEqual([
    "M",
    "T",
    "W",
    "T",
    "F",
    "S",
    "S",
  ]);
  expect(weekdayLetters("es", 1)).toEqual(["L", "M", "X", "J", "V", "S", "D"]);
});

test("a distance in time is said in words where the locale has them", () => {
  expect(formatRelative("en-US", 0, "day")).toBe("today");
  expect(formatRelative("en-US", -1, "day")).toBe("yesterday");
  expect(formatRelative("en-US", -2, "day")).toBe("2 days ago");
  expect(formatRelative("en-US", 3, "hour")).toBe("in 3 hours");
  expect(formatRelative("es", -1, "day")).toBe("ayer");
  expect(formatRelative("es", 0, "day")).toBe("hoy");
});
