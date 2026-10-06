import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The shell on a small touch screen: a phone-sized viewport with a coarse
// pointer and no hover. Controls grow to finger size through the density
// tokens, nothing overflows sideways, and everything that a mouse reaches
// a tap or a touch drag reaches too.
test.use({
  viewport: { width: 390, height: 844 },
  hasTouch: true,
  isMobile: true,
});

// The smallest side a control may have under a finger.
const FINGER = 44;

const open = (target: Page, scenario = "signed-in") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const overflowing = (target: Page) =>
  target.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the pointer is coarse and every control is finger sized", async ({
  page: target,
}) => {
  await open(target);
  expect(
    await target.evaluate(() => matchMedia("(pointer: coarse)").matches),
  ).toBe(true);
  await target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .tap();
  const controls = target.locator(
    ".rail button, .pane-head button, .tabstrip button, .logview button, .logview input, .logview select",
  );
  const count = await controls.count();
  expect(count).toBeGreaterThan(12);
  for (let index = 0; index < count; index++) {
    const control = controls.nth(index);
    if (!(await control.isVisible())) continue;
    const box = await control.boundingBox();
    const name =
      (await control.getAttribute("aria-label")) ??
      (await control.textContent()) ??
      "control";
    expect(box?.height, name).toBeGreaterThanOrEqual(FINGER);
    // A tab is as wide as its name; everything else is at least a finger
    // wide as well.
    if ((await control.getAttribute("role")) !== "tab")
      expect(box?.width, name).toBeGreaterThanOrEqual(FINGER);
  }
});

// In the source language and in the one with the longest words.
for (const language of ["en", "hu"])
  test(`the log keeps room for its records on a small screen (${language})`, async ({
    page: target,
  }) => {
    await target.goto(
      `/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=${language}`,
    );
    // By its tab, which no language renames.
    await target.locator("#tab-logs").tap();
    const list = target.locator(".logview-list");
    // The newest record: the log follows its end.
    await expect(list.locator(".record").last()).toBeVisible();
    const sizes = await target.evaluate(() => {
      const panel = document.querySelector("section.panel");
      const rows = document.querySelector(".logview-list");
      return {
        panel: panel?.getBoundingClientRect().height ?? 0,
        list: rows?.getBoundingClientRect().height ?? 0,
        bottom: rows?.getBoundingClientRect().bottom ?? 0,
        scrolledBy: document.documentElement.scrollTop,
        tall: document.documentElement.scrollHeight > window.innerHeight,
      };
    });
    // The bars never take more than they leave: a few records stay in view,
    // inside the window, and the window itself does not scroll.
    expect(sizes.list, language).toBeGreaterThanOrEqual(60);
    expect(sizes.bottom, language).toBeLessThanOrEqual(844);
    expect(sizes.tall, language).toBe(false);
    expect(sizes.scrolledBy, language).toBe(0);
  });

// In the source language and in the one with the longest words.
for (const language of ["en", "hu"])
  test(`the filing calendar fits a small screen under a finger (${language})`, async ({
    page: target,
  }) => {
    await target.goto(
      `/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=${language}`,
    );
    // By its place in the rail, which no language moves: after search, the
    // documentation and the TUI.
    await target.locator(".rail button").nth(3).tap();
    const page = target.locator(".calendar-page");
    // Each face in turn: the months, where every window is a control, a
    // window of one day among them; then the list.
    const fits = async (face: string) => {
      expect(await overflowing(target), face).toBe(false);
      expect(
        await page.evaluate(
          (element) => element.scrollWidth > element.clientWidth,
        ),
        face,
      ).toBe(false);
      const controls = [
        ...(await page.getByRole("button").all()),
        ...(await page.getByRole("radio").all()),
      ];
      expect(controls.length, face).toBeGreaterThan(2);
      for (const control of controls) {
        const box = await control.boundingBox();
        const name = `${language} ${face}: ${await control.getAttribute("aria-label")}`;
        expect(box?.height, name).toBeGreaterThanOrEqual(FINGER);
        expect(box?.width, name).toBeGreaterThanOrEqual(FINGER);
      }
    };
    await expect(page.locator(".calendar-months")).toBeVisible();
    await expect(
      page.locator('.calendar-bar[data-entry="349:2026-3T"]'),
    ).toHaveCount(1);
    await fits("months");
    // The choice of face stays in reach wherever the page is scrolled to.
    const list = page.getByRole("radio", {
      name: label("desktop.calendar.view_list", {}, language),
    });
    await expect(list).toBeInViewport();
    await list.tap();
    await expect(page.locator(".calendar-list li[data-entry]")).toHaveCount(9);
    await fits("list");
    // Every row keeps its text inside the page.
    const edge = (await page.boundingBox())!;
    for (const row of await page.getByRole("listitem").all()) {
      const box = await row.boundingBox();
      if (!box) continue;
      expect(box.x + box.width, language).toBeLessThanOrEqual(
        edge.x + edge.width + 1,
      );
    }
    // How far off each open obligation is stays on screen at this width:
    // seven of the fixture's nine are not filed.
    await expect(page.locator(".calendar-distance:visible")).toHaveCount(7);
    // A finger scrolls the page: a real drag, sent as touch input.
    const box = (await page.boundingBox())!;
    const client = await target.context().newCDPSession(target);
    const x = box.x + box.width / 2;
    // From well inside the page: a touch that lands on nothing of its own
    // within a fingertip of the line between the panes is given to that
    // line by the browser, and moves it.
    const from = box.y + box.height - 80;
    const before = await page.evaluate((element) => element.scrollTop);
    const touch = (type: "touchStart" | "touchMove" | "touchEnd", y: number) =>
      client.send("Input.dispatchTouchEvent", {
        type,
        touchPoints: type === "touchEnd" ? [] : [{ x, y }],
      });
    await touch("touchStart", from);
    for (let step = 1; step <= 10; step++)
      await touch("touchMove", from - step * 12);
    await touch("touchEnd", from - 120);
    await expect
      .poll(() => page.evaluate((element) => element.scrollTop), {
        message: language,
      })
      .toBeGreaterThan(before + 60);
  });

