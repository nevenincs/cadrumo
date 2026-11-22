import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import {
  UNANSWERED_IVA_REASON,
  UNANSWERED_IVA_WARNINGS,
} from "../../src/dev/fixtures/calendarSuppressed";
import { fixtureYear } from "../../src/dev/fixtureDates";

// A profile that claims the IVA block and leaves its yes/no questions
// unanswered: the calendar loads, says which 303 window it could not decide
// and why, and offers the way to the profile where the questions are answered.

async function openCalendar(page: Page, extra: string) {
  await page.goto(`/scenarios.html?scenario=signed-in&latency=0${extra}`);
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.calendar.title") })
    .click();
  return page.getByRole("region", { name: label("desktop.calendar.title") });
}

test("an unanswered IVA question leaves its 303 window undecided, with its reason and the way to the profile", async ({
  page,
}) => {
  const calendar = await openCalendar(page, "&calendar=unanswered_iva");
  // The calendar loads: its rows are drawn and no failure is said.
  await expect(calendar.locator("[data-entry]").first()).toBeVisible();
  await expect(calendar).not.toContainText(label("desktop.calendar.failed"));
  await expect(calendar.getByRole("alert")).toHaveCount(0);
  // The 303 window it could not decide is held apart, with the reason the
  // product served, which names the unanswered question.
  const held = calendar.locator(
    `[data-suppressed="303:${fixtureYear}-3T"][data-verdict="incomplete"]`,
  );
  await expect(held).toContainText(
    "Synthetic words served for the incomplete verdict.",
  );
  await expect(held.locator("[data-suppressed-reason]")).toHaveText(
    UNANSWERED_IVA_REASON,
  );
  // 303 is advised as undetermined.
  await expect(calendar).toContainText(
    label("desktop.calendar.coverage.applicability_undetermined", {
      modelos: new Intl.ListFormat("en", { type: "conjunction" }).format([
        "303",
        "347",
      ]),
    }),
  );
  // Each unanswered question is said in the served words, in the notice
  // beside the way to the profile; its heading is the profile's own standing.
  const notice = calendar.getByRole("status").filter({
    has: page.getByRole("link", {
      name: label("desktop.profile.notice.open_profile"),
    }),
  });
  await notice
    .getByRole("button", { name: label("desktop.profile.notice.show_details") })
    .click();
  for (const words of UNANSWERED_IVA_WARNINGS)
    await expect(notice.getByText(words, { exact: true })).toBeVisible();
  await expect(
    notice.getByRole("link", {
      name: label("desktop.profile.notice.open_profile"),
    }),
  ).toBeVisible();
  // The held row's own way to the profile opens the profile page.
  await held
    .getByRole("link", { name: label("desktop.profile.notice.open_profile") })
    .click();
  await expect(page.locator(".user-profile-page")).toBeVisible();
});

test("a held row the product decided keeps its verdict words alone", async ({
  page,
}) => {
  const calendar = await openCalendar(page, "&calendar=unanswered_iva");
  const decided = calendar.locator(
    `[data-suppressed="115:${fixtureYear}-3T"][data-verdict="not_applicable"]`,
  );
  await expect(decided).toHaveText(
    /Synthetic words served for the not_applicable verdict\./,
  );
  await expect(decided).not.toContainText("Synthetic registry reason");
  await expect(decided.getByRole("link")).toHaveCount(0);
});

test("a refused calendar read says the product's words for why", async ({
  page,
}) => {
  const words = "Synthetic words the product served for refusing the read.";
  await page.addInitScript((served) => {
    window.__scenarioCalendarRefusalWords = served;
  }, words);
  const calendar = await openCalendar(page, "");
  await expect(calendar.getByRole("alert")).toHaveText(
    label("desktop.calendar.failed"),
  );
  await expect(calendar.locator("[data-calendar-failure]")).toHaveText(words);
});

test("a failed calendar read without served words names its code", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.__scenarioCalendarRefused = true;
  });
  const calendar = await openCalendar(page, "");
  await expect(calendar.getByRole("alert")).toHaveText(
    label("desktop.calendar.failed"),
  );
  await expect(calendar.locator("[data-calendar-failure]")).toHaveText(
    label("desktop.operations.error_code", { code: "timed_out" }),
  );
});
