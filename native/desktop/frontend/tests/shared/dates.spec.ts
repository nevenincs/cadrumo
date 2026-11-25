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
import {
  fixtureDay,
  fixtureInstant,
  fixtureMonth,
  fixtureYear,
} from "../../src/dev/fixtureDates";

// The translator the shell builds reads the generated catalogue, which a
// plain test has no build for; this one joins the pieces as English does.
const words = Object.assign(
  (key: string, values?: Record<string, string | number>) =>
    key === "desktop.compose.facts" ? `${values?.head} · ${values?.tail}` : key,
  { locale: "en-US" },
);

// The readings below are written from the calendar and the names of its days
// and months, not from the formatters under test, for whichever year the
// fixtures stand in.
const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const parts = (iso: string) => {
  const [year, month, day] = iso.split("-").map(Number) as [
    number,
    number,
    number,
  ];
  return { year, month, day };
};
/** English readings of an ISO day. */
const english = (iso: string) => {
  const { year, month, day } = parts(iso);
  const name = MONTHS[month - 1]!;
  const weekday =
    WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()]!;
  return {
    short: `${name.slice(0, 3)} ${day}`,
    medium: `${name.slice(0, 3)} ${day}, ${year}`,
    full: `${weekday}, ${name} ${day}, ${year}`,
    month: `${name} ${year}`,
    weekday: weekday.slice(0, 3),
    narrow: weekday.slice(0, 1),
  };
};
const DAY_MS = 24 * 60 * 60 * 1000;
/** An ISO day the given number of days from another. */
const shift = (iso: string, days: number): string =>
  new Date(Date.parse(iso) + days * DAY_MS).toISOString().slice(0, 10);
/** The first year from the fixtures' own on that has, or lacks, a 29th of February. */
const yearWithFebruary29 = (leap: boolean): number => {
  let year = fixtureYear;
  while ((new Date(Date.UTC(year, 1, 29)).getUTCMonth() === 1) !== leap)
    year += 1;
  return year;
};
const LEAP_YEAR = yearWithFebruary29(true);
const COMMON_YEAR = yearWithFebruary29(false);
/** The last Sunday of a month, the day Europe changes its clocks in March. */
const lastSunday = (year: number, month: number): number => {
  const last = new Date(Date.UTC(year, month, 0));
  return last.getUTCDate() - last.getUTCDay();
};

/** A day the zone's own clock cannot show: found by walking the calendar days
 * from the epoch on that zone's clock, as a process in the zone sees them. A
 * `date` is a civil date that never occurred there; a `midnight` is one whose
 * midnight never came, the day beginning at one. */
const skippedDay = (zone: string, kind: "date" | "midnight"): string => {
  const result = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      `
      const kind = ${JSON.stringify(kind)};
      for (let at = 0; at < 47_000; at += 1) {
        const utc = new Date(at * 86_400_000);
        const [year, month, day] = [utc.getUTCFullYear(), utc.getUTCMonth(), utc.getUTCDate()];
        const local = new Date(year, month, day);
        const missing = kind === "date" ? local.getDate() !== day : local.getDate() === day && local.getHours() !== 0;
        if (missing) {
          process.stdout.write(
            [year, String(month + 1).padStart(2, "0"), String(day).padStart(2, "0")].join("-"),
          );
          break;
        }
      }
    `,
    ],
    { env: { ...process.env, TZ: zone }, encoding: "utf8" },
  );
  expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
  expect(result.stdout, `${zone} has a ${kind} to find`).not.toBe("");
  return result.stdout;
};
const APIA_SKIPPED = () => skippedDay("Pacific/Apia", "date");
const SAO_PAULO_SKIPPED = () => skippedDay("America/Sao_Paulo", "midnight");

test("local date conversion keeps the day and discards the time", () => {
  for (const iso of [
    fixtureDay(1, 1),
    `${LEAP_YEAR}-02-29`,
    fixtureDay(12, 31),
  ]) {
    const date = isoDay(iso);
    expect(localDay(date)).toBe(iso);
    expect(date.getHours()).toBe(0);
    date.setHours(23, 59, 59);
    expect(localDay(date)).toBe(iso);
  }
});

