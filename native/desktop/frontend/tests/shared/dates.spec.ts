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
import { dateFormats } from "../../src/shared/dateFormats";
import { evaluatedLabel, evaluatedWord } from "../../src/shell/calendar";

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
  expect(evaluatedLabel("2026-10-09", "2026-10-09", "en-US")).toBe(
    "Today · Oct 9",
  );
  expect(evaluatedLabel("2026-10-09", "2026-10-10", "en-US")).toBe(
    "Oct 9, 2026",
  );
  expect(evaluatedLabel("2026-10-09", "2026-10-10", "en-US", true)).toBe(
    "Friday, October 9, 2026",
  );
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
