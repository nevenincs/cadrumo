import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open } from "../support/scenarioShell";
import { openLogs, errorsHeld } from "../support/scenarioLogView";

// The log's fit in small windows and large text, its toolbar, and keyboard focus as records arrive.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("a small window at twice the text size keeps every area inside it", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1024, height: 640 });
  await open(target, "signed-in");
  await showTui(target);
  // The text size a person sets reaches the page as its root font size; the
  // shell reads its floors again when the window reports a resize.
  await target.addStyleTag({ content: "html { font-size: 200% }" });
  await target.evaluate(() => window.dispatchEvent(new Event("resize")));
  await openLogs(target);
  await expect(target.locator(".logview-list .record").last()).toBeVisible();
  const boxes = await target.evaluate(() => {
    const box = (selector: string) =>
      document.querySelector(selector)?.getBoundingClientRect();
    return {
      main: box('[data-dock-pane="tui"]')?.height ?? 0,
      panelBottom: box("section.panel")?.bottom ?? 0,
      list: box(".logview-list")?.height ?? 0,
      newest: box(".logview-list .record:last-child")?.bottom ?? 0,
      window: window.innerHeight,
      scrolled: document.documentElement.scrollTop,
    };
  });
  // Neither floor fits, so the two share the height: both stay on screen,
  // and so does the newest record, which the log is following.
  expect(boxes.panelBottom).toBeLessThanOrEqual(boxes.window);
  expect(boxes.main).toBeGreaterThan(boxes.window / 3);
  expect(boxes.list).toBeGreaterThanOrEqual(40);
  expect(boxes.newest).toBeLessThanOrEqual(boxes.window);
  expect(boxes.scrolled).toBe(0);
});

test("the smallest window keeps the newest record in view", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 520, height: 400 });
  await open(target, "signed-in");
  await openLogs(target);
  await expect(target.locator(".logview-list .record").last()).toBeVisible();
  const boxes = await target.evaluate(() => {
    const box = (selector: string) =>
      document.querySelector(selector)?.getBoundingClientRect();
    return {
      list: box(".logview-list"),
      newest: box(".logview-list .record:last-child")?.bottom ?? 0,
      view: document.querySelector(".logview"),
      window: window.innerHeight,
    };
  });
  // Every control of that one row keeps its own width: none is squeezed
  // under its neighbour.
  const controls = await target
    .locator(".logview .filter-text, .logview select, .logview button")
    .evaluateAll((all) =>
      all
        // Those that are drawn: Follow has a place in each shape of the
        // bar and is shown in one.
        .filter(
          (control) =>
            !control.closest(".logview-list") &&
            control.getClientRects().length > 0,
        )
        .map((control) => {
          const box = control.getBoundingClientRect();
          return {
            left: box.left,
            right: box.right,
            width: box.width,
            top: box.top,
          };
        })
        .sort((a, b) => a.top - b.top || a.left - b.left),
    );
  expect(controls.length).toBeGreaterThan(4);
  for (const [index, control] of controls.entries()) {
    expect(control.width, `control ${index}`).toBeGreaterThanOrEqual(24);
    const next = controls[index + 1];
    if (next && Math.abs(next.top - control.top) < 4)
      expect(control.right, `control ${index}`).toBeLessThanOrEqual(
        next.left + 1,
      );
  }
  // In a panel at its floor the log's bar is one row, so the records keep
  // room; the list is the only thing in the view that scrolls.
  expect(boxes.list?.height ?? 0).toBeGreaterThanOrEqual(40);
  expect(boxes.list?.bottom ?? 0).toBeLessThanOrEqual(boxes.window);
  expect(boxes.newest).toBeLessThanOrEqual(boxes.window);
  expect(boxes.newest).toBeLessThanOrEqual((boxes.list?.bottom ?? 0) + 1);
  expect(
    await target
      .locator(".logview")
      .evaluate((view) => view.scrollHeight - view.clientHeight),
  ).toBeLessThanOrEqual(1);
});

test("a short log toolbar exposes every icon without sideways scrolling", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 520, height: 400 });
  await open(target, "signed-in");
  await openLogs(target);
  const bar = target.locator(".log-toolbar");
  expect(
    await bar.evaluate((element) => element.scrollWidth <= element.clientWidth),
  ).toBe(true);
  for (const button of await bar.getByRole("button").all())
    await expect(button).toBeInViewport({ ratio: 1 });
  await expect(target.locator(".logview-list")).toBeVisible();
});

test("a reader who has left the end keeps their place while records arrive", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=40",
  );
  await openLogs(target);
  const list = target.locator(".logview-list");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect(list.locator(".record")).toHaveCount(400);
  // Wheel up from the end, as a reader does: following stops and the view
  // rests on a record.
  const box = await list.boundingBox();
  if (!box) throw new Error("The log's list is not on screen.");
  await target.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await target.mouse.wheel(0, -600);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const resting = await list.evaluate((element) => {
    const edge = element.getBoundingClientRect().top;
    const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
      (candidate) => candidate.getBoundingClientRect().top >= edge,
    );
    return {
      seq: row?.dataset.seq ?? "",
      top: (row?.getBoundingClientRect().top ?? 0) - edge,
    };
  });
  expect(resting.seq).not.toBe("");
  const newest = async () =>
    Number(await list.locator(".record").last().getAttribute("data-seq"));
  const before = await newest();
  // Well over a span's worth arrives; the record at the top stays there.
  await expect.poll(newest, { timeout: 15000 }).toBeGreaterThan(before + 600);
  const after = await list.evaluate((element, seq) => {
    const edge = element.getBoundingClientRect().top;
    const row = element.querySelector(`[data-seq="${seq}"]`);
    return (row?.getBoundingClientRect().top ?? Number.NaN) - edge;
  }, resting.seq);
  expect(Math.abs(after - resting.top)).toBeLessThanOrEqual(2);
  // Back at the end, following resumes and the span is the newest one again.
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect(list.locator(".record")).toHaveCount(400);
});

