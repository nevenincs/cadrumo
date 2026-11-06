import { expect, test } from "@playwright/test";
import { startFromDocs } from "../support/scenarioShell";
import { openLogs, errorsHeld, overLog } from "../support/scenarioLogView";

// Whether the log follows its newest record: scrolls, keys and the end of a busy log.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("a slow scroll up from the end stops the log following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=2000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // A pixel at a time, as a slow drag of the scrollbar moves it: the
  // movement adds up from the end.
  await list.evaluate(
    (element) =>
      new Promise<void>((done) => {
        let steps = 0;
        const step = () => {
          element.scrollTop -= 1;
          if (++steps < 60) requestAnimationFrame(step);
          else done();
        };
        requestAnimationFrame(step);
      }),
  );
  await expect(follow).toHaveAttribute("aria-pressed", "false");
});

test("the gentlest wheel up leaves the end of a busy log", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=2000&feed=100",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // One notch of the smallest size a wheel sends.
  await target.mouse.wheel(0, -2);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // And the view stays where the wheel left it while records arrive.
  const gap = () =>
    list.evaluate(
      (element) =>
        element.scrollHeight - element.scrollTop - element.clientHeight,
    );
  const before = await gap();
  await expect.poll(gap).toBeGreaterThan(before + 200);
});

test("End returns a reader to the newest record of a busy log", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=40",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  // Repeated: losing this to a batch that lands mid-way was intermittent.
  for (let round = 0; round < 5; round++) {
    await target.mouse.wheel(0, -900);
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await list.locator(".record").nth(5).focus();
    // The newest record drawn before the key: whatever takes focus after it
    // cannot be older than that.
    const newestBefore = await list.evaluate((element) =>
      Number((element.lastElementChild as HTMLElement | null)?.dataset.seq),
    );
    await target.keyboard.press("End");
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    await expect(list.locator(".record")).toHaveCount(400);
    // The record that took focus is at least as new as anything there was
    // before the key, and the view is at the end of the log.
    await expect(list.locator(".record:focus")).toHaveCount(1);
    const landed = await list.evaluate((element) => ({
      seq: Number(
        element.querySelector<HTMLElement>(".record:focus")?.dataset.seq,
      ),
      fromEnd: element.scrollHeight - element.scrollTop - element.clientHeight,
    }));
    expect(landed.seq).toBeGreaterThanOrEqual(newestBefore);
    expect(landed.fromEnd).toBeLessThan(40);
  }
});

test("an arrow up from the newest record stops the log following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=400",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await list.locator(".record").last().focus();
  await target.keyboard.press("ArrowUp");
  await target.keyboard.press("ArrowUp");
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // Records go on arriving, and the record the keyboard is on stays in view.
  const drawnSeq = () =>
    list.evaluate((element) =>
      Number(
        (element.lastElementChild as HTMLElement | null)?.dataset.seq ?? 0,
      ),
    );
  const then = await drawnSeq();
  await expect.poll(drawnSeq).toBeGreaterThan(then + 40);
  expect(
    await list.evaluate((element) => {
      const row = element.querySelector<HTMLElement>(".record:focus");
      const box = element.getBoundingClientRect();
      const at = row?.getBoundingClientRect();
      return !!at && at.bottom > box.top && at.top < box.bottom;
    }),
  ).toBe(true);
});

test("Home is the oldest record of the log, and stays there while records arrive", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=5000&feed=40",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await list.locator(".record").last().focus();
  await target.keyboard.press("Home");
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const oldest = () =>
    list.evaluate((element) => {
      const focused = element.querySelector<HTMLElement>(".record:focus");
      return {
        seq: Number(focused?.dataset.seq ?? Number.NaN),
        first: Number(
          element.querySelector<HTMLElement>(".record")?.dataset.seq,
        ),
        scrollTop: Math.round(element.scrollTop),
      };
    });
  // One press: the first record of the whole log, at the top.
  await expect.poll(async () => (await oldest()).seq).toBe(1);
  expect((await oldest()).first).toBe(1);
  expect((await oldest()).scrollTop).toBe(0);
  // Batches that arrive afterwards do not put the view back: some two
  // hundred more records, by the errors among them.
  const held = await errorsHeld(target)();
  await expect.poll(errorsHeld(target)).toBeGreaterThan(held + 30);
  expect((await oldest()).seq).toBe(1);
  expect((await oldest()).scrollTop).toBe(0);
});

test("an arrow back down to the newest record resumes following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await list.locator(".record").last().focus();
  await target.keyboard.press("ArrowUp");
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await target.keyboard.press("ArrowDown");
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect(list.locator(".record").last()).toBeFocused();
});

test("ArrowDown on the newest record resumes following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  const newest = list.locator(".record").last();
  await newest.focus();
  await target.keyboard.press("ArrowUp");
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // Back on the newest by a press, which resumes nothing by itself.
  await newest.click();
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  await target.keyboard.press("ArrowDown");
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect(newest).toBeFocused();
});

test("a sideways turn of the wheel does not stop the log following", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=2000",
  );
  await openLogs(target);
  const { follow } = await overLog(target);
  for (let turn = 0; turn < 5; turn++) await target.mouse.wheel(60, -1);
  await target.waitForTimeout(200);
  await expect(follow).toHaveAttribute("aria-pressed", "true");
});

test("the notice of dropped records stands at the start of the log only", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=10000&feed=30",
  );
  await openLogs(target);
  const { list } = await overLog(target);
  const notice = list.getByText(/dropped/i);
  // Once the ring has let records go, the newest span says nothing of it:
  // there are thousands of older records still to read above it.
  await expect
    .poll(
      () =>
        list.evaluate(
          (element) =>
            Number(element.querySelector<HTMLElement>(".record")?.dataset.seq) >
            9700,
        ),
      { timeout: 15000 },
    )
    .toBe(true);
  await expect(notice).toHaveCount(0);
  // At the oldest record that is left, it does.
  await list.locator(".record").last().focus();
  await target.keyboard.press("Home");
  await expect(notice).toBeVisible({ timeout: 10000 });
});

test("a reader far from the end is never given the whole log to draw", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=20",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await target.mouse.wheel(0, -900);
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
  // Far more arrives than the span may hold: about twenty-eight hundred
  // records, by the errors among them.
  const held = await errorsHeld(target)();
  await expect
    .poll(errorsHeld(target), { timeout: 20000 })
    .toBeGreaterThan(held + 400);
  // The span is full, and no fuller.
  expect(await list.locator(".record").count()).toBe(2000);
  const after = await list.evaluate((element, seq) => {
    const edge = element.getBoundingClientRect().top;
    const row = element.querySelector(`[data-seq="${seq}"]`);
    return (row?.getBoundingClientRect().top ?? Number.NaN) - edge;
  }, resting.seq);
  expect(Math.abs(after - resting.top)).toBeLessThanOrEqual(2);
  // The Follow button is the way back to the newest record.
  await follow.click();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  await expect(list.locator(".record")).toHaveCount(400);
});
