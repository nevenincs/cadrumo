import { expect, test, type Locator } from "@playwright/test";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";
import {
  showCalendar,
  calendarReads,
  FIXTURE_DAY,
  weekRuns,
} from "../support/scenarioCalendar";
import {
  fixtureDay,
  fixtureMonth,
  fixtureYear,
} from "../../src/dev/fixtureDates";

// The calendar's months: filing windows across their days, week start, the list beside them and the legend.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("the calendar's months draw each filing window across the days it is open", async ({
  page: target,
}) => {
  // Short enough that the months before the current one cannot all be in
  // view with it: opening on it is something the page has to do.
  await target.setViewportSize({ width: 1280, height: 640 });
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const months = page.locator(".calendar-month");
  await expect(months.first()).toBeAttached();
  expect(await page.evaluate((element) => element.scrollTop)).toBeGreaterThan(
    100,
  );
  await expect(months.first().getByRole("heading")).not.toBeInViewport();
  // Every month of the range that was read, each under its own name.
  await expect(months).toHaveCount(12);
  await expect(months.first().getByRole("heading", { level: 2 })).toHaveText(
    new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(
      new Date(fixtureYear, 6, 1),
    ),
  );
  // It opens on the month the product evaluated in, with that day marked.
  const october = page.locator(
    `.calendar-month[data-month="${fixtureMonth(10)}"]`,
  );
  await expect(october.getByRole("heading", { level: 2 })).toBeInViewport();
  await expect(page.locator(".calendar-grid-today")).toHaveText(["6"]);
  await expect(
    october.locator(`[data-day="${fixtureDay(10, 6)}"] .calendar-grid-today`),
  ).toHaveCount(1);

  // Where on the page a day and a window are.
  const edges = async (locator: Locator) => {
    const box = (await locator.boundingBox())!;
    return { left: box.x, right: box.x + box.width, top: box.y };
  };
  const dayOf = (iso: string) => page.locator(`[data-day="${iso}"]`);
  // A window open from the first to the twentieth is drawn in each week it
  // crosses, where the week begins on Sunday: from its first day to the
  // week's end, across the whole weeks, and up to its closing day.
  const window303 = october.locator(
    `.calendar-bar[data-entry="303:${fixtureYear}-3T"]`,
  );
  const spans = weekRuns(fixtureDay(10, 1), fixtureDay(10, 20), 0);
  expect(spans.length).toBeGreaterThan(1);
  await expect(window303).toHaveCount(spans.length);
  const continued = spans.map((_, index) => index).slice(1);
  for (const [index, [from, to]] of spans.entries()) {
    const bar = await edges(window303.nth(index));
    const first = await edges(dayOf(from));
    const last = await edges(dayOf(to));
    expect(Math.abs(bar.left - first.left), from).toBeLessThanOrEqual(3);
    expect(Math.abs(bar.right - last.right), to).toBeLessThanOrEqual(3);
    // Under the days it covers, not over them.
    expect(bar.top, from).toBeGreaterThan(first.top);
  }
  // It is one thing to hear and to reach, said once with its days and where
  // it stands; the rest of it is for the eye.
  const short = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
  });
  await expect(window303.first()).toHaveAccessibleName(
    [
      `${label("desktop.calendar.modelo", { modelo: "303" })} ${fixtureYear}-3T`,
      short.formatRange(
        new Date(fixtureYear, 9, 1),
        new Date(fixtureYear, 9, 20),
      ),
      label("desktop.calendar.state.due"),
    ].join(", "),
  );
  await expect(
    page.getByRole("button", { name: new RegExp(`303.* ${fixtureYear}-3T`) }),
  ).toHaveCount(1);
  for (const index of continued) {
    await expect(window303.nth(index)).toHaveAttribute("aria-hidden", "true");
    await expect(window303.nth(index)).toHaveAttribute("tabindex", "-1");
  }
  // It is named in full once in the month, where it is first drawn; the
  // weeks it goes on across carry its Modelo alone.
  await expect(window303.getByText("303", { exact: true })).toHaveCount(
    spans.length,
  );
  await expect(window303.first().getByText(`${fixtureYear}-3T`)).toBeVisible();
  for (const index of continued)
    await expect(
      window303.nth(index).getByText(`${fixtureYear}-3T`),
    ).toBeHidden();
  // A window closes with a rounded pill end and has no border.
  const measures = await window303.last().evaluate((bar) => ({
    closing: getComputedStyle(bar).borderRightWidth,
    radius: getComputedStyle(bar).borderTopRightRadius,
    opening: getComputedStyle(bar).borderLeftWidth,
  }));
  expect(measures.closing).toBe("0px");
  expect(measures.radius).not.toBe("0px");
  expect(measures.opening).toBe("0px");
  // Pressed, a part that is only for the eye chooses the obligation and
  // leaves the keyboard on the part that is its stop, the view unmoved.
  await window303.nth(2).scrollIntoViewIfNeeded();
  const before = await page.evaluate((element) => element.scrollTop);
  await window303.nth(2).click();
  await expect(window303.first()).toHaveAttribute("aria-pressed", "true");
  await expect(window303.first()).toBeFocused();
  expect(await page.evaluate((element) => element.scrollTop)).toBe(before);
  await window303.first().click();
  await expect(window303.first()).toHaveAttribute("aria-pressed", "false");
  // Windows open over the same days each keep a row of their own.
  const tops = new Set<number>();
  for (const key of [
    `111:${fixtureYear}-3T`,
    `130:${fixtureYear}-3T`,
    `303:${fixtureYear}-3T`,
  ])
    tops.add(
      Math.round(
        (
          await edges(
            october.locator(`.calendar-bar[data-entry="${key}"]`).first(),
          )
        ).top,
      ),
    );
  expect(tops.size).toBe(3);
  // How it stands is drawn, and never only by colour: the list says it.
  await expect(window303.first()).toHaveAttribute("data-state", "due");
  await expect(
    october
      .locator(`.calendar-bar[data-entry="111:${fixtureYear}-3T"]`)
      .first(),
  ).toHaveAttribute("data-state", "filed");

  // A window whose opening was not reported is not guessed at: its closing
  // day alone is drawn, and it says the opening is not known.
  const unknown = page.locator(
    `.calendar-bar[data-entry="349:${fixtureYear}-3T"]`,
  );
  await expect(unknown).toHaveCount(1);
  const closing = await edges(dayOf(fixtureDay(10, 20)));
  const drawn = await edges(unknown);
  expect(Math.abs(drawn.left - closing.left)).toBeLessThanOrEqual(3);
  expect(Math.abs(drawn.right - closing.right)).toBeLessThanOrEqual(3);
  await expect(unknown).toHaveAccessibleName(
    new RegExp(
      `${short.format(new Date(fixtureYear, 9, 20))} \\(${label("desktop.calendar.window_unknown")}\\)`,
    ),
  );

  // A window that runs from one month into the next is drawn in both: the
  // fourth quarter's, moved from a Saturday to the Monday after.
  await expect(
    page.locator(
      `.calendar-month[data-month="${fixtureMonth(1, 1)}"] .calendar-bar[data-entry="303:${fixtureYear}-4T"]`,
    ),
  ).not.toHaveCount(0);
  await expect(
    page.locator(
      `.calendar-month[data-month="${fixtureMonth(2, 1)}"] .calendar-bar[data-entry="303:${fixtureYear}-4T"]`,
    ),
  ).toHaveCount(1);

  // What was observed stands on its own day: the profile's filings and the
  // agency's message, each said with its date and the product's sentence.
  const events = page.locator(".calendar-event");
  await expect(events).toHaveCount(3);
  const filed = dayOf(fixtureDay(10, 2)).locator(".calendar-event");
  await expect(filed).toHaveAttribute("data-event", "filing");
  await expect(filed).toHaveAccessibleName(
    `${new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(
      new Date(fixtureYear, 9, 2),
    )}: ${label("desktop.calendar.event.filing")}. Modelo 111 ${fixtureYear}-3T filed`,
  );
  await expect(
    dayOf(fixtureDay(9, 3)).locator(".calendar-event"),
  ).toHaveAttribute("data-event", "message");
  // Nothing was read a second time to draw the months.
  expect(await calendarReads(target)()).toBe(1);
});

