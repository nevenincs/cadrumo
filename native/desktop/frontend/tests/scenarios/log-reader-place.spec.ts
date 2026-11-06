import { openLogFilters } from "../support/panel";
import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { startFromDocs, open } from "../support/scenarioShell";
import { openLogs, errorsHeld, overLog } from "../support/scenarioLogView";

// The log reader's place across filters, Tab, Page Up and Page Down, and record menus.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

// Where the top of the view is: the record there, and how far from the end.
const logPlace = (target: Page) =>
  target.locator(".logview-list").evaluate((element) => {
    const edge = element.getBoundingClientRect().top;
    const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
      (candidate) => candidate.getBoundingClientRect().bottom > edge + 1,
    );
    return {
      seq: Number(row?.dataset.seq ?? Number.NaN),
      top: Math.round((row?.getBoundingClientRect().top ?? 0) - edge),
      fromEnd: Math.round(
        element.scrollHeight - element.scrollTop - element.clientHeight,
      ),
      scrollTop: Math.round(element.scrollTop),
    };
  });

test("a filter that still shows the reader's record keeps their place", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { follow } = await overLog(target);
  await target.mouse.wheel(0, -3000);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await expect
    .poll(async () => (await logPlace(target)).fromEnd)
    .toBeGreaterThan(2000);
  const before = await logPlace(target);
  // Every level: more records than before, the reader's among them.
  await openLogFilters(target);
  await target
    .getByLabel(label("desktop.logs.minimum_level"))
    .selectOption("0");
  await target.keyboard.press("Escape");
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await expect.poll(async () => (await logPlace(target)).seq).toBe(before.seq);
  expect(
    Math.abs((await logPlace(target)).top - before.top),
  ).toBeLessThanOrEqual(2);
});

test("a filter that hides the reader's record starts the new view at its end, and carries nothing over", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { follow } = await overLog(target);
  await target.mouse.wheel(0, -3000);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const filter = target.locator(".logview .filter-text");
  // Nothing matches: the reader's record is not in this view.
  await filter.fill("no such record anywhere");
  await expect(target.locator(".logview-list .record")).toHaveCount(0);
  await filter.fill("");
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(async () => (await logPlace(target)).fromEnd)
    .toBeLessThan(40);
  // Leaving the end again leaves it from here: the place held in the old
  // view, three thousand pixels up, is not come back to.
  await overLog(target);
  await target.mouse.wheel(0, -40);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await target.waitForTimeout(300);
  expect((await logPlace(target)).fromEnd).toBeLessThan(400);
  // The same by the Follow button, with no scroll at all.
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await target.waitForTimeout(300);
  expect((await logPlace(target)).fromEnd).toBeLessThan(400);
});

test("Tab into a log the reader has scrolled leaves their place alone", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await target.mouse.wheel(0, -3000);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await expect
    .poll(async () => (await logPlace(target)).fromEnd)
    .toBeGreaterThan(2000);
  const before = await logPlace(target);
  // From the bar, Tab by Tab, until focus is in the list.
  await target.locator(".logview .filter-text").focus();
  for (let press = 0; press < 12; press++) {
    await target.keyboard.press("Tab");
    if (
      await list.evaluate(
        (element) =>
          element === document.activeElement ||
          element.contains(document.activeElement),
      )
    )
      break;
  }
  // The list itself takes it: no record is chosen for the reader.
  await expect(list).toBeFocused();
  expect((await logPlace(target)).scrollTop).toBe(before.scrollTop);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // An arrow key goes to the record at the top of the view, which moves
  // nothing either.
  await target.keyboard.press("ArrowDown");
  await expect(list.locator(".record:focus")).toHaveCount(1);
  expect(
    await list.evaluate((element) =>
      Number(element.querySelector<HTMLElement>(".record:focus")?.dataset.seq),
    ),
  ).toBe(before.seq);
  expect(
    Math.abs((await logPlace(target)).scrollTop - before.scrollTop),
  ).toBeLessThanOrEqual(2);
});