test("a crowded month's controls fit a finger, and its count opens it", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&calendar=busy",
  );
  await target.locator(".rail button").nth(3).tap();
  const page = target.locator(".calendar-page");
  const january = page.locator('.calendar-month[data-month="2027-01"]');
  const whole = january.locator(".calendar-whole");
  await expect(whole).toBeVisible();
  for (const control of [
    whole,
    january.locator(".calendar-more").first(),
    january.locator(".calendar-bar").first(),
  ]) {
    const box = (await control.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(FINGER);
    expect(box.width).toBeGreaterThanOrEqual(FINGER);
  }
  expect(await overflowing(target)).toBe(false);
  await january.locator(".calendar-more").first().tap();
  await expect(whole).toHaveAttribute("aria-expanded", "true");
  await expect(january.locator(".calendar-more")).toHaveCount(0);
  expect(await overflowing(target)).toBe(false);
});

test("a tap on messages says why there is no count", async ({
  page: target,
}) => {
  // Never synced: under a finger there is no tooltip to say so.
  await open(target, "empty");
  await target
    .locator(`.rail button[aria-label^="${label("desktop.rail.messages")}"]`)
    .tap();
  await expect(target.locator("[data-slot=toast]")).toContainText(
    label("desktop.messages.never"),
  );
});

// Spanish has the longest name for the calendar.
test("a narrow header gives up a duplicate control before it cuts its title", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=es",
  );
  await target.locator(".rail button").nth(3).tap();
  await expect(target.locator(".calendar-page")).toBeVisible();
  const title = target.locator(".pane-docs .pane-title");
  expect(
    await title.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  // What it gave up is the swap, which the TUI's header still has: maximize
  // and close here; maximize, swap and close there.
  await expect(
    target.locator(".pane-docs .pane-head button:visible"),
  ).toHaveCount(2);
  await expect(
    target.locator(".pane-tui .pane-head button:visible"),
  ).toHaveCount(3);
});

test("the shell stacks its panes and never scrolls sideways", async ({
  page: target,
}) => {
  await open(target);
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  expect(await overflowing(target)).toBe(false);
  // The tab row keeps every control inside the panel.
  const panel = await target.locator("section.panel").boundingBox();
  for (const button of await target.locator(".tabstrip button").all()) {
    const box = await button.boundingBox();
    expect(box && panel && box.x + box.width <= panel.x + panel.width + 1).toBe(
      true,
    );
  }
});

test("a tap reaches the rail, the tabs and the log filters", async ({
  page: target,
}) => {
  await open(target);
  await target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .tap();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await follow.tap();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  expect(await overflowing(target)).toBe(false);
});

