import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";
import { calendarReads, FIXTURE_DAY } from "../support/scenarioCalendar";
import { fixtureDay, fixtureYear } from "../../src/dev/fixtureDates";

// Which filing year the calendar page looks at is the person's choice, and
// the range it asks the product for follows it: a past period is served only
// for a range that reaches its deadline.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
  await seedLayout(target);
  await target.clock.setFixedTime(FIXTURE_DAY);
});

/** The ranges the shell has asked the host for, in order. */
const asked = (target: Page) =>
  target.evaluate(() =>
    (window as unknown as { __scenarioHostCalls: string[] }).__scenarioHostCalls
      .filter((made) => made.startsWith("filingCalendar "))
      .map((made) => {
        const [, from, to] = made.split(" ");
        return { from: from!, to: to! };
      }),
  );

const shown = async (target: Page) => {
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page.locator(".calendar-months")).toBeVisible();
  return page;
};

test("the default view asks for the rolling range around today", async ({
  page: target,
}) => {
  const page = await shown(target);
  await expect.poll(calendarReads(target)).toBe(1);
  const [range] = await asked(target);
  expect(range!.from <= fixtureDay(10, 6)).toBe(true);
  expect(range!.to >= fixtureDay(10, 6)).toBe(true);
  // No year is chosen until the person chooses one.
  await expect(
    page.getByRole("group", { name: label("desktop.calendar.year") }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: label("desktop.calendar.year_current") }),
  ).toHaveCount(0);
});

test("choosing a past filing year asks for a range that reaches its October 20", async ({
  page: target,
}) => {
  const page = await shown(target);
  await expect.poll(calendarReads(target)).toBe(1);
  await page
    .getByRole("button", { name: label("desktop.calendar.year_previous") })
    .click();
  // One read for the change, and the range holds the past year's deadline.
  await expect.poll(calendarReads(target)).toBe(2);
  const ranges = await asked(target);
  const range = ranges[1]!;
  const wanted = fixtureDay(10, 20, -1);
  expect(range.from <= wanted).toBe(true);
  expect(range.to >= wanted).toBe(true);
  expect(Number(range.to.slice(0, 4)) - Number(range.from.slice(0, 4))).toBe(0);
  // The page names the year it was asked for, and keeps showing the rows
  // the fixture serves for it.
  await expect(
    page.getByRole("group", { name: label("desktop.calendar.year") }),
  ).toContainText(String(fixtureYear - 1));
  await expect(page.locator(".calendar-months")).toBeVisible();
  // Back to the current view asks for today's rolling range again.
  await page
    .getByRole("button", { name: label("desktop.calendar.year_current") })
    .click();
  await expect.poll(calendarReads(target)).toBe(3);
  expect((await asked(target))[2]).toEqual(ranges[0]);
});

test("a year that cannot be read leaves the rows and the year as they were", async ({
  page: target,
}) => {
  const page = await shown(target);
  const rows = page.locator(".calendar-months [data-entry]");
  const before = await rows.count();
  expect(before).toBeGreaterThan(0);
  await target.evaluate(() => {
    window.__scenarioCalendarRefused = true;
  });
  await page
    .getByRole("button", { name: label("desktop.calendar.year_previous") })
    .click();
  await expect.poll(calendarReads(target)).toBe(2);
  await expect(
    page.locator(".calendar-controls").getByRole("status"),
  ).toContainText(label("desktop.calendar.year_failed"));
  // Neither drawn as an empty calendar nor as a failed page.
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(await rows.count()).toBe(before);
  await expect(
    page.getByRole("button", { name: label("desktop.calendar.year_current") }),
  ).toHaveCount(0);
  // Asking again, once it can be read, shows the year.
  await target.evaluate(() => {
    window.__scenarioCalendarRefused = false;
  });
  await page
    .getByRole("button", { name: label("desktop.calendar.year_previous") })
    .click();
  await expect.poll(calendarReads(target)).toBe(3);
  await expect(
    page.getByRole("group", { name: label("desktop.calendar.year") }),
  ).toContainText(String(fixtureYear - 1));
  await expect(
    page.locator(".calendar-controls").getByRole("status"),
  ).toHaveCount(0);
});

test("the year can be changed from the keyboard", async ({ page: target }) => {
  const page = await shown(target);
  const next = page.getByRole("button", {
    name: label("desktop.calendar.year_next"),
  });
  await next.focus();
  await expect(next).toBeFocused();
  await target.keyboard.press("Enter");
  await expect.poll(calendarReads(target)).toBe(2);
  const wanted = fixtureDay(10, 20, 1);
  const range = (await asked(target))[1]!;
  expect(range.from <= wanted && wanted <= range.to).toBe(true);
  await expect(
    page.getByRole("group", { name: label("desktop.calendar.year") }),
  ).toContainText(String(fixtureYear + 1));
  // The group is reached by Tab in order, previous before next.
  const previous = page.getByRole("button", {
    name: label("desktop.calendar.year_previous"),
  });
  await previous.focus();
  await target.keyboard.press("Tab");
  await expect(next).toBeFocused();
  await target.keyboard.press("Space");
  await expect.poll(calendarReads(target)).toBe(3);
});