test("Page Up and Page Down move the record the keyboard is on", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  const focusedSeq = () =>
    list.evaluate((element) =>
      Number(element.querySelector<HTMLElement>(".record:focus")?.dataset.seq),
    );
  await list.locator(".record").last().focus();
  const newest = await focusedSeq();
  const position = () =>
    list.evaluate((element) => ({
      offset:
        element.querySelector<HTMLElement>(".record:focus")?.offsetTop ?? 0,
      viewport: element.clientHeight,
    }));
  const before = await position();
  for (let press = 0; press < 3; press++) await target.keyboard.press("PageUp");
  // Moving up from the end leaves it.
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const up = await focusedSeq();
  expect(up).toBeLessThan(newest);
  // Paging covers the view even when diagnostic metadata makes rows taller.
  expect(before.offset - (await position()).offset).toBeGreaterThan(
    2 * before.viewport,
  );
  await expect(list.locator(".record:focus")).toHaveAttribute(
    "aria-current",
    "true",
  );
  // The focused record is in view, and the next arrow goes on from it
  // rather than back to where the keyboard used to be.
  const inView = () =>
    list.evaluate((element) => {
      const row = element.querySelector<HTMLElement>(".record:focus");
      const box = element.getBoundingClientRect();
      const at = row?.getBoundingClientRect();
      return !!at && at.bottom > box.top && at.top < box.bottom;
    });
  expect(await inView()).toBe(true);
  await target.keyboard.press("ArrowUp");
  const next = await focusedSeq();
  expect(next).toBeLessThan(up);
  expect(up - next).toBeLessThan(10);
  const downFrom = await position();
  await target.keyboard.press("PageDown");
  expect(await focusedSeq()).toBeGreaterThan(next);
  expect((await position()).offset - downFrom.offset).toBeGreaterThan(
    downFrom.viewport / 2,
  );
  expect(await inView()).toBe(true);
});

test("a filter chosen from a record's menu keeps the reader on that record", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000&feed=200",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await target.mouse.wheel(0, -1500);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // The third record in view, not the one at its top: the record at the
  // top has another logger and will not be in the new view.
  const chosen = await list.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const rows = [...element.querySelectorAll<HTMLElement>(".record")].filter(
      (row) => row.getBoundingClientRect().top >= box.top,
    );
    return Number(rows[2]?.dataset.seq);
  });
  const row = list.locator(`.record[data-seq="${chosen}"]`);
  await row.click({ button: "right" });
  await target
    .getByRole("menuitem", { name: label("desktop.menu.only_logger") })
    .click();
  await expect(
    target.locator(".logview").getByRole("button", {
      name: new RegExp(`^${label("desktop.logs.clear_logger")}: `),
    }),
  ).toBeVisible();
  // Records go on arriving; the reader is still on the record they chose,
  // in view, and the log has not gone back to following.
  const held = await errorsHeld(target)();
  await expect.poll(errorsHeld(target)).toBeGreaterThan(held + 10);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await expect(row).toBeVisible();
  expect(
    await list.evaluate((element, seq) => {
      const at = element
        .querySelector(`.record[data-seq="${seq}"]`)
        ?.getBoundingClientRect();
      const box = element.getBoundingClientRect();
      return !!at && at.top >= box.top - 1 && at.bottom <= box.bottom + 1;
    }, chosen),
  ).toBe(true);
});

test("Tab does not go back to a record the reader has scrolled away from", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // The keyboard was on the newest record; then the reader scrolled far
  // from it and went to the filter.
  await list.locator(".record").last().focus();
  await target.mouse.wheel(0, -3000);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await expect
    .poll(async () => (await logPlace(target)).fromEnd)
    .toBeGreaterThan(2000);
  // Nothing more is scrolled once the keyboard is elsewhere: where the
  // record went was known when it went.
  await target.locator(".logview .filter-text").focus();
  const before = await logPlace(target);
  for (let press = 0; press < 12; press++) {
    await target.keyboard.press("Tab");
    if (
      await list.evaluate(
        (element) =>
          element === document.activeElement ||
          element.contains(document.activeElement),
      )
    )
      break;
  }
  await expect(list).toBeFocused();
  expect((await logPlace(target)).scrollTop).toBe(before.scrollTop);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // Out of the list and back in, the same.
  await target.keyboard.press("Shift+Tab");
  await target.keyboard.press("Tab");
  await expect(list).toBeFocused();
  expect((await logPlace(target)).scrollTop).toBe(before.scrollTop);
});