test("a focused record that scrolls out of the log hands focus to the log, once", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=1000&feed=30",
  );
  await openLogs(target);
  const list = target.locator(".logview-list");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(list.locator(".record")).toHaveCount(400);
  // The keyboard is on the newest record, and the view stays at the end.
  await list
    .locator(".record")
    .last()
    .evaluate((row) => row.focus({ preventScroll: true }));
  // Following, the newest span moves on and the focused record leaves it:
  // focus goes to the list and stays there, and the log goes on following.
  await expect(list).toBeFocused({ timeout: 15000 });
  // Once: another whole span of records arrives, and focus is where it was.
  const held = await errorsHeld(target)();
  await expect.poll(errorsHeld(target)).toBeGreaterThan(held + 60);
  await expect(list).toBeFocused();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  // An arrow key goes on to the record Tab would reach.
  await target.keyboard.press("ArrowUp");
  await expect(list.locator(".record:focus")).toHaveCount(1);
});

test("Follow keeps the keyboard when the bar changes shape under it", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in");
  await openLogs(target);
  await expect(target.locator(".logview-list .record").first()).toBeVisible();
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await follow.focus();
  // Wide to narrow, narrow to a short panel, and back: each shape shows
  // Follow in another place, and the one shown has the keyboard.
  for (const size of [
    { width: 700, height: 900 },
    { width: 700, height: 420 },
    { width: 1600, height: 900 },
  ]) {
    await target.setViewportSize(size);
    await expect(follow).toHaveCount(1);
    await expect(follow).toBeFocused();
  }
  // A panel grown from the palette changes the bar's shape too.
  await target.setViewportSize({ width: 700, height: 420 });
  await expect(follow).toBeFocused();
  await target.keyboard.press("ControlOrMeta+k");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.pane.maximize_panel"));
  await target.keyboard.press("Enter");
  await expect(target.locator(".palette")).toHaveCount(0);
  await expect(follow).toBeFocused();
});

test("log controls keep a consistent keyboard order as the toolbar wraps", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  for (const size of [
    { width: 1600, height: 900 },
    { width: 700, height: 900 },
    { width: 700, height: 420 },
  ]) {
    await target.setViewportSize(size);
    const controls = target.locator(".log-toolbar").getByRole("button");
    expect(
      await controls.evaluateAll((buttons) =>
        buttons.map((button) => button.getAttribute("aria-label")),
      ),
    ).toEqual([
      label("desktop.logs.filters"),
      label("desktop.menu.select_all"),
      label("desktop.menu.copy"),
      label("desktop.logs.export"),
      label("desktop.logs.reveal"),
      label("desktop.logs.follow"),
    ]);
    await controls.first().focus();
    for (let at = 1; at < (await controls.count()); at++) {
      await target.keyboard.press("Tab");
      await expect(controls.nth(at)).toBeFocused();
      await expect(controls.nth(at)).toBeInViewport({ ratio: 1 });
    }
  }
});

test("a filter control that removes itself hands the keyboard to the filter field", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  const filter = target.locator(".logview .filter-text");
  await expect(target.locator(".logview-list .record").first()).toBeVisible();
  // The reset offered when nothing matches.
  await filter.fill("no such record anywhere");
  const reset = target.locator(".logview-list").getByRole("button", {
    name: label("desktop.action.logs_reset"),
  });
  await reset.focus();
  await target.keyboard.press("Enter");
  await expect(filter).toBeFocused();
  await expect(filter).toHaveValue("");
  // The chip of a logger filter, which names the logger it clears.
  // A record that names its logger: the others have nothing to filter by.
  const row = target.locator(".logview-list .record:has(span[title])").last();
  await row.focus();
  await target.keyboard.press("Shift+F10");
  await target
    .getByRole("menuitem", { name: label("desktop.menu.only_logger") })
    .click();
  const chip = target.locator(".logview").getByRole("button", {
    name: new RegExp(`^${label("desktop.logs.clear_logger")}: .+`),
  });
  await expect(chip).toBeVisible();
  await chip.focus();
  await target.keyboard.press("Enter");
  await expect(chip).toHaveCount(0);
  await expect(filter).toBeFocused();
});

test("opening a detail at the end keeps the newest record in view", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  const list = target.locator(".logview-list");
  const rows = list.locator(".record");
  await expect(rows.last()).toBeVisible();
  await rows
    .filter({ has: target.locator("[aria-expanded]") })
    .last()
    .locator("[aria-expanded]")
    .click();
  await expect(list.locator("pre")).toBeVisible();
  const [listBox, newest] = [
    await list.boundingBox(),
    await rows.last().boundingBox(),
  ];
  if (!listBox || !newest) throw new Error("The log is not on screen.");
  expect(newest.y + newest.height).toBeLessThanOrEqual(
    listBox.y + listBox.height + 1,
  );
});
