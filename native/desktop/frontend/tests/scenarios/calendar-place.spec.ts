import { expect, test, type Locator } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";
import { showCalendar, calendarReads } from "../support/scenarioCalendar";

// The reader's place in the calendar's months and list, kept across layouts, returns and choices.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("the months come back to the month the reader left them on, in a pane and beside the list", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const heading = (month: string) =>
    page.locator(`.calendar-month[data-month="${month}"] h2`);
  await expect(heading("2026-10")).toBeInViewport();
  // The reader scrolls on to January, which begins a row of months in a
  // pane and beside the list alike.
  await page.evaluate((element) => {
    const month = element.querySelector('[data-month="2027-01"]');
    if (!month) throw new Error("no January");
    element.scrollTop +=
      month.getBoundingClientRect().top -
      element.getBoundingClientRect().top -
      100;
  });
  await expect(heading("2027-01")).toBeInViewport();
  await expect(heading("2026-10")).not.toBeInViewport();
  const head = target.locator('[data-dock-header="docs"]');
  // Maximized, the months are laid out anew beside the list: on January.
  await head
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  await expect(heading("2027-01")).toBeInViewport();
  await expect(heading("2026-10")).not.toBeInViewport();
  // And back in a pane, the same.
  await head
    .getByRole("button", { name: label("desktop.dock.restore") })
    .click();
  await expect(page.locator(".calendar-aside")).toHaveCount(0);
  await expect(heading("2027-01")).toBeInViewport();
  await expect(heading("2026-10")).not.toBeInViewport();
  // After the list, too: the list opens on its own mark for today, and
  // the months are where they were left.
  const view = page.getByRole("radiogroup", {
    name: label("desktop.calendar.view"),
  });
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await expect(page.getByRole("separator")).toBeInViewport();
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  await expect(heading("2027-01")).toBeInViewport();
  await expect(heading("2026-10")).not.toBeInViewport();
});

