import { expect, test, type Locator } from "@playwright/test";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";
import { calendarReads } from "../support/scenarioCalendar";

// The filing calendar's look: pill colours, head height, forced system colours and crowded months.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("a short page keeps only the calendar's controls in view, a tall one its whole head", async ({
  page: target,
}) => {
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  // Nothing the page does while it is resized is reported as an error:
  // not a loop of its own observations either.
  const errors: string[] = [];
  target.on("pageerror", (error) => errors.push(error.message));
  await target.addInitScript(() => {
    window.addEventListener("error", (event) => {
      (window as unknown as { __errors?: string[] }).__errors ??= [];
      (window as unknown as { __errors: string[] }).__errors.push(
        event.message,
      );
    });
  });
  // Tall: the counts, which are the key to the months' colours, and the
  // sentence about where the page comes from stay with the controls.
  await target.setViewportSize({ width: 1280, height: 1000 });
  await open(target, "signed-in");
  await calendarButton(target).click();
  await expect(page).toHaveAttribute("data-head", "whole");
  await page.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(page.locator(".calendar-standing")).toBeInViewport();
  await expect(page.locator(".calendar-controls")).toBeInViewport();
  // Short: the head would take half of what there is. Only the controls
  // stay, and the rest of the head scrolls with the page.
  await target.setViewportSize({ width: 1280, height: 500 });
  await expect(page).toHaveAttribute("data-head", "controls");
  await page.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(page.locator(".calendar-controls")).toBeInViewport();
  await expect(page.locator(".calendar-standing")).not.toBeInViewport();
  const sizes = await page.evaluate((element) => ({
    page: element.clientHeight,
    kept: element.querySelector<HTMLElement>(".calendar-controls")
      ?.offsetHeight,
  }));
  expect(sizes.kept ?? 0).toBeLessThan(sizes.page / 3);
  // And tall again, wide enough for both faces, and back to a pane's width.
  for (const size of [
    { width: 1280, height: 1000 },
    { width: 2000, height: 1000 },
    { width: 2000, height: 420 },
    { width: 1280, height: 420 },
    { width: 1280, height: 1000 },
  ]) {
    await target.setViewportSize(size);
    await expect(page).toHaveAttribute(
      "data-head",
      size.height >= 700 ? "whole" : "controls",
    );
  }
  expect(errors).toEqual([]);
  expect(
    await target.evaluate(
      () => (window as unknown as { __errors?: string[] }).__errors ?? [],
    ),
  ).toEqual([]);
});