test("the months begin the week on the day the language does", async ({
  page: target,
}) => {
  // The first Sunday and the first Monday of the month.
  const firstOn = (weekday: number) =>
    new Date(
      fixtureYear,
      9,
      1 + ((weekday - new Date(fixtureYear, 9, 1).getDay() + 7) % 7),
    );
  for (const [language, first] of [
    ["en", firstOn(0)],
    ["es", firstOn(1)],
    ["hu", firstOn(1)],
  ] as const) {
    await open(target, "signed-in", `&lang=${language}`);
    await showCalendar(target, language);
    const october = target.locator(
      `.calendar-month[data-month="${fixtureMonth(10)}"]`,
    );
    // The first of its weekday letters, and the day under it in the first
    // whole week: a Sunday in English, a Monday in Spanish and Hungarian.
    await expect(
      october.locator("[aria-hidden=true] > span").first(),
    ).toHaveText(
      new Intl.DateTimeFormat(language, { weekday: "narrow" }).format(first),
    );
    const iso = fixtureDay(10, first.getDate());
    await expect(october.locator('[data-day="' + iso + '"]')).toHaveCSS(
      "grid-column-start",
      "1",
    );
  }
});

test("a maximized calendar shows the months and the list together, and one marks what the other chose", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const view = page.getByRole("radiogroup", {
    name: label("desktop.calendar.view"),
  });
  // In a pane: one face, and the choice between them.
  await expect(view).toBeVisible();
  await expect(page.locator(".calendar-list")).toHaveCount(0);
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  // With room for both: the months, and the list as a second column that
  // scrolls by itself. There is nothing left to choose between.
  const months = page.locator(".calendar-months");
  const list = page.locator(".calendar-aside");
  await expect(list.locator("li[data-entry]")).toHaveCount(9);
  await expect(months).toBeVisible();
  await expect(view).toHaveCount(0);
  const left = (await months.boundingBox())!;
  const right = (await list.boundingBox())!;
  expect(right.x).toBeGreaterThanOrEqual(left.x + left.width - 1);
  // The column is as tall as the page and stays while the months scroll.
  const frame = (await page.boundingBox())!;
  expect(Math.abs(right.height - frame.height)).toBeLessThanOrEqual(2);
  // Each opens on where the person is: the current month, and today's mark.
  await expect(
    page.locator(`.calendar-month[data-month="${fixtureMonth(10)}"] h2`),
  ).toBeInViewport();
  await expect(list.getByRole("separator")).toBeInViewport();
  expect(await list.evaluate((element) => element.scrollTop)).toBeGreaterThan(
    0,
  );

  // Chosen among the months, an obligation is marked in the list, and all
  // of its window is marked among the months.
  const bars = page.locator(
    `.calendar-bar[data-entry="303:${fixtureYear}-4T"]`,
  );
  const row = list.locator(`li[data-entry="303:${fixtureYear}-4T"]`);
  await expect(row).not.toHaveAttribute("aria-current");
  await bars.first().scrollIntoViewIfNeeded();
  await bars.first().click();
  await expect(bars.first()).toHaveAttribute("aria-pressed", "true");
  await expect(row).toHaveAttribute("aria-current", "true");
  await expect(row).toBeInViewport();
  await expect(row.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  expect(await bars.count()).toBeGreaterThan(1);
  await expect(page.locator(".calendar-bar[data-selected]")).toHaveCount(
    await bars.count(),
  );
  // Chosen in the list, the last obligation of the range is brought into
  // view among the months, and it alone is chosen.
  const far = page
    .locator(`.calendar-bar[data-entry="100:${fixtureYear}"]`)
    .first();
  await expect(far).not.toBeInViewport();
  await list
    .locator(`li[data-entry="100:${fixtureYear}"]`)
    .getByRole("button")
    .click();
  await expect(far).toHaveAttribute("aria-pressed", "true");
  await expect(far).toBeInViewport();
  await expect(row).not.toHaveAttribute("aria-current");
  await expect(list.locator('[aria-current="true"]')).toHaveCount(1);
  await expect(bars.first()).toHaveAttribute("aria-pressed", "false");
  // The window's own row of controls does not cover what was brought in.
  const head = (await page.locator(".calendar-head").boundingBox())!;
  expect((await far.boundingBox())!.y).toBeGreaterThanOrEqual(
    head.y + head.height,
  );

  // Back in a pane the choice is kept, and each face opens on it.
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.restore") })
    .click();
  await expect(view).toBeVisible();
  await expect(far).toHaveAttribute("aria-pressed", "true");
  await expect(far).toBeInViewport();
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  const kept = page.locator(
    `.calendar-list li[data-entry="100:${fixtureYear}"]`,
  );
  await expect(kept).toHaveAttribute("aria-current", "true");
  await expect(kept).toBeInViewport();
  // Choosing it again lets it go.
  await kept.getByRole("button").click();
  await expect(page.locator('[aria-current="true"]')).toHaveCount(0);
  expect(await calendarReads(target)()).toBe(1);
});