test("the reader's month does not drift however often the months are laid out anew", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const head = target.locator('[data-dock-header="docs"]');
  // How far under the head a month's name sits.
  const under = (month: string) =>
    page.evaluate((element, key) => {
      const kept =
        element.querySelector<HTMLElement>(".calendar-head")?.offsetHeight ||
        element.querySelector<HTMLElement>(".calendar-controls")
          ?.offsetHeight ||
        0;
      return Math.round(
        (element.querySelector(`[data-month="${key}"]`)?.getBoundingClientRect()
          .top ?? 0) -
          element.getBoundingClientRect().top -
          kept,
      );
    }, month);
  // March's row to the top of the view, just under the head, with the row
  // before it gone above: the row at the top is the one that is kept.
  const toMarch = () =>
    page.evaluate((element) => {
      const month = element.querySelector('[data-month="2027-03"]');
      if (!month) throw new Error("no March");
      const kept =
        element.querySelector<HTMLElement>(".calendar-head")?.offsetHeight ||
        element.querySelector<HTMLElement>(".calendar-controls")
          ?.offsetHeight ||
        0;
      element.scrollTop +=
        month.getBoundingClientRect().top -
        element.getBoundingClientRect().top -
        kept -
        12;
    });
  // The reader goes on to March. The place that is kept is the month that
  // begins March's row, which need not be March: the months of a row are
  // made up anew at every width, and that one month is what stays put.
  const march = page.locator('.calendar-month[data-month="2027-03"]');
  await toMarch();
  await expect(march.locator("h2")).toBeInViewport();
  const begins = await page.evaluate((element) => {
    const months = [
      ...element.querySelectorAll<HTMLElement>(".calendar-month"),
    ];
    const top = (month: Element) =>
      Math.round(month.getBoundingClientRect().top);
    const row = top(element.querySelector('[data-month="2027-03"]')!);
    return months.find((month) => top(month) === row)?.dataset.month ?? "";
  });
  expect(begins).not.toBe("");
  const left = { march: await under("2027-03"), begins: await under(begins) };
  // Maximized and restored, three times over. Beside the list the month
  // that began the row is where it was, to the pixel; back in a pane so is
  // March. Nothing walks from one round to the next.
  for (let round = 0; round < 3; round++) {
    await head
      .getByRole("button", { name: label("desktop.dock.expand") })
      .click();
    await expect(page.locator(".calendar-aside")).toBeVisible();
    expect(
      Math.abs((await under(begins)) - left.begins),
      `maximized ${round}`,
    ).toBeLessThanOrEqual(1);
    await head
      .getByRole("button", { name: label("desktop.dock.restore") })
      .click();
    await expect(page.locator(".calendar-aside")).toHaveCount(0);
    expect(
      Math.abs((await under("2027-03")) - left.march),
      `restored ${round}`,
    ).toBeLessThanOrEqual(1);
  }
  // Nor by the window narrowed and widened by a few pixels, and by a lot.
  for (const width of [1598, 1600, 1300, 1000, 1300, 1598, 1600]) {
    await target.setViewportSize({ width, height: 900 });
    await expect
      .poll(async () => Math.abs((await under(begins)) - left.begins), {
        message: `at ${width}`,
      })
      .toBeLessThanOrEqual(1);
  }
  expect(Math.abs((await under("2027-03")) - left.march)).toBeLessThanOrEqual(
    1,
  );

  // A reader at the very start stays at the very start, whatever the head
  // above the months comes to measure at each width. The scroll is the
  // reader's once the page has been told of it, a frame later.
  await page.evaluate(
    (element) =>
      new Promise<void>((done) => {
        element.addEventListener("scroll", () => done(), { once: true });
        element.scrollTop = 0;
      }),
  );
  for (const width of [1300, 900, 700, 1100, 1600]) {
    await target.setViewportSize({ width, height: 900 });
    await expect
      .poll(() => page.evaluate((element) => element.scrollTop), {
        message: `at ${width}`,
      })
      .toBe(0);
  }

  // The place is the reader's even with something chosen elsewhere: a
  // window of October is chosen, and the reader goes on to March.
  await target.setViewportSize({ width: 1600, height: 900 });
  await page.evaluate((element) => {
    element
      .querySelector('.calendar-bar[data-entry="303:2026-3T"]')
      ?.scrollIntoView({ block: "center" });
  });
  await page.locator('.calendar-bar[data-entry="303:2026-3T"]').first().click();
  await toMarch();
  await expect(march.locator("h2")).toBeInViewport();
  const chosenAt = {
    march: await under("2027-03"),
    begins: await under(begins),
  };
  await head
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  expect(Math.abs((await under(begins)) - chosenAt.begins)).toBeLessThanOrEqual(
    1,
  );
  await head
    .getByRole("button", { name: label("desktop.dock.restore") })
    .click();
  await expect(page.locator(".calendar-aside")).toHaveCount(0);
  expect(
    Math.abs((await under("2027-03")) - chosenAt.march),
  ).toBeLessThanOrEqual(1);

  // The list has its place too: left at its start in a pane, it is at its
  // start beside the months, and back.
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await page.evaluate((element) => {
    element.scrollTop = 0;
  });
  await head
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const aside = page.locator(".calendar-aside");
  await expect(aside).toBeVisible();
  expect(await aside.evaluate((element) => element.scrollTop)).toBe(0);
  await head
    .getByRole("button", { name: label("desktop.dock.restore") })
    .click();
  await expect(aside).toHaveCount(0);
  expect(await page.evaluate((element) => element.scrollTop)).toBe(0);
});

test("a choice that moves another obligation's stop takes the keyboard to the new stop", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in", "&calendar=busy");
  await calendarButton(target).click();
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const aside = page.locator(".calendar-aside");
  await expect(aside).toBeVisible();
  const stop = (key: string) =>
    page.locator(`.calendar-bar[data-entry="${key}"]:not([tabindex="-1"])`);
  const weekOf = (bar: Locator) =>
    bar.evaluate((element) =>
      [...(element.parentElement?.parentElement?.children ?? [])].indexOf(
        element.parentElement as Element,
      ),
    );
  // Chosen in the list, a window that January's weeks only counted takes
  // the place of the one they kept last, whose stop moves to a later week.
  const before = await weekOf(stop("130:2026-4T"));
  await aside
    .locator('li[data-entry="303:2026-4T"]')
    .getByRole("button")
    .click();
  await expect(stop("303:2026-4T")).toHaveAttribute("aria-pressed", "true");
  const moved = await weekOf(stop("130:2026-4T"));
  expect(moved).toBeGreaterThan(before);
  // The keyboard goes to that stop and chooses it: its stop is back in the
  // first week, and the keyboard is on it, not on a part that is now only
  // for the eye.
  await stop("130:2026-4T").focus();
  // With the first week of the month scrolled out of view above.
  await page.evaluate((element) => {
    const held = document.activeElement as HTMLElement;
    const head =
      element.querySelector<HTMLElement>(".calendar-head")?.offsetHeight ?? 0;
    element.scrollTop +=
      held.getBoundingClientRect().top -
      element.getBoundingClientRect().top -
      head -
      4;
  });
  await expect(
    page.locator('.calendar-month[data-month="2027-01"] h2'),
  ).not.toBeInViewport();
  await target.keyboard.press("Enter");
  await expect(stop("130:2026-4T")).toHaveAttribute("aria-pressed", "true");
  expect(await weekOf(stop("130:2026-4T"))).toBe(before);
  await expect(stop("130:2026-4T")).toBeFocused();
  // The keyboard is where it can be seen: the view went to the stop.
  await expect(stop("130:2026-4T")).toBeInViewport({ ratio: 1 });
  expect(
    await target.evaluate(() =>
      document.activeElement?.getAttribute("aria-hidden"),
    ),
  ).toBeNull();
  // And the arrow keys go on from there.
  await target.keyboard.press("ArrowRight");
  expect(
    await target.evaluate(() =>
      document.activeElement?.getAttribute("data-entry"),
    ),
  ).not.toBe("130:2026-4T");
  await expect(target.locator(".calendar-bar:focus")).toHaveCount(1);
});