/**
 * Puts the keyboard on the newest record of a log that is growing, in one
 * step inside the page, and says which record that was. A click sent from
 * here would first scroll to a record the log has since moved past, which
 * is a scroll up and ends following: nothing a person at the end can do.
 */
const focusNewest = (target: Page) =>
  target.locator(".logview-list").evaluate((element) => {
    const newest = element.querySelector<HTMLElement>(
      ":scope > .record:last-of-type",
    );
    if (!newest) throw new Error("the log has no record");
    newest.focus({ preventScroll: true });
    return Number(newest.dataset.seq);
  });

/** Tab from the filter field until focus is in the log's list. */
const tabIntoLog = async (target: Page) => {
  const list = target.locator(".logview-list");
  await target.locator(".logview .filter-text").focus();
  for (let press = 0; press < 12; press++) {
    await target.keyboard.press("Tab");
    if (
      await list.evaluate(
        (element) =>
          element === document.activeElement ||
          element.contains(document.activeElement),
      )
    )
      return;
  }
  throw new Error("Tab never reached the log");
};

test("Tab goes to the newest record once the reader is back at the end, not to one they left", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // A record chosen well above the end; then the keyboard goes elsewhere
  // and the reader scrolls back down to the end.
  await target.mouse.wheel(0, -4000);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const chosen = (await logPlace(target)).seq + 2;
  await list.locator(`.record[data-seq="${chosen}"]`).click();
  await target.locator(".logview .filter-text").focus();
  await list.hover();
  await target.mouse.wheel(0, 20000);
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await tabIntoLog(target);
  await expect(list.locator(".record").last()).toBeFocused();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  expect((await logPlace(target)).fromEnd).toBeLessThan(30);
  // One stop in the list, whatever the state.
  expect(
    await list.evaluate(
      (element) =>
        [element, ...element.querySelectorAll(":scope > .record")].filter(
          (node) => (node as HTMLElement).tabIndex === 0,
        ).length,
    ),
  ).toBe(1);
});

test("Tab does not go back to a record the log has moved on from while following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=200",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // The keyboard was on the newest record, then went to the filter; the
  // log went on following and that record is long out of view.
  const seq = await focusNewest(target);
  await target.locator(".logview .filter-text").focus();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(async () =>
      Number(await list.locator(".record").last().getAttribute("data-seq")),
    )
    .toBeGreaterThan(seq + 60);
  await tabIntoLog(target);
  // On the newest record there now is, still following: not thrown back.
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  expect(
    await target.evaluate(() =>
      Number((document.activeElement as HTMLElement).dataset.seq),
    ),
  ).toBeGreaterThan(seq + 60);
  expect((await logPlace(target)).fromEnd).toBeLessThan(30);
});

test("a filter typed with the current record out of view does not throw the view to that record", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await target.mouse.wheel(0, -600);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // A record chosen in view that names its logger; then the reader scrolls
  // far above it and filters to that logger, which the record at the top of
  // their view does not match.
  const chosen = await list.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
      (candidate) =>
        candidate.getBoundingClientRect().top >= box.top &&
        candidate.querySelector("span[title]"),
    );
    return {
      seq: Number(row?.dataset.seq),
      logger: row?.querySelector("span[title]")?.getAttribute("title") ?? "",
    };
  });
  expect(chosen.logger).not.toBe("");
  await list.locator(`.record[data-seq="${chosen.seq}"]`).click();
  await target.locator(".logview .filter-text").focus();
  await list.hover();
  await target.mouse.wheel(0, -2500);
  await expect
    .poll(async () => (await logPlace(target)).fromEnd)
    .toBeGreaterThan(2500);
  const top = (await logPlace(target)).seq;
  const word = chosen.logger.split(".").at(-1) ?? chosen.logger;
  // The record at the top must not match, or its place would simply hold.
  expect(
    await list
      .locator(`.record[data-seq="${top}"]`)
      .evaluate((row, text) => row.textContent?.includes(text) ?? false, word),
  ).toBe(false);
  await target.locator(".logview .filter-text").fill(word);
  // Neither record is a place to keep: the view starts at its newest again
  // and follows, as any new view does.
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  expect((await logPlace(target)).fromEnd).toBeLessThan(30);
});