test("the calendar's mark stands where the past ends in each shape of range, and is called today only on that day", async ({
  page: target,
}) => {
  const said = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const today = new RegExp(`^${said.format(0, "day")} · `, "i");
  const shown = async (shape: string) => {
    await open(target, "signed-in", `&calendar=${shape}`);
    // With the TUI beside it, the calendar has a pane's width.
    await showTui(target);
    await showCalendar(target);
    const page = target.getByRole("region", {
      name: label("desktop.calendar.title"),
    });
    await page
      .getByRole("radio", { name: label("desktop.calendar.view_list") })
      .click();
    const mark = page.getByRole("separator");
    await expect(mark).toHaveCount(1);
    const order = await page.evaluate((element) => {
      const nodes = [
        ...element.querySelectorAll(".calendar-today, li[data-entry]"),
      ];
      const at = nodes.findIndex((node) =>
        node.classList.contains("calendar-today"),
      );
      const section = nodes[at]?.closest("section");
      return {
        behind: at,
        ahead: nodes.length - at - 1,
        // Rows of the mark's own month on each side of it.
        split: [
          nodes
            .slice(0, at)
            .filter((node) => node.closest("section") === section).length,
          nodes
            .slice(at + 1)
            .filter((node) => node.closest("section") === section).length,
        ],
      };
    });
    return { page, mark, order };
  };
  await target.clock.setFixedTime(FIXTURE_DAY);
  // Everything behind: the mark closes the list, after the last row.
  let found = await shown("behind");
  expect(found.order).toMatchObject({ behind: 2, ahead: 0 });
  await expect(found.mark).toHaveAccessibleName(today);
  await expect(found.mark).toBeInViewport();
  // Everything ahead: the mark opens the list, before the first month.
  found = await shown("ahead");
  expect(found.order).toMatchObject({ behind: 0, ahead: 7, split: [0, 4] });
  await expect(found.mark).toHaveAccessibleName(today);
  // The day inside a month: that month is two lists with the mark between.
  found = await shown("straddling");
  expect(found.order).toMatchObject({ behind: 1, ahead: 7, split: [1, 4] });
  await expect(found.mark).toHaveAccessibleName(today);
  // Among the months the same day is the one marked.
  await found.page
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  const cell = found.page.locator(`[data-day="${fixtureDay(10, 6)}"]`);
  await expect(cell.locator(".calendar-grid-today")).toHaveAttribute(
    "data-today",
    "true",
  );
  // Read aloud it is a whole date, with the word for today.
  const whole = new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(
    FIXTURE_DAY,
  );
  await expect(cell.locator(".sr-only")).toHaveText(
    new RegExp(`^${said.format(0, "day")} · ${whole}$`, "i"),
  );

  // A calendar worked out for a day that is not today here does not call
  // that day today: the mark says the day, and stands where it stood.
  await target.clock.setFixedTime(new Date(fixtureYear, 9, 7, 9));
  found = await shown("straddling");
  expect(found.order).toMatchObject({ behind: 1, ahead: 7, split: [1, 4] });
  await expect(found.mark).toHaveAccessibleName(
    new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(FIXTURE_DAY),
  );
  await expect(found.mark).not.toHaveAccessibleName(today);
  // Among the months that day is still marked, as the day the readings
  // are of, and is neither drawn nor said as today.
  await found.page
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  const stale = found.page.locator(`[data-day="${fixtureDay(10, 6)}"]`);
  await expect(stale.locator(".calendar-grid-today")).toHaveAttribute(
    "data-today",
    "false",
  );
  await expect(stale.locator(".sr-only")).toHaveText(whole);
  expect(
    await stale
      .locator(".calendar-grid-today")
      .evaluate((mark) => getComputedStyle(mark).borderTopWidth),
  ).toBe("1px");
  await expect(found.page.locator('[data-today="true"]')).toHaveCount(0);
});