test("a calendar brought back keeps a place the reader scrolled away from their choice to", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1600, height: 700 });
  await open(target, "signed-in");
  await calendarButton(target).click();
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const aside = page.locator(".calendar-aside");
  await expect(aside).toBeVisible();
  // An October window is chosen; the reader then goes to the end of the
  // months, and to the start of the list.
  const chosen = page
    .locator('.calendar-bar[data-entry="303:2026-3T"]')
    .first();
  await chosen.click();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  // Scrolled as far as asked, or to the end, and reported to the page.
  const scrolledTo = (scroller: Locator, top: number | "end") =>
    scroller.evaluate(
      (element, to) =>
        new Promise<number>((done) => {
          element.addEventListener(
            "scroll",
            () => requestAnimationFrame(() => done(element.scrollTop)),
            { once: true },
          );
          element.scrollTop = to === "end" ? element.scrollHeight : to;
        }),
      top,
    );
  const monthsAt = await scrolledTo(page, "end");
  expect(monthsAt).toBeGreaterThan(200);
  await expect(chosen).not.toBeInViewport();
  const listAt = await scrolledTo(aside, 60);
  expect(listAt).toBe(60);
  // Put away and brought back: both faces are where they were left, and
  // the choice is not pulled back into view.
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(page).toHaveCount(0);
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(aside).toBeVisible();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  expect(
    Math.abs((await page.evaluate((element) => element.scrollTop)) - monthsAt),
  ).toBeLessThanOrEqual(1);
  expect(
    Math.abs((await aside.evaluate((element) => element.scrollTop)) - listAt),
  ).toBeLessThanOrEqual(1);
  await expect(chosen).not.toBeInViewport();
});

test("a list brought back in a pane is where it was left, though something is chosen", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1600, height: 700 });
  await open(target, "signed-in");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const chosen = page
    .locator('.calendar-bar[data-entry="303:2026-3T"]')
    .first();
  await chosen.click();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  const list = page.getByRole("radio", {
    name: label("desktop.calendar.view_list"),
  });
  await list.click();
  const row = page.locator('.calendar-list li[data-entry="303:2026-3T"]');
  await expect(row).toHaveAttribute("aria-current", "true");
  // The reader goes to the start of the list, away from what they chose.
  for (const left of [0, 40]) {
    await page.evaluate(
      (element, to) =>
        new Promise<void>((done) => {
          if (element.scrollTop === to) return done();
          element.addEventListener(
            "scroll",
            () => requestAnimationFrame(() => done()),
            { once: true },
          );
          element.scrollTop = to;
        }),
      left,
    );
    await target.keyboard.press("Control+Shift+KeyD");
    await expect(page).toHaveCount(0);
    await target.keyboard.press("Control+Shift+KeyD");
    await expect(list).toBeChecked();
    await expect(row).toHaveAttribute("aria-current", "true");
    expect(
      await page.evaluate((element) => element.scrollTop),
      `left at ${left}`,
    ).toBe(left);
  }
});

