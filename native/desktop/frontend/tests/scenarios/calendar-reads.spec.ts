import { expect, test } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import {
  startFromDocs,
  open,
  password,
  submit,
  calls,
} from "../support/scenarioShell";
import { calendarButton, messagesButton } from "../support/scenarioRail";
import { calendarReads, FIXTURE_DAY } from "../support/scenarioCalendar";

// When the filing calendar is read: on showing, after sign-out, past midnight, and when a read fails.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("the filing calendar is a page of the first pane, read when it is shown", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.clock.setFixedTime(FIXTURE_DAY);
  await open(target, "signed-in");
  const pane = target.locator(".pane-docs");
  await expect(pane.locator(".docs-frame")).toBeVisible();
  // Nothing is read for a page nobody is looking at.
  expect(await calendarReads(target)()).toBe(0);
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  await expect(calendarButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.calendar.title"),
  );
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toBeFocused();
  // A pane shows one face of the calendar at a time, the months first; the
  // list is the other, and says where each obligation stands.
  await expect(page.locator(".calendar-months")).toBeVisible();
  await expect(page.locator(".calendar-list")).toHaveCount(0);
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await expect(page.locator(".calendar-months")).toHaveCount(0);
  const rows = page.locator(".calendar-list li[data-entry]");
  // The obligations, by month, each with the product's own reading. A
  // month in which something was only observed has its heading too.
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(5);
  await expect(rows).toHaveCount(9);
  await expect(rows.filter({ hasText: "2026-3T" })).toHaveCount(4);
  const late = rows.filter({ hasText: "2026-2T" }).first();
  await expect(late).toContainText(label("desktop.calendar.state.late"));
  await expect(late).toContainText(label("desktop.calendar.aeat.not_observed"));
  // How the range stands, in the product's four readings, the pressing
  // ones first: one late, five due, one unknown, two filed.
  await expect(page.locator(".calendar-standing [data-slot=badge]")).toHaveText(
    [
      ["late", 1],
      ["due", 5],
      ["unknown", 1],
      ["filed", 2],
    ].map(
      ([kind, count]) => `${label(`desktop.calendar.state.${kind}`)} ${count}`,
    ),
  );
  // How far each is: lateness in the product's own days, a near date in
  // days, a far one in months.
  const said = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  await expect(late).toContainText(said.format(-78, "day"));
  await expect(rows.filter({ hasText: "2026-3T" }).last()).toContainText(
    said.format(14, "day"),
  );
  await expect(rows.filter({ hasText: "2026-4T" })).toContainText(
    said.format(3, "month"),
  );
  // The standing is a list of readings, each with its count.
  await expect(page.locator("ul.calendar-standing > li")).toHaveCount(4);
  // Read aloud, each obligation says its whole date, not a day and a
  // weekday that only the heading above makes a date.
  await expect(late.locator("time .sr-only")).toHaveText(
    new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(
      new Date(2026, 6, 20),
    ),
  );
  await expect(late.locator("time [aria-hidden=true]")).toHaveCount(2);
  // Where the past ends is marked once, in the language's word for today,
  // between the last obligation behind and the first one ahead.
  const mark = page.getByRole("separator");
  await expect(mark).toHaveCount(1);
  await expect(mark).toHaveAccessibleName(
    new RegExp(`^${said.format(0, "day")} · `, "i"),
  );
  expect(
    await page.evaluate((element) => {
      const order = [
        ...element.querySelectorAll(".calendar-today, li[data-entry]"),
      ];
      const at = order.findIndex((node) =>
        node.classList.contains("calendar-today"),
      );
      const dates = (nodes: Element[]) =>
        nodes.map((node) => node.querySelector("time")?.dateTime ?? "");
      return {
        behind: dates(order.slice(0, at)),
        ahead: dates(order.slice(at + 1)),
      };
    }),
  ).toEqual({
    behind: ["2026-07-20", "2026-07-20"],
    ahead: [
      "2026-10-20",
      "2026-10-20",
      "2026-10-20",
      "2026-10-20",
      "2027-02-01",
      "2027-02-01",
      "2027-06-30",
    ],
  });
  // The list opens on that mark, not on the oldest thing in the range.
  await expect(mark).toBeInViewport();
  // What was observed stands in its month, apart from what is due: two
  // filings and a message, each with its day and the product's sentence.
  const observed = page.getByRole("list", {
    name: label("desktop.calendar.observed"),
  });
  await expect(observed).toHaveCount(3);
  await expect(observed.locator("li")).toHaveText([
    new RegExp(
      `^Jul 17 · ${label("desktop.calendar.event.filing")} · Modelo 303 2026-2T filed$`,
    ),
    new RegExp(`^Sep 3 · ${label("desktop.calendar.event.message")} · `),
    new RegExp(
      `^Oct 2 · ${label("desktop.calendar.event.filing")} · Modelo 111 2026-3T filed$`,
    ),
  ]);
  // What could not be determined is said, not left out.
  await expect(page).toContainText("347");
  await expect.poll(calendarReads(target)).toBe(1);
  // A whole year is asked for, in whole months.
  const asked = await target.evaluate(() =>
    (
      window as unknown as { __scenarioHostCalls: string[] }
    ).__scenarioHostCalls.find((made) => made.startsWith("filingCalendar ")),
  );
  const expected = await target.evaluate(() => {
    const iso = (day: Date) =>
      [
        day.getFullYear(),
        String(day.getMonth() + 1).padStart(2, "0"),
        String(day.getDate()).padStart(2, "0"),
      ].join("-");
    const today = new Date();
    // From the first day three months back to the last day eight ahead.
    return `filingCalendar ${iso(
      new Date(today.getFullYear(), today.getMonth() - 3, 1),
    )} ${iso(new Date(today.getFullYear(), today.getMonth() + 9, 0))}`;
  });
  expect(asked).toBe(expected);
  // No row offers a way to a place the window cannot reach.
  await expect(
    page.getByRole("button", { name: label("desktop.calendar.open_tui") }),
  ).toHaveCount(0);
});