test("a close the product does not know is listed and drawn as unknown, with its earliest close and no countdown", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(FIXTURE_DAY);
  await open(target, "signed-in", "&calendar=close_unknown");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await showCalendar(target);
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  const short = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
  });
  const earliest = (on: Date) =>
    label("desktop.calendar.earliest_close", { date: short.format(on) });
  const ahead = page.locator(
    `.calendar-list li[data-entry="123:${fixtureYear}-3T"]`,
  );
  const passed = page.locator(
    `.calendar-list li[data-entry="115:${fixtureYear}-2T"]`,
  );
  for (const [row, on] of [
    [ahead, new Date(fixtureYear, 9, 20)],
    [passed, new Date(fixtureYear, 6, 20)],
  ] as const) {
    // Kept in the list, called by the product's own words for it.
    await expect(row).toBeVisible();
    await expect(row.locator("[data-slot=badge]")).toHaveText(
      label("workspace.declarations.calendar.legal.unknown"),
    );
    // Its date is said only as the earliest close, never drawn as the day
    // a deadline falls on, and nothing is counted to or from it.
    await expect(row).toContainText(earliest(on));
    await expect(row.locator("time")).toHaveCount(0);
    await expect(row.locator(".calendar-distance")).toHaveCount(0);
    await expect(row).not.toContainText(label("desktop.calendar.state.late"));
  }
  // In the month of its earliest close, after that month's known closes,
  // and after the mark for today only where even its earliest close is
  // ahead of it.
  const order = await page.evaluate((element) =>
    [...element.querySelectorAll(".calendar-today, li[data-entry]")].map(
      (node) =>
        node.classList.contains("calendar-today")
          ? "today"
          : (node.getAttribute("data-entry") ?? ""),
    ),
  );
  const at = (key: string) => order.indexOf(key);
  expect(at(`115:${fixtureYear}-2T`)).toBeGreaterThan(
    at(`130:${fixtureYear}-2T`),
  );
  expect(at(`115:${fixtureYear}-2T`)).toBeGreaterThan(
    at(`303:${fixtureYear}-2T`),
  );
  expect(at(`115:${fixtureYear}-2T`)).toBeLessThan(at("today"));
  expect(at(`123:${fixtureYear}-3T`)).toBeGreaterThan(at("today"));
  for (const known of [
    `303:${fixtureYear}-3T`,
    `130:${fixtureYear}-3T`,
    `111:${fixtureYear}-3T`,
  ])
    expect(at(`123:${fixtureYear}-3T`)).toBeGreaterThan(at(known));
  expect(at(`123:${fixtureYear}-3T`)).toBeLessThan(at(`303:${fixtureYear}-4T`));

  // Among the months the window says the same, and is not drawn closing.
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  const bar = page.locator(
    `.calendar-bar[data-entry="123:${fixtureYear}-3T"]:not([tabindex="-1"])`,
  );
  await expect(bar).toHaveAccessibleName(
    new RegExp(
      `${earliest(new Date(fixtureYear, 9, 20))}.*${label("workspace.declarations.calendar.legal.unknown")}$`,
    ),
  );
  await expect(
    page.locator(
      `.calendar-bar[data-entry="123:${fixtureYear}-3T"].rounded-r-full`,
    ),
  ).toHaveCount(0);
  await expect(
    page.locator(
      `.calendar-bar[data-entry="130:${fixtureYear}-3T"].rounded-r-full`,
    ),
  ).toHaveCount(1);
});