test("a finger drawn down the log leaves its end, and the bar is one row", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=2000&feed=200",
  );
  await target.locator("#tab-logs").tap();
  const list = target.locator(".logview-list");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(list.locator(".record").last()).toBeVisible();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  // Under a finger, two rows of controls would leave the records two lines:
  // the bar is one row, and the list has most of the panel.
  const sizes = await target.evaluate(() => {
    const bar = document.querySelector(".logview > div");
    const rows = document.querySelector(".logview-list");
    return {
      bar: bar?.getBoundingClientRect().height ?? 0,
      list: rows?.getBoundingClientRect().height ?? 0,
    };
  });
  expect(sizes.bar).toBeLessThan(70);
  expect(sizes.list).toBeGreaterThan(sizes.bar * 2);
  // A real drag, sent as touch input.
  const box = (await list.boundingBox())!;
  const client = await target.context().newCDPSession(target);
  const x = box.x + box.width / 2;
  const from = box.y + 20;
  const touch = (type: "touchStart" | "touchMove" | "touchEnd", y: number) =>
    client.send("Input.dispatchTouchEvent", {
      type,
      touchPoints: type === "touchEnd" ? [] : [{ x, y }],
    });
  await touch("touchStart", from);
  for (let step = 1; step <= 8; step++)
    await touch("touchMove", from + step * 10);
  await touch("touchEnd", from + 80);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // The place holds while records arrive: the same record at the top of
  // the view, where it was, with the end moving away below.
  const place = () =>
    list.evaluate((element) => {
      const edge = element.getBoundingClientRect().top;
      const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
        (candidate) => candidate.getBoundingClientRect().bottom > edge + 1,
      );
      return {
        seq: row?.dataset.seq,
        top: Math.round((row?.getBoundingClientRect().top ?? 0) - edge),
        gap: element.scrollHeight - element.scrollTop - element.clientHeight,
      };
    });
  const before = await place();
  await expect
    .poll(async () => (await place()).gap)
    .toBeGreaterThan(before.gap + 200);
  const after = await place();
  expect(after.seq).toBe(before.seq);
  expect(Math.abs(after.top - before.top)).toBeLessThanOrEqual(2);
  // The way back to the end is on screen, not off the bar's edge.
  const way = (await follow.boundingBox())!;
  expect(way.x).toBeGreaterThanOrEqual(0);
  expect(way.x + way.width).toBeLessThanOrEqual(390);
});

test("a touch drag resizes the panel", async ({ page: target }) => {
  await open(target);
  const handle = target.getByRole("separator", {
    name: label("desktop.panel.resize"),
  });
  const box = await handle.boundingBox();
  if (!box) throw new Error("The panel handle is not on screen.");
  const before = Number(await handle.getAttribute("aria-valuenow"));
  const client = await target.context().newCDPSession(target);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const touch = (type: "touchStart" | "touchMove" | "touchEnd", at: number) =>
    client.send("Input.dispatchTouchEvent", {
      type,
      touchPoints: type === "touchEnd" ? [] : [{ x, y: at }],
    });
  await touch("touchStart", y);
  for (let step = 1; step <= 8; step++) await touch("touchMove", y - step * 15);
  await touch("touchEnd", y - 120);
  await expect
    .poll(async () => Number(await handle.getAttribute("aria-valuenow")))
    .toBeGreaterThan(before);
});

test("the sign-in dialog fits the screen and takes a tapped password", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const dialog = target.locator(".sign-in");
  const box = await dialog.boundingBox();
  expect(box && box.x >= 0 && box.x + box.width <= 390).toBe(true);
  expect(box && box.y >= 0 && box.y + box.height <= 844).toBe(true);
  await target.locator("#profile-password").tap();
  await target.keyboard.type("anything");
  await target
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .tap();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
});

test("the palette and settings fit the screen", async ({ page: target }) => {
  await open(target);
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .tap();
  const palette = await target.locator(".palette").boundingBox();
  expect(palette && palette.x >= 0 && palette.x + palette.width <= 390).toBe(
    true,
  );
  // Its input and its close control are each a fingertip, once the palette
  // has finished scaling in.
  for (const control of ["input", "button"]) {
    const part = target.locator(`.palette ${control}`).first();
    await expect
      .poll(async () => (await part.boundingBox())?.height, control)
      .toBeGreaterThanOrEqual(FINGER);
    expect((await part.boundingBox())?.width, control).toBeGreaterThanOrEqual(
      FINGER,
    );
  }
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .tap();
  const settings = await target.locator(".settings").boundingBox();
  expect(
    settings && settings.x >= 0 && settings.x + settings.width <= 390,
  ).toBe(true);
  expect(
    settings && settings.y >= 0 && settings.y + settings.height <= 844,
  ).toBe(true);
});