test("an arrow from a record the following log has moved past takes the view to where the keyboard goes", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=200",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // The keyboard is on the newest record; the log goes on following and
  // that record is soon far above the view.
  const seq = await focusNewest(target);
  await expect
    .poll(async () =>
      Number(await list.locator(".record").last().getAttribute("data-seq")),
    )
    .toBeGreaterThan(seq + 60);
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  for (const [key, least] of [
    ["ArrowDown", 1],
    ["PageDown", 2],
  ] as const) {
    await target.keyboard.press(key);
    // The record moved to is in view, and the log has stopped following:
    // the view went with the keyboard, not back to the end from under it.
    const at = await list.evaluate((element) => {
      const row = document.activeElement as HTMLElement;
      const box = element.getBoundingClientRect();
      const rect = row.getBoundingClientRect();
      return {
        seq: Number(row.dataset.seq),
        inView: rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1,
      };
    });
    expect(at.seq, key).toBeGreaterThanOrEqual(seq + least);
    expect(at.inView, key).toBe(true);
    await expect(follow).toHaveAttribute("aria-pressed", "false");
  }
  // And it stays there while more records arrive.
  const held = await errorsHeld(target)();
  await expect.poll(errorsHeld(target)).toBeGreaterThan(held + 5);
  expect(
    await list.evaluate((element) => {
      const box = element.getBoundingClientRect();
      const rect = (
        document.activeElement as HTMLElement
      ).getBoundingClientRect();
      return rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1;
    }),
  ).toBe(true);
});

test("under a fast feed, every key from a record the log has passed takes the view with it", async ({
  page: target,
}) => {
  // A batch every thirty milliseconds: one can land between a key and the
  // scroll it causes, which is when the log used to carry on following.
  // Thirty keys, each looked at, under a feed that keeps the page busy.
  test.setTimeout(60_000);
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=30",
  );
  await openLogs(target);
  const { list } = await overLog(target);
  const seq = await focusNewest(target);
  await expect
    .poll(async () =>
      Number(await list.locator(".record").last().getAttribute("data-seq")),
    )
    .toBeGreaterThan(seq + 200);
  for (let press = 0; press < 30; press++) {
    await target.keyboard.press(press % 3 === 2 ? "PageDown" : "ArrowDown");
    const at = await list.evaluate((element) => {
      const row = document.activeElement as HTMLElement;
      const box = element.getBoundingClientRect();
      const rect = row.getBoundingClientRect();
      return {
        newest: row === element.querySelector(":scope > .record:last-of-type"),
        inView: rect.bottom > box.top && rect.top < box.bottom,
        // Read in the same moment as the view, not after another batch.
        following:
          document
            .querySelector("[data-follow]")
            ?.getAttribute("aria-pressed") === "true",
      };
    });
    // On the newest record the log follows again, as it should.
    if (at.newest) break;
    expect(at.inView, `press ${press}`).toBe(true);
    expect(at.following, `press ${press}`).toBe(false);
  }
});

test("Space on a record with no detail does not scroll the log", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1440, height: 600 });
  await open(target, "signed-in", "&bar=off");
  await openLogs(target);
  const { list, follow } = await overLog(target, 14);
  await target.mouse.wheel(0, -1500);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // The unnamed-source fixture has neither continuation text nor context.
  // Generated measurement records all carry diagnostic metadata.
  const plain = list.locator('.record[data-seq="8"]');
  await expect(plain.locator("[aria-expanded]")).toHaveCount(0);
  await plain.focus();
  const before = (await logPlace(target)).scrollTop;
  // The key is taken from the browser, whose own answer to it is to scroll.
  await target.evaluate(() => {
    document.addEventListener(
      "keydown",
      (event) => {
        (window as unknown as { spaceTaken?: boolean }).spaceTaken =
          event.defaultPrevented;
      },
      { once: true },
    );
  });
  await target.keyboard.press("Space");
  expect(
    await target.evaluate(
      () => (window as unknown as { spaceTaken?: boolean }).spaceTaken,
    ),
  ).toBe(true);
  expect((await logPlace(target)).scrollTop).toBe(before);
});