test("a month that makes the page scroll when drawn whole does not change the page's width", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  // Tall enough that the months, under the profile notice, fit without
  // scrolling until one is whole.
  await target.setViewportSize({ width: 1600, height: 1600 });
  await open(target, "signed-in", "&calendar=busy");
  await calendarButton(target).click();
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page.locator(".calendar-aside")).toBeVisible();
  const measure = () =>
    page.evaluate((element) => ({
      width: element.clientWidth,
      scrolls: element.scrollHeight > element.clientHeight,
    }));
  const before = await measure();
  expect(before.scrolls).toBe(false);
  const week = page
    .locator('.calendar-month[data-month="2027-01"] > div:last-child > div')
    .nth(4);
  const top = async () => Math.round((await week.boundingBox())!.y);
  const pressedAt = await top();
  await week.locator(".calendar-more").click();
  await expect(
    page.locator('.calendar-month[data-month="2027-01"] .calendar-whole'),
  ).toHaveAttribute("aria-expanded", "true");
  // The page scrolls now, is as wide as it was, and the week that was
  // pressed is where it was pressed.
  const after = await measure();
  expect(after.scrolls).toBe(true);
  expect(after.width).toBe(before.width);
  expect(Math.abs((await top()) - pressedAt)).toBeLessThanOrEqual(1);

  // A page with nothing to scroll keeps no room for a scrollbar: what it
  // says stays in the middle.
  await open(target, "empty");
  await showCalendar(target);
  await expect(page).toContainText(label("desktop.calendar.empty"));
  expect(
    await page.evaluate(
      (element) => (element as HTMLElement).offsetWidth - element.clientWidth,
    ),
  ).toBe(0);
});

test("a reader inside a month taller than the page is kept on that month", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in", "&calendar=busy");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const january = page.locator('.calendar-month[data-month="2027-01"]');
  await january.locator(".calendar-whole").click();
  // Deep inside January: its name is far above the view and the next row
  // of months is still below it.
  const top = () =>
    page.evaluate((element) =>
      Math.round(
        (element
          .querySelector('[data-month="2027-01"]')
          ?.getBoundingClientRect().top ?? 0) -
          element.getBoundingClientRect().top -
          (element.querySelector<HTMLElement>(".calendar-head")?.offsetHeight ||
            element.querySelector<HTMLElement>(".calendar-controls")
              ?.offsetHeight ||
            0),
      ),
    );
  await page.evaluate(
    (element) =>
      new Promise<void>((done) => {
        const month = element.querySelector('[data-month="2027-01"]');
        if (!month) throw new Error("no January");
        element.addEventListener("scroll", () => done(), { once: true });
        element.scrollTop +=
          month.getBoundingClientRect().top -
          element.getBoundingClientRect().top +
          300;
      }),
  );
  const inside = await top();
  expect(inside).toBeLessThan(-300);
  expect((await january.boundingBox())!.height).toBeGreaterThan(
    (await page.boundingBox())!.height,
  );
  // Beside the list, and back, the reader is as deep inside January.
  const head = target.locator('[data-dock-header="docs"]');
  await head
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  expect(Math.abs((await top()) - inside)).toBeLessThanOrEqual(1);
  await head
    .getByRole("button", { name: label("desktop.dock.restore") })
    .click();
  await expect(page.locator(".calendar-aside")).toHaveCount(0);
  expect(Math.abs((await top()) - inside)).toBeLessThanOrEqual(1);
});

test("a calendar put away and brought back is as it was left", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await open(target, "signed-in", "&calendar=busy");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const whole = page.locator(
    '.calendar-month[data-month="2027-01"] .calendar-whole',
  );
  // A month asked for whole, something chosen, and a place left on.
  await whole.click();
  await expect(whole).toHaveAttribute("aria-expanded", "true");
  const chosen = page.locator(
    '.calendar-bar[data-entry="347:2026"]:not([tabindex="-1"])',
  );
  await chosen.scrollIntoViewIfNeeded();
  await chosen.click();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  const where = () =>
    page.evaluate((element) => {
      const month = element.querySelector('[data-month="2027-02"]');
      return Math.round(
        (month?.getBoundingClientRect().top ?? 0) -
          element.getBoundingClientRect().top,
      );
    });
  await page.evaluate((element) => {
    const month = element.querySelector('[data-month="2027-02"]');
    if (!month) throw new Error("no February");
    element.scrollTop +=
      month.getBoundingClientRect().top -
      element.getBoundingClientRect().top -
      160;
  });
  await expect.poll(where).toBeGreaterThan(100);
  const left = await where();
  // Put away with the chord, and brought back with it.
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(page).toHaveCount(0);
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(page).toBeFocused();
  await expect(whole).toHaveAttribute("aria-expanded", "true");
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  expect(Math.abs((await where()) - left)).toBeLessThanOrEqual(1);
  // The face is kept as well.
  await page
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(page).toHaveCount(0);
  await target.keyboard.press("Control+Shift+KeyD");
  await expect(
    page.getByRole("radio", { name: label("desktop.calendar.view_list") }),
  ).toBeChecked();
  await expect(
    page.locator('.calendar-list li[data-entry="347:2026"]'),
  ).toHaveAttribute("aria-current", "true");
  // Nothing was read again for it.
  expect(await calendarReads(target)()).toBe(1);
});