test("a calendar read again after a sign-out opens on the current month, as the first did", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1280, height: 640 });
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const october = page.locator('.calendar-month[data-month="2026-10"] h2');
  await expect(october).toBeInViewport();
  const first = await page.evaluate((element) => element.scrollTop);
  expect(first).toBeGreaterThan(100);
  // Something is chosen, and then the profile is signed out.
  const chosen = page
    .locator('.calendar-bar[data-entry="303:2026-3T"]')
    .first();
  await chosen.click();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  // Signed out from the page, and in again from it.
  await target.keyboard.press("ControlOrMeta+k");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.account.sign_out"));
  await target.keyboard.press("Enter");
  await expect(page).toContainText(label("desktop.calendar.signed_out"));
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await password(target).fill("demo");
  await submit(target).click();
  await expect(october).toBeInViewport();
  expect(await page.evaluate((element) => element.scrollTop)).toBe(first);
  // Nothing made of the page before is carried into the new sign-in.
  await expect(chosen).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("[data-selected]")).toHaveCount(0);
});

test("a calendar left on screen past midnight is read again for the new day", async ({
  page: target,
}) => {
  await target.clock.install({ time: new Date(2026, 9, 6, 23, 59, 40) });
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  const mark = page.getByRole("separator");
  const said = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  await expect(mark).toHaveAccessibleName(
    new RegExp(`^${said.format(0, "day")} · `, "i"),
  );
  await expect.poll(calendarReads(target)).toBe(1);
  // Every distance on the page is counted from the day it was read: at
  // midnight it is asked for again, without anyone touching it.
  await target.clock.fastForward("01:00");
  await expect.poll(calendarReads(target)).toBe(2);
  // The fixture still answers for the sixth, which is no longer today.
  await expect(mark).toHaveAccessibleName(
    new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(FIXTURE_DAY),
  );
  // Put away, nothing is read at the next midnight for a page nobody sees.
  await calendarButton(target).click();
  await target.clock.fastForward("24:00:00");
  await target.clock.runFor(1000);
  expect(await calendarReads(target)()).toBe(2);
});

test("the calendar is not read again for being put away and brought back", async ({
  page: target,
}) => {
  await target.clock.install();
  await open(target, "signed-in");
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  for (let round = 0; round < 3; round++) {
    await calendarButton(target).click();
    await expect(page.getByRole("listitem").first()).toBeVisible();
    await calendarButton(target).click();
    await expect(page).toHaveCount(0);
  }
  expect(await calendarReads(target)()).toBe(1);
  // Refresh always asks.
  await calendarButton(target).click();
  await page
    .getByRole("button", { name: label("desktop.calendar.refresh") })
    .click();
  await expect.poll(calendarReads(target)).toBe(2);
  await calendarButton(target).click();
  // Shown anew after a while, it is read again.
  await target.clock.runFor(31_000);
  await calendarButton(target).click();
  await expect.poll(calendarReads(target)).toBe(3);
  await expect(page.getByRole("listitem").first()).toBeVisible();
});

