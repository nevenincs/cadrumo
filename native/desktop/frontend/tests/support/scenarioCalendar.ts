import { expect, type Page } from "@playwright/test";
import { FIXTURE_TODAY } from "../../src/dev/fixtures/calendar";
import { BUSY_TODAY } from "../../src/dev/fixtures/calendarBusy";
import { calendarButton } from "./scenarioRail";

/** Navigating to another fixture restores the selected page. */
export const showCalendar = async (target: Page, locale = "en") => {
  const toggle = calendarButton(target, locale);
  if ((await toggle.getAttribute("aria-pressed")) !== "true")
    await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
};

/** How many times the shell has asked the host for the filing calendar. */
export const calendarReads = (target: Page) => () =>
  target.evaluate(
    () =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter((made) =>
        made.startsWith("filingCalendar "),
      ).length ?? 0,
  );

/** An ISO day at local noon. */
const noonOf = (iso: string): Date => {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year!, month! - 1, day!, 12);
};

/** The day the fixture calendar was evaluated on, at noon. */
export const FIXTURE_DAY = noonOf(FIXTURE_TODAY);

/** The day the busy calendar was evaluated on, at noon. */
export const BUSY_DAY = noonOf(BUSY_TODAY);

/** The runs of days a window from `from` to `to` (ISO days) is drawn in when
 * weeks begin on `weekStart` (0 is Sunday): one `[first, last]` pair for each
 * week it crosses, cut at the week's edges. */
export const weekRuns = (
  from: string,
  to: string,
  weekStart: number,
): [string, string][] => {
  const iso = (date: Date) =>
    `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")}`;
  const parse = (text: string) => {
    const [year, month, day] = text.split("-").map(Number);
    return new Date(Date.UTC(year!, month! - 1, day!));
  };
  const runs: [string, string][] = [];
  const last = parse(to);
  let first = parse(from);
  while (first <= last) {
    const toWeekEnd = (weekStart + 6 - first.getUTCDay() + 7) % 7;
    const end = new Date(first.getTime() + toWeekEnd * 86_400_000);
    const stop = end < last ? end : last;
    runs.push([iso(first), iso(stop)]);
    first = new Date(stop.getTime() + 86_400_000);
  }
  return runs;
};