test("the calendar says what its marks are, and has a way back to where it stands", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(FIXTURE_DAY);
  await target.setViewportSize({ width: 1280, height: 640 });
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  // The key to the marks on the days, by the counts that are the key to
  // the windows: a filled mark for a filing, a hollow one for a message.
  const key = page.locator(".calendar-key");
  await expect(key).toHaveAccessibleName(label("desktop.calendar.observed"));
  await expect(key.getByRole("listitem")).toHaveText([
    label("desktop.calendar.event.filing"),
    label("desktop.calendar.event.message"),
  ]);
  const shape = (item: number) =>
    key
      .getByRole("listitem")
      .nth(item)
      .locator("span")
      .evaluate((mark) => {
        const style = getComputedStyle(mark);
        return {
          filled: style.backgroundColor !== "rgba(0, 0, 0, 0)",
          edge: style.borderTopWidth,
        };
      });
  expect(await shape(0)).toEqual({ filled: true, edge: "0px" });
  expect(await shape(1)).toEqual({ filled: false, edge: "2px" });
  // Each count carries the mark its reading has among the months; what is
  // simply due has none.
  const counts = page.locator(".calendar-standing [data-slot=badge]");
  await expect(counts).toHaveCount(4);
  // Read aloud, the counts say what they are counts of.
  await expect(page.locator(".calendar-standing")).toHaveAccessibleName(
    label("desktop.calendar.standing"),
  );
  expect(
    await counts.evaluateAll((badges) =>
      badges.map((badge) => badge.querySelector("[data-slot=icon]") !== null),
    ),
  ).toEqual([true, false, true, true]);

  // The way back is named in the language's word for today, since the
  // calendar was worked out today.
  const said = new Intl.RelativeTimeFormat("en", { numeric: "auto" }).format(
    0,
    "day",
  );
  const back = page.getByRole("button", {
    name: new RegExp(`^${said}$`, "i"),
  });
  const october = page.locator(
    `.calendar-month[data-month="${fixtureMonth(10)}"] h2`,
  );
  await expect(october).toBeInViewport();
  const opened = await page.evaluate((element) => element.scrollTop);
  await page.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(october).not.toBeInViewport();
  await back.click();
  await expect(october).toBeInViewport();
  expect(await page.evaluate((element) => element.scrollTop)).toBe(opened);
  await expect(back).toBeFocused();
  // In the list it goes to the list's own mark for today, and the key to
  // the months' marks is put away with the months.
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await expect(key).toHaveCount(0);
  const mark = page.getByRole("separator");
  await page.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(mark).not.toBeInViewport();
  await back.click();
  await expect(mark).toBeInViewport();
  // Beside the list it brings both back.
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const aside = page.locator(".calendar-aside");
  await expect(aside).toBeVisible();
  await page.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await aside.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(october).not.toBeInViewport();
  await expect(aside.getByRole("separator")).not.toBeInViewport();
  await back.click();
  await expect(october).toBeInViewport();
  await expect(aside.getByRole("separator")).toBeInViewport();

  // A calendar worked out for another day names the way back by that day.
  await target.clock.setFixedTime(new Date(fixtureYear, 9, 7, 9));
  await open(target, "signed-in");
  await showCalendar(target);
  // The day alone is what is shown; read aloud it says where it goes.
  const toDay = page.getByRole("button", {
    name: label("desktop.calendar.to_day", {
      date: new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(
        FIXTURE_DAY,
      ),
    }),
    exact: true,
  });
  await expect(toDay).toHaveText(
    new Intl.DateTimeFormat("en", { day: "numeric", month: "short" }).format(
      FIXTURE_DAY,
    ),
  );
  await expect(back).toHaveCount(0);
  // The page keeps room for a scrollbar whether or not it has one, so a
  // month drawn whole cannot change the page's width by making it scroll.
  expect(
    await page.evaluate((element) => getComputedStyle(element).scrollbarGutter),
  ).toBe("stable");
});