test("the calendar asks for a sign-in, then reads; a sign-out drops what was read", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(target.locator(".sign-in")).toBeVisible();
  await target.keyboard.press("Escape");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toContainText(label("desktop.calendar.signed_out"));
  expect(await calendarReads(target)()).toBe(0);
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await password(target).fill("demo");
  await submit(target).click();
  await expect(page.getByRole("listitem").first()).toBeVisible();
  await expect.poll(calendarReads(target)).toBe(1);
  // Signed out again, nothing of the profile stays on screen.
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .locator(".account-menu")
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(page).toContainText(label("desktop.calendar.signed_out"));
  await expect(page.getByRole("listitem")).toHaveCount(0);
});

test("views-refused: a read that fails is said, never drawn as an empty calendar", async ({
  page: target,
}) => {
  await open(target, "views-refused");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page.getByRole("alert")).toContainText(
    label("desktop.calendar.failed"),
  );
  await expect(page.getByRole("alert")).not.toContainText("timed_out");
  await expect(page).not.toContainText(label("desktop.calendar.empty"));
  await expect.poll(calendarReads(target)).toBe(1);
  const again = page.getByRole("button", {
    name: label("desktop.calendar.refresh"),
  });
  // Marked, so the same elements can be told from new ones afterwards.
  await page.getByRole("alert").evaluate((node) => {
    node.setAttribute("data-heard", "");
  });
  await again.evaluate((node) => node.setAttribute("data-kept", ""));
  // Both refusals so far, the calendar's and the messages', are on
  // screen, so the status read each asked for has been made.
  await expect(messagesButton(target).locator("[data-pin=failed]")).toHaveCount(
    1,
  );
  const statusReads = await calls(target, "signInStatus")();
  await again.focus();
  await target.keyboard.press("Enter");
  await expect.poll(calendarReads(target)).toBe(2);
  await expect(page.getByRole("alert")).toContainText(
    label("desktop.calendar.failed"),
  );
  await expect(page.getByRole("alert")).not.toContainText("timed_out");
  // The button that asked is the same one, and still holds the keyboard.
  await expect(again).toBeFocused();
  await expect(again).toHaveAttribute("data-kept", "");
  // The failure is said by a new alert, so it is heard a second time.
  await expect(page.getByRole("alert")).not.toHaveAttribute("data-heard");
  // This refusal has the account looked at again: one more status read.
  await expect.poll(calls(target, "signInStatus")).toBe(statusReads + 1);
});

test("unsupported: where sign-in is the TUI's, the calendar is asked for and shown", async ({
  page: target,
}) => {
  await open(target, "unsupported");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page.getByRole("listitem").first()).toBeVisible();
  await expect(page).not.toContainText(label("desktop.calendar.signed_out"));
});

test("empty: a calendar with nothing due says so", async ({ page: target }) => {
  await open(target, "empty");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toContainText(label("desktop.calendar.empty"));
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("no-views: a host that offers no profile views shows no way into one", async ({
  page: target,
}) => {
  await open(target, "no-views");
  await showTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(calendarButton(target)).toHaveCount(0);
  await expect(messagesButton(target)).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  for (const key of ["desktop.calendar.title", "desktop.rail.messages"]) {
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label(key));
    await expect(
      palette.locator(".palette-title").filter({ hasText: label(key) }),
    ).toHaveCount(0);
  }
  expect(await calls(target, "notifications")()).toBe(0);
});

test("a calendar shown again after a failed read says the new failure once", async ({
  page: target,
}) => {
  await open(target, "views-refused");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page.getByRole("alert")).toBeVisible();
  await calendarButton(target).click();
  await expect(page).toHaveCount(0);
  // Every alert put into the document from here on is counted.
  await target.evaluate(() => {
    const counted = window as unknown as { alerts: number };
    counted.alerts = 0;
    new MutationObserver((changes) => {
      for (const change of changes)
        for (const node of change.addedNodes)
          if (node instanceof Element)
            counted.alerts +=
              (node.matches("[role=alert]") ? 1 : 0) +
              node.querySelectorAll("[role=alert]").length;
    }).observe(document.body, { childList: true, subtree: true });
  });
  await calendarButton(target).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect.poll(calendarReads(target)).toBe(2);
  expect(
    await target.evaluate(
      () => (window as unknown as { alerts: number }).alerts,
    ),
  ).toBe(1);
});

test("signed out, the calendar offers sign-in and does not read the account again or send the person to the TUI", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  const before = await calls(target, "signInStatus")();
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toContainText(label("desktop.account.signed_out"));
  await expect(page.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  // The account is known to be signed out: opening the page does not ask
  // again, and nothing of the profile is read.
  await target.waitForTimeout(600);
  expect(await calls(target, "signInStatus")()).toBe(before);
  expect(await calendarReads(target)()).toBe(0);
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(password(target)).toBeFocused();
});