test("calendar arithmetic crosses leap days, years and clock changes", () => {
  const skipped = APIA_SKIPPED();
  for (const [from, to, count] of [
    [`${LEAP_YEAR}-02-28`, `${LEAP_YEAR}-03-01`, 2],
    [fixtureDay(12, 31), fixtureDay(1, 1, 1), 1],
    [fixtureDay(3, 1), fixtureDay(4, 1), 31],
    [fixtureDay(10, 1), fixtureDay(11, 1), 31],
    // Samoa skipped a local date once; ISO dates still differ by two days.
    [shift(skipped, -1), shift(skipped, 1), 2],
  ] as const) {
    expect(daysBetween(from, to)).toBe(count);
    expect(daysBetween(to, from)).toBe(-count);
  }
  expect(dayOrdinal("1970-01-01")).toBe(0);
});

test("the owning date parser and arithmetic work in distinct process time zones", () => {
  const module = pathToFileURL(resolve("src/shared/dates.ts")).href;
  const skipped = APIA_SKIPPED();
  const october9 = fixtureDay(10, 9);
  // Across the day Europe changes its clocks.
  const sunday = lastSunday(fixtureYear, 3);
  const beforeChange = fixtureDay(3, sunday - 1);
  const afterChange = shift(beforeChange, 2);
  for (const zone of ["Europe/Madrid", "America/Los_Angeles", "Pacific/Apia"]) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { isoDay, localDay, daysBetween } from ${JSON.stringify(module)};
      process.stdout.write(JSON.stringify([
        localDay(isoDay(${JSON.stringify(october9)})),
        daysBetween(${JSON.stringify(beforeChange)}, ${JSON.stringify(afterChange)}),
        daysBetween(${JSON.stringify(shift(skipped, -1))}, ${JSON.stringify(shift(skipped, 1))})
      ]));
    `,
      ],
      { env: { ...process.env, TZ: zone }, encoding: "utf8" },
    );
    expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual([october9, 2, 2]);
  }
});

test("named date formats preserve localized dates and distinct label lengths", () => {
  const october9 = fixtureDay(10, 9);
  const october10 = fixtureDay(10, 10);
  const named = english(october9);
  const date = isoDay(october9);
  const formats = dateFormats("en-US");
  expect(formats.short.format(date)).toBe(named.short);
  expect(formats.medium.format(date)).toBe(named.medium);
  expect(formats.full.format(date)).toBe(named.full);
  expect(formats.month.format(date)).toBe(named.month);
  expect(formats.weekday.format(date)).toBe(named.weekday);
  expect(formats.weekdayNarrow.format(date)).toBe(named.narrow);
  expect(dateFormats("es-ES").month.format(date)).toBe(
    `octubre de ${fixtureYear}`,
  );
  expect(evaluatedWord(october9, october9, "en-US")).toBe("Today");
  expect(evaluatedLabel(words, october9, october9, "en-US")).toBe(
    `Today · ${named.short}`,
  );
  expect(evaluatedLabel(words, october9, october10, "en-US")).toBe(
    named.medium,
  );
  expect(evaluatedLabel(words, october9, october10, "en-US", true)).toBe(
    named.full,
  );
});

test("a calendar date reads the same in every locale's form", () => {
  const october9 = fixtureDay(10, 9);
  expect(formatDay("en-US", october9)).toBe(english(october9).medium);
  expect(formatDay("en-US", october9, { withYear: false })).toBe(
    english(october9).short,
  );
  expect(formatDay("es", october9)).toBe(`9 oct ${fixtureYear}`);
  expect(formatDay("hu", october9)).toBe(`${fixtureYear}. okt. 9.`);
  // The named local-clock format is the independent reading of each locale.
  for (const locale of ["en", "es", "ca", "hu"]) {
    const date = isoDay(october9);
    const formats = dateFormats(locale);
    expect(formatDay(locale, october9)).toBe(formats.medium.format(date));
    expect(formatDay(locale, october9, { withYear: false })).toBe(
      formats.short.format(date),
    );
  }
});

test("text that names no real day comes back as it came", () => {
  for (const raw of [
    "",
    "soon",
    `${fixtureYear}-13-01`,
    `${fixtureYear}-02-30`,
    `${COMMON_YEAR}-02-29`,
  ]) {
    expect(formatDay("en-US", raw)).toBe(raw);
  }
  expect(formatDay("en-US", `${LEAP_YEAR}-02-29`)).toBe(`Feb 29, ${LEAP_YEAR}`);
  // A two-digit year is that year, not one in the nineteen hundreds.
  expect(formatDay("en-US", "0099-03-04")).not.toContain("1999");
  expect(formatTime("en-US", "soon")).toBe("soon");
});

test("days and moments in distinct process time zones", () => {
  const module = pathToFileURL(resolve("src/shared/dateFormats.ts")).href;
  const apia = APIA_SKIPPED();
  const saoPaulo = SAO_PAULO_SKIPPED();
  const newYear = fixtureDay(1, 1);
  const newYearsEve = fixtureDay(12, 31, -1);
  const before = fixtureYear - 1;
  // Moments: the first of January at 00:30Z on each zone's clock, with the
  // winter offset. Days: both ends of a year, a date the Apia clock skipped,
  // and one whose midnight the Sao Paulo clock skipped.
  for (const [zone, moment] of [
    ["UTC", `Jan 1, ${fixtureYear}, 12:30 AM`],
    ["Europe/Madrid", `Jan 1, ${fixtureYear}, 1:30 AM`],
    ["America/Los_Angeles", `Dec 31, ${before}, 4:30 PM`],
    ["Pacific/Kiritimati", `Jan 1, ${fixtureYear}, 2:30 PM`],
    ["Pacific/Apia", `Jan 1, ${fixtureYear}, 1:30 PM`],
    ["America/Sao_Paulo", `Dec 31, ${before}, 9:30 PM`],
  ] as const) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { formatDay, formatTime } from ${JSON.stringify(module)};
      process.stdout.write(JSON.stringify([
        formatDay("en-US", ${JSON.stringify(newYear)}),
        formatDay("en-US", ${JSON.stringify(newYearsEve)}),
        formatDay("en-US", ${JSON.stringify(apia)}),
        formatDay("en-US", ${JSON.stringify(saoPaulo)}),
        formatDay("en-US", ${JSON.stringify(newYear)}, { withYear: false }),
        formatTime("en-US", ${JSON.stringify(newYear)}),
        formatTime("en-US", ${JSON.stringify(fixtureInstant(1, 1, "00:30:00Z"))}),
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
      english(newYear).medium,
      english(newYearsEve).medium,
      english(apia).medium,
      english(saoPaulo).medium,
      english(newYear).short,
      english(newYear).medium,
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
  expect(readLocaleDay("en", `10/11/${fixtureYear}`)).toBe(fixtureDay(10, 11));
  expect(readLocaleDay("es", `10/11/${fixtureYear}`)).toBe(fixtureDay(11, 10));
  expect(readLocaleDay("ca", `1.2.${fixtureYear}`)).toBe(fixtureDay(2, 1));
  expect(readLocaleDay("hu", `${fixtureYear}. 10. 31.`)).toBe(
    fixtureDay(10, 31),
  );
  // Year first is ISO's order in any language.
  expect(readLocaleDay("en", fixtureDay(10, 31))).toBe(fixtureDay(10, 31));
  expect(readLocaleDay("es", `${fixtureYear}/1/2`)).toBe(fixtureDay(1, 2));
  // A century is never guessed, and no day is invented.
  expect(readLocaleDay("es", "31/10/26")).toBeNull();
  expect(readLocaleDay("es", `31/02/${fixtureYear}`)).toBeNull();
  expect(readLocaleDay("en", `31/10/${fixtureYear}`)).toBeNull();
  expect(readLocaleDay("es", "abc")).toBeNull();
  expect(readLocaleDay("es", "")).toBeNull();
  expect(readLocaleDay("es", `29/02/${LEAP_YEAR}`)).toBe(`${LEAP_YEAR}-02-29`);
});

test("a date is drawn in the figures it is typed in", () => {
  expect(formatDayFigures("en", fixtureDay(10, 31))).toBe(
    `10/31/${fixtureYear}`,
  );
  expect(formatDayFigures("es", fixtureDay(10, 31))).toBe(
    `31/10/${fixtureYear}`,
  );
  expect(formatDayFigures("es", `31/13/${fixtureYear}`)).toBe(
    `31/13/${fixtureYear}`,
  );
  for (const locale of ["en", "es", "ca", "hu"])
    expect(
      readLocaleDay(locale, formatDayFigures(locale, fixtureDay(3, 9))),
    ).toBe(fixtureDay(3, 9));
});

// Newer ICU data separates a clock's AM or PM with a narrow space.
const plain = (text: string) => text.replace(/\s/g, " ");

test("a clock reads the time of day in each language", () => {
  const at = new Date(fixtureYear, 9, 9, 14, 5);
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
  expect(formatClock("en-US", fixtureDay(10, 9))).toBe(fixtureDay(10, 9));
  expect(formatClock("en-US", "soon")).toBe("soon");
});

test("the day an instant falls on is the day where the person is", () => {
  const late = new Date(fixtureYear, 9, 9, 23, 30).toISOString();
  const early = new Date(fixtureYear, 9, 10, 0, 30).toISOString();
  expect(formatInstantDay("en-US", late)).toBe(`Oct 9, ${fixtureYear}`);
  expect(formatInstantDay("en-US", early)).toBe(`Oct 10, ${fixtureYear}`);
  expect(formatInstantDay("es", late)).toBe(`9 oct ${fixtureYear}`);
  // A date without a time stays that date, whatever the zone.
  expect(formatInstantDay("en-US", fixtureDay(10, 9))).toBe(
    `Oct 9, ${fixtureYear}`,
  );
  expect(formatInstantDay("en-US", "soon")).toBe("soon");
});

test("an instant's day follows the process time zone", () => {
  const module = pathToFileURL(resolve("src/shared/dateFormats.ts")).href;
  // 00:30Z on the first of January is 16:30 on 31 December at UTC-8, 21:30
  // at UTC-3 and already the afternoon of 1 January at UTC+13 and UTC+14.
  for (const [zone, day] of [
    ["UTC", `Jan 1, ${fixtureYear}`],
    ["America/Los_Angeles", `Dec 31, ${fixtureYear - 1}`],
    ["America/Sao_Paulo", `Dec 31, ${fixtureYear - 1}`],
    ["Pacific/Apia", `Jan 1, ${fixtureYear}`],
    ["Pacific/Kiritimati", `Jan 1, ${fixtureYear}`],
  ] as const) {
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "--eval",
        `
      import { formatInstantDay } from ${JSON.stringify(module)};
      process.stdout.write(formatInstantDay("en-US", ${JSON.stringify(fixtureInstant(1, 1, "00:30:00Z"))}));
    `,
      ],
      { env: { ...process.env, TZ: zone }, encoding: "utf8" },
    );
    expect(result.status, `${zone}: ${result.stderr}`).toBe(0);
    expect(result.stdout, zone).toBe(day);
  }
});

test("a month is named in full with its year", () => {
  expect(formatMonth("en-US", fixtureMonth(10))).toBe(`October ${fixtureYear}`);
  expect(formatMonth("es", fixtureMonth(1))).toBe(`enero de ${fixtureYear}`);
  expect(formatMonth("hu", fixtureMonth(10))).toBe(`${fixtureYear}. október`);
  expect(formatMonth("en-US", new Date(fixtureYear, 9, 31))).toBe(
    `October ${fixtureYear}`,
  );
  // Text that names no month comes back as it came.
  for (const raw of [
    "",
    String(fixtureYear),
    `${fixtureYear}-00`,
    `${fixtureYear}-13`,
    "soon",
  ]) {
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
