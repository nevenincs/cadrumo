import { expect, test, type Locator, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";
import { calendarReads, FIXTURE_DAY } from "../support/scenarioCalendar";
import { fixtureYear } from "../../src/dev/fixtureDates";
import {
  SUPPORT_BOUNDED,
  SUPPORT_OPEN,
  SUPPORT_PROJECTED,
} from "../../src/dev/fixtures/calendarSupport";

// Where the requested range sits in the filing-year envelope is the
// product's to say, and the page says it: a range the product cannot answer
// for is unsupported, never "nothing due".

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
  await seedLayout(target);
  await target.clock.setFixedTime(FIXTURE_DAY);
});

const shown = async (target: Page, shape: string | null) => {
  await open(target, "signed-in", shape === null ? "" : `&calendar=${shape}`);
  await calendarButton(target).click();
  return target.getByRole("region", { name: label("desktop.calendar.title") });
};

const step = (page: Locator, by: "previous" | "next") =>
  page.getByRole("button", { name: label(`desktop.calendar.year_${by}`) });

const rows = (page: Locator) => page.locator(".calendar-months [data-entry]");

const year = (page: Locator) =>
  page.getByRole("group", { name: label("desktop.calendar.year") });

const words = {
  projectedNote: () =>
    label("desktop.calendar.support_projected", {
      horizon: SUPPORT_PROJECTED.horizon,
    }),
  partial: () =>
    label("desktop.calendar.support_partial", { floor: SUPPORT_OPEN.floor }),
  partialBounded: () =>
    label("desktop.calendar.support_partial_bounded", {
      floor: SUPPORT_BOUNDED.floor,
      ceiling: SUPPORT_BOUNDED.hard_ceiling!,
    }),
  belowFloor: () =>
    label("desktop.calendar.support_below_floor", {
      floor: SUPPORT_OPEN.floor,
    }),
  aboveCeiling: () =>
    label("desktop.calendar.support_above_ceiling", {
      ceiling: SUPPORT_BOUNDED.hard_ceiling!,
    }),
};

test("a supported read draws the calendar with no note", async ({
  page: target,
}) => {
  const page = await shown(target, "support_supported");
  await expect(page.locator(".calendar-months")).toBeVisible();
  expect(await rows(page).count()).toBeGreaterThan(0);
  await expect(page.locator("[data-calendar-support]")).toHaveCount(0);
  await expect(page.getByText(label("desktop.calendar.empty"))).toHaveCount(0);
});

test("a read that carries no support is drawn as supported", async ({
  page: target,
}) => {
  const page = await shown(target, null);
  await expect(page.locator(".calendar-months")).toBeVisible();
  expect(await rows(page).count()).toBeGreaterThan(0);
  await expect(page.locator("[data-calendar-support]")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(step(page, "previous")).toBeEnabled();
  await expect(step(page, "next")).toBeEnabled();
});

test("a projected read keeps its rows and says they are projected", async ({
  page: target,
}) => {
  const page = await shown(target, "support_projected");
  await expect(page.locator(".calendar-months")).toBeVisible();
  expect(await rows(page).count()).toBeGreaterThan(0);
  await expect(page.locator('[data-calendar-support="projected"]')).toHaveText(
    words.projectedNote(),
  );
  await expect(page.getByText(label("desktop.calendar.empty"))).toHaveCount(0);
});

test("a partial read keeps its rows and says part of the range is unsupported", async ({
  page: target,
}) => {
  const page = await shown(target, "support_partial");
  await expect(page.locator(".calendar-months")).toBeVisible();
  expect(await rows(page).count()).toBeGreaterThan(0);
  await expect(page.locator('[data-calendar-support="partial"]')).toHaveText(
    words.partial(),
  );
});

test("a partial read under a hard ceiling names both bounds", async ({
  page: target,
}) => {
  const page = await shown(target, "support_partial_bounded");
  expect(await rows(page).count()).toBeGreaterThan(0);
  await expect(page.locator('[data-calendar-support="partial"]')).toHaveText(
    words.partialBounded(),
  );
});

test("a range below the floor is unsupported, not empty", async ({
  page: target,
}) => {
  const page = await shown(target, "support_below_floor");
  await expect(
    page.locator('[data-calendar-support="below_floor"]'),
  ).toContainText(words.belowFloor());
  await expect(page.locator(".calendar-months")).toHaveCount(0);
  await expect(page.getByText(label("desktop.calendar.empty"))).toHaveCount(0);
  await expect(
    page.getByText(label("desktop.calendar.coverage.no_dates")),
  ).toHaveCount(0);
  // The way to another year stays.
  await expect(step(page, "next")).toBeVisible();
});

test("a range above the ceiling is unsupported, not empty", async ({
  page: target,
}) => {
  const page = await shown(target, "support_above_ceiling");
  await expect(
    page.locator('[data-calendar-support="above_ceiling"]'),
  ).toContainText(words.aboveCeiling());
  await expect(page.locator(".calendar-months")).toHaveCount(0);
  await expect(page.getByText(label("desktop.calendar.empty"))).toHaveCount(0);
  await expect(step(page, "previous")).toBeVisible();
});

test("stepping stops at the floor and at a hard ceiling", async ({
  page: target,
}) => {
  const page = await shown(target, "support_bounded");
  await expect(page.locator(".calendar-months")).toBeVisible();
  // The rolling range falls in the fixture's year, inside both bounds.
  await expect(step(page, "previous")).toBeEnabled();
  await expect(step(page, "next")).toBeEnabled();
  await step(page, "previous").click();
  await expect.poll(calendarReads(target)).toBe(2);
  await expect(year(page)).toContainText(String(SUPPORT_BOUNDED.floor));
  // Nothing before the floor is asked for.
  await expect(step(page, "previous")).toBeDisabled();
  await expect(step(page, "next")).toBeEnabled();
  await step(page, "next").click();
  await expect.poll(calendarReads(target)).toBe(3);
  await step(page, "next").click();
  await expect.poll(calendarReads(target)).toBe(4);
  await expect(year(page)).toContainText(String(SUPPORT_BOUNDED.hard_ceiling));
  await expect(step(page, "next")).toBeDisabled();
  await expect(step(page, "previous")).toBeEnabled();
  // The ceiling is never asked past, by pointer or by force.
  await step(page, "next").click({ force: true });
  expect(await calendarReads(target)()).toBe(4);
});

test("with no hard ceiling the next year can always be asked for", async ({
  page: target,
}) => {
  const page = await shown(target, "support_supported");
  await expect(page.locator(".calendar-months")).toBeVisible();
  for (let count = 1; count <= 3; count++) {
    await expect(step(page, "next")).toBeEnabled();
    await step(page, "next").click();
    await expect.poll(calendarReads(target)).toBe(count + 1);
    await expect(year(page)).toContainText(String(fixtureYear + count));
  }
});

test("a disabled step keeps its name and the other step stays reachable", async ({
  page: target,
}) => {
  const page = await shown(target, "support_bounded");
  await step(page, "previous").click();
  await expect.poll(calendarReads(target)).toBe(2);
  await expect(step(page, "previous")).toBeDisabled();
  await expect(year(page)).toBeVisible();
  await step(page, "next").focus();
  await expect(step(page, "next")).toBeFocused();
  await target.keyboard.press("Enter");
  await expect.poll(calendarReads(target)).toBe(3);
});