test("the arrow keys go from one obligation to the next among the months", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const stops = page.locator('.calendar-bar:not([tabindex="-1"])');
  await expect(stops).toHaveCount(9);
  const entry = () =>
    target.evaluate(() =>
      (document.activeElement as HTMLElement).getAttribute("data-entry"),
    );
  const order = await stops.evaluateAll((bars) =>
    bars.map((bar) => bar.getAttribute("data-entry")),
  );
  await stops.first().focus();
  expect(await entry()).toBe(order[0]);
  // Right and down go on, left and up go back, each to an obligation's one
  // stop and never to another week of the same window.
  await target.keyboard.press("ArrowRight");
  expect(await entry()).toBe(order[1]);
  await target.keyboard.press("ArrowDown");
  expect(await entry()).toBe(order[2]);
  await target.keyboard.press("ArrowLeft");
  expect(await entry()).toBe(order[1]);
  await target.keyboard.press("ArrowUp");
  expect(await entry()).toBe(order[0]);
  // End and Home go to the last and the first, and the view goes with the
  // keyboard: the last obligation of the range is far below.
  await target.keyboard.press("End");
  expect(await entry()).toBe(order.at(-1));
  await expect(stops.last()).toBeInViewport();
  await target.keyboard.press("Home");
  expect(await entry()).toBe(order[0]);
  await expect(stops.first()).toBeInViewport();
  // Not covered by the head that stays at the top.
  const head = (await page.locator(".calendar-head").boundingBox())!;
  expect((await stops.first().boundingBox())!.y).toBeGreaterThanOrEqual(
    head.y + head.height,
  );
  // Enter chooses, as on any of them.
  await target.keyboard.press("Enter");
  await expect(stops.first()).toHaveAttribute("aria-pressed", "true");
  // From the page itself the arrows still scroll it.
  await page.focus();
  const before = await page.evaluate((element) => element.scrollTop);
  await target.keyboard.press("ArrowDown");
  await expect
    .poll(() => page.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(before);
});
