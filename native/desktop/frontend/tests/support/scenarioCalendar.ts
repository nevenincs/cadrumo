import { expect, type Page } from "@playwright/test";
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

/** The day the fixture calendar was evaluated on, at noon. */
export const FIXTURE_DAY = new Date(2026, 9, 6, 12);