for (const scheme of ["light", "dark"] as const)
  test(`calendar pills are opaque, borderless and have readable text (${scheme})`, async ({
    page: target,
  }) => {
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
    await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
    await open(target, "signed-in", "&calendar=busy");
    await calendarButton(target).click();
    const page = target.getByRole("region", {
      name: label("desktop.calendar.title"),
    });
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    // Every reading is drawn somewhere once the crowded months are whole.
    await expect(page.locator(".calendar-whole").first()).toBeVisible();
    for (const whole of await page.locator(".calendar-whole").all())
      await whole.click();
    const ratios = await page.evaluate((element) => {
      const canvas = document.createElement("canvas").getContext("2d")!;
      const rgba = (colour: string) => {
        canvas.clearRect(0, 0, 1, 1);
        canvas.fillStyle = colour;
        canvas.fillRect(0, 0, 1, 1);
        const [r = 0, g = 0, b = 0, a = 0] = canvas.getImageData(
          0,
          0,
          1,
          1,
        ).data;
        return [r, g, b, a / 255] as const;
      };
      type Colour = readonly [number, number, number, number];
      const over = (top: Colour, under: readonly number[]) =>
        [0, 1, 2].map(
          (channel) =>
            (top[channel] ?? 0) * top[3] + (under[channel] ?? 0) * (1 - top[3]),
        );
      const luminance = (colour: readonly number[]) => {
        const [r = 0, g = 0, b = 0] = colour.map((value) => {
          const part = value / 255;
          return part <= 0.03928
            ? part / 12.92
            : ((part + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      const ratio = (a: readonly number[], b: readonly number[]) => {
        const [high = 0, low = 0] = [luminance(a), luminance(b)].sort(
          (x, y) => y - x,
        );
        return (high + 0.05) / (low + 0.05);
      };
      const card = over(
        rgba(
          getComputedStyle(
            element.querySelector(".calendar-month > div:last-child")!,
          ).backgroundColor,
        ),
        [255, 255, 255],
      );
      return ["late", "due", "unknown", "filed"].map((state) => {
        const bar = element.querySelector(
          `.calendar-bar[data-state="${state}"]`,
        );
        if (!bar) throw new Error(`Missing calendar state: ${state}`);
        const style = getComputedStyle(bar);
        const fill = rgba(style.backgroundColor);
        return {
          state,
          alpha: fill[3],
          border: style.borderTopWidth,
          contrast: ratio(rgba(style.color), over(fill, card)),
        };
      });
    });
    for (const { state, alpha, border, contrast } of ratios) {
      expect(alpha, `${state} fill`).toBe(1);
      expect(border, `${state} border`).toBe("0px");
      expect(contrast, `${state} text`).toBeGreaterThanOrEqual(4.5);
    }
  });

test("with the system's colours forced, the calendar still shows its day, its states and what is chosen", async ({
  page: target,
}) => {
  await target.emulateMedia({ forcedColors: "active" });
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await open(target, "signed-in", "&calendar=busy");
  await calendarButton(target).click();
  await target
    .locator('[data-dock-header="docs"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const style = (locator: Locator, property: string) =>
    locator.evaluate(
      (element, name) => getComputedStyle(element).getPropertyValue(name),
      property,
    );
  const canvas = await style(
    page.locator(".calendar-month > div").last(),
    "background-color",
  );
  // The evaluated day is filled with the system's highlight, not left as a
  // number among numbers.
  expect(
    await style(page.locator(".calendar-grid-today"), "background-color"),
  ).not.toBe(canvas);
  // A filing is a filled mark and a message a hollow one.
  const filing = page.locator('.calendar-event[data-event="filing"]').first();
  const message = page.locator('.calendar-event[data-event="message"]').first();
  expect(await style(filing, "background-color")).not.toBe(canvas);
  expect(await style(message, "border-top-width")).toBe("2px");
  expect(await style(message, "background-color")).not.toBe(
    await style(filing, "background-color"),
  );
  // State icons remain visible when forced colours remove the hues.
  const late = page.locator('.calendar-bar[data-state="late"]').first();
  const unknown = page.locator('.calendar-bar[data-state="unknown"]').first();
  const due = page.locator('.calendar-bar[data-state="due"]').first();
  expect(await style(late, "border-top-width")).toBe("0px");
  expect(await style(late, "background-color")).not.toBe(canvas);
  expect(await style(due, "border-top-width")).toBe("0px");
  await expect(late.locator("[data-slot=icon]")).toBeVisible();
  await expect(due.locator("[data-slot=icon]")).toHaveCount(0);
  // Filed windows are found by expanding the crowded month.
  await page
    .locator('.calendar-month[data-month="2027-01"] .calendar-whole')
    .click();
  const filed = page.locator('.calendar-bar[data-state="filed"]').first();
  await expect(filed.locator("[data-slot=icon]")).toBeVisible();
  expect(await style(filed, "border-top-width")).toBe("0px");
  expect(await style(filed, "background-color")).not.toBe(canvas);
  // The unknown window of the fixture is one day wide and is found whole.
  await page
    .locator('.calendar-month[data-month="2027-02"] .calendar-whole')
    .click();
  expect(await style(unknown, "border-top-width")).toBe("0px");
  await expect(unknown.locator("[data-slot=icon]")).toBeVisible();
  // What is chosen is outlined among the months, and in the list it alone
  // has an edge that is not the page's own colour.
  await late.click();
  expect(await style(late, "outline-style")).toBe("solid");
  expect(await style(late, "outline-width")).toBe("2px");
  expect(await style(due, "outline-style")).toBe("none");
  const rows = page.locator(".calendar-list li[data-entry]");
  const chosen = page.locator('.calendar-list li[aria-current="true"]');
  await expect(chosen).toHaveCount(1);
  const edge = await style(chosen, "border-left-color");
  const plain = await style(
    rows.filter({ hasNot: target.locator(":scope[aria-current]") }).first(),
    "border-left-color",
  );
  expect(edge).not.toBe(plain);
  expect(plain).toBe(await style(page, "background-color"));
});

test("a crowded month shows each week's nearest deadlines and counts the rest, and can be drawn whole", async ({
  page: target,
}) => {
  // The day the crowded fixture was evaluated on.
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await open(target, "signed-in", "&calendar=busy");
  // With the TUI beside it, the calendar has a pane's width.
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const january = page.locator('.calendar-month[data-month="2027-01"]');
  const title = new Intl.DateTimeFormat("en", {
    month: "long",
    year: "numeric",
  }).format(new Date(2027, 0, 1));
  const all = `${label("desktop.calendar.show_all")}: ${title}`;
  const fewer = `${label("desktop.calendar.show_fewer")}: ${title}`;
  const whole = january.locator(".calendar-whole");
  await expect(whole).toHaveAccessibleName(all);
  await expect(whole).toHaveAttribute("aria-expanded", "false");
  // The range asked for ends in April; the Renta window open in it closes
  // at the end of June, and the months run on to that closing day.
  await expect(page.locator(".calendar-month")).toHaveCount(8);
  await expect(
    page.locator(
      '.calendar-month[data-month="2027-06"] .calendar-bar[data-entry="100:2026"]',
    ),
  ).not.toHaveCount(0);
  // A month with room for all its windows has nothing to ask.
  await expect(
    page.locator('.calendar-month[data-month="2026-12"] .calendar-whole'),
  ).toHaveCount(0);

  // Eight windows cross the week of the third. Three are drawn: the two
  // still due on the twentieth, and the first of those due later. The one
  // already filed is counted with the rest, though it closes as soon as
  // any: the fourth row counts five. No week is more than four rows.
  const week = january.locator(":scope > div:last-child > div").nth(2);
  await expect(week.locator(".calendar-bar")).toHaveCount(3);
  await expect(week.locator(".calendar-bar")).toHaveText([
    /^111/,
    /^123/,
    /^130/,
  ]);
  await expect(week.locator('[data-state="filed"]')).toHaveCount(0);
  await expect(week.locator(".calendar-more")).toHaveText(
    label("desktop.calendar.more", { count: 5 }),
  );
  const rows = (month: Locator) =>
    month.evaluate((element) =>
      Math.max(
        ...[
          ...element.querySelectorAll<HTMLElement>(
            ".calendar-bar, .calendar-more",
          ),
        ].map((bar) => Number(bar.style.gridRowStart) - 1),
      ),
    );
  expect(await rows(january)).toBe(4);
  // What is only counted is not drawn, and is not a stop for the keyboard;
  // the count is for the eye and the pointer, and says which they are.
  await expect(january.locator('[data-entry="303:2026-4T"]')).toHaveCount(0);
  await expect(week.locator(".calendar-more")).toHaveAttribute(
    "aria-hidden",
    "true",
  );
  await expect(week.locator(".calendar-more")).toHaveAttribute(
    "title",
    /303 2026-4T/,
  );
  const collapsed = (await january.boundingBox())!.height;

  // By the keyboard: the month's own control draws it whole, stays where
  // it is, and keeps the keyboard.
  await whole.focus();
  await target.keyboard.press("Enter");
  await expect(whole).toHaveAttribute("aria-expanded", "true");
  await expect(whole).toHaveAccessibleName(fewer);
  await expect(whole).toBeFocused();
  await expect(january.locator(".calendar-more")).toHaveCount(0);
  await expect(week.locator(".calendar-bar")).toHaveCount(8);
  expect(await rows(january)).toBe(8);
  expect((await january.boundingBox())!.height).toBeGreaterThan(
    collapsed * 1.3,
  );
  // Each obligation is still one stop: its first week in the month.
  const stops = january.locator(
    '.calendar-bar[data-entry="303:2026-4T"]:not([tabindex="-1"])',
  );
  await expect(stops).toHaveCount(1);
  await expect(stops).toHaveAccessibleName(/303.* 2026-4T/);
  // And back.
  await target.keyboard.press("Enter");
  await expect(whole).toHaveAttribute("aria-expanded", "false");
  await expect(whole).toBeFocused();
  expect((await january.boundingBox())!.height).toBe(collapsed);

  // By the pointer, the count itself opens its month, and the keyboard is
  // left on the control that undoes it, not on nothing.
  // The month grows above the week that was pressed, and that week stays
  // where it was pressed: a later week, with crowded ones above it.
  const later = january.locator(":scope > div:last-child > div").nth(4);
  await later.locator(".calendar-more").scrollIntoViewIfNeeded();
  const top = async () => Math.round((await later.boundingBox())!.y);
  const pressedAt = await top();
  await later.locator(".calendar-more").click();
  await expect(whole).toHaveAttribute("aria-expanded", "true");
  await expect(whole).toBeFocused();
  expect(Math.abs((await top()) - pressedAt)).toBeLessThanOrEqual(1);
  await expect(later).toBeInViewport();
  await whole.click();
  await expect(whole).toHaveAttribute("aria-expanded", "false");

  // What is chosen is never among what is only counted: chosen in the
  // list, an obligation left out of its weeks is drawn in each of them, in
  // place of what the week would keep last. The month is no taller for it.
  const view = page.getByRole("radiogroup", {
    name: label("desktop.calendar.view"),
  });
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await page
    .locator('.calendar-list li[data-entry="390:2026"]')
    .getByRole("button")
    .click();
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  const chosen = page.locator('.calendar-bar[data-entry="390:2026"]').first();
  await expect(chosen).toHaveAttribute("aria-pressed", "true");
  await expect(chosen).toBeInViewport();
  await expect(whole).toHaveAttribute("aria-expanded", "false");
  expect(await rows(january)).toBe(4);
  expect((await january.boundingBox())!.height).toBe(collapsed);
  await expect(week.locator(".calendar-bar")).toHaveText([
    /^111/,
    /^123/,
    /^390/,
  ]);
  // Choosing one that is drawn does not redraw the month under the hand:
  // the window pressed stays under the pointer, and stays the stop.
  const drawnOne = january.locator(
    '.calendar-bar[data-entry="123:2026-4T"]:not([tabindex="-1"])',
  );
  await drawnOne.scrollIntoViewIfNeeded();
  await drawnOne.hover();
  const at = (await drawnOne.boundingBox())!;
  await drawnOne.click();
  await expect(drawnOne).toHaveAttribute("aria-pressed", "true");
  await expect(drawnOne).toBeFocused();
  expect((await drawnOne.boundingBox())!.y).toBe(at.y);
  // The one chosen before is counted again, now that it is not chosen.
  await expect(january.locator('[data-entry="390:2026"]')).toHaveCount(0);
  // Let go with the keyboard on it, a window drawn only for being chosen
  // stays until the keyboard leaves it, and then is counted again.
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  await page
    .locator('.calendar-list li[data-entry="390:2026"]')
    .getByRole("button")
    .click();
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_months") })
    .click();
  await chosen.focus();
  await target.keyboard.press("Enter");
  await expect(page.locator("[data-selected]")).toHaveCount(0);
  await expect(chosen).toBeFocused();
  await target.keyboard.press("Tab");
  await expect(january.locator('[data-entry="390:2026"]')).toHaveCount(0);
  await expect(
    target.locator(":focus"),
    "the keyboard has gone on to something, not to nothing",
  ).toHaveCount(1);
  expect(await calendarReads(target)()).toBe(1);
});
