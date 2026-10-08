import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The development entry on the development server: the production shell on
// the scenario host, with the documentation fixture on another origin. These
// tests prove the scenarios present what they are named for. They are
// presentation evidence only; no host, runtime or sign-in is behind them.

const open = (target: Page, scenario: string, extra = "") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0${extra}`);

const password = (target: Page) =>
  target.getByLabel(label("desktop.signin.password"), { exact: true });

const submit = (target: Page) =>
  target.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });

/** How many times the shell has made this host call in the current run. */
const calls = (target: Page, call: string) => () =>
  target.evaluate(
    (name) =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter((made) => made === name).length ?? 0,
    call,
  );

const openLogs = (target: Page) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    // Exercise the full panel layout as a returning user's saved choice.
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({ layout: { panelOpen: true } }),
    );
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the page names itself as simulated", async ({ page: target }) => {
  await open(target, "signed-out");
  await expect(target.locator(".scenario-bar")).toContainText("Simulated host");
  await expect(target.locator(".scenario-bar")).toContainText("Signed out");
});

test("signed out: one submission signs in and starts the TUI fixture", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(password(target)).toBeVisible();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
  await password(target).fill("anything");
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
    "Simulated TUI session",
  );
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("signing in: the pending state stays up", async ({ page: target }) => {
  await open(target, "signing-in");
  await password(target).fill("anything");
  await submit(target).click();
  // Nothing is disabled while the answer is awaited, so focus stays put.
  await expect(password(target)).toHaveAttribute("readonly", "");
  await expect(
    target.getByRole("button", { name: label("desktop.signin.submitting") }),
  ).toHaveAttribute("aria-busy", "true");
  await target.keyboard.press("Tab");
  await expect(target.locator(".sign-in").locator(":focus")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("signed in: the TUI runs and the account can sign out", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
    "Simulated TUI session",
  );
  await expect(password(target)).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(
    target.getByText(label("desktop.signin.signed_out_lead")),
  ).toBeVisible();
  await expect(password(target)).toHaveCount(0);
  await target.keyboard.press("Escape");
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(password(target)).toBeFocused();
});

test("wrong password: the refusal shows and nothing is retried", async ({
  page: target,
}) => {
  await open(target, "wrong-password");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(
    target.getByText(label("desktop.signin.refused.invalid")),
  ).toBeVisible();
  await expect(password(target)).toHaveValue("");
  // The status read that follows a refusal has settled and the field is
  // usable again: nothing else was sent.
  await expect(password(target)).toBeEnabled();
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("throttled: the wait is shown and submission is held", async ({
  page: target,
}) => {
  await open(target, "throttled");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(submit(target)).toBeDisabled();
  // The wait counts down from the host's thirty seconds.
  const shown = async () =>
    Number(
      /\b(\d+)\b/.exec(
        (await target.locator(".sign-in").textContent()) ?? "",
      )?.[1],
    );
  await expect.poll(shown).toBeGreaterThan(0);
  await expect.poll(shown).toBeLessThanOrEqual(30);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("profile locked: the refusal shows and the TUI handover is offered", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await dialog
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
    "Simulated TUI session",
  );
});

test("runtime unavailable: said plainly, with submission disabled", async ({
  page: target,
}) => {
  await open(target, "runtime-unavailable");
  await expect(target.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(password(target)).toHaveCount(0);
  await expect(submit(target)).toHaveCount(0);
});

test("unsupported: no sign-in view, and the TUI starts", async ({
  page: target,
}) => {
  await open(target, "unsupported");
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(password(target)).toHaveCount(0);
});

test("loading: nothing is invented while the host has not answered", async ({
  page: target,
}) => {
  await open(target, "loading");
  // The pane and its header say the same thing: the check is in flight.
  const pane = target.locator(".pane-tui");
  await expect(pane.locator("[data-slot=empty]")).toHaveText(
    label("desktop.signin.checking"),
  );
  await expect(pane.locator(".pane-head")).toContainText(
    label("desktop.signin.checking"),
  );
  await expect(target.locator(".docs-frame")).toHaveCount(0);
  await openLogs(target);
  await expect(target.locator(".record")).toHaveCount(0);
  await expect(target.locator(".source-banner")).toHaveCount(0);
});

test("empty: an available log with no records says so", async ({
  page: target,
}) => {
  await open(target, "empty");
  await openLogs(target);
  await expect(target.locator(".logview-list")).toContainText(
    label("desktop.logs.empty"),
  );
  await expect(target.locator(".record")).toHaveCount(0);
});

test("error: refusals are shown, not swallowed", async ({ page: target }) => {
  await open(target, "error");
  // A read the host failed is said to have failed, not to need the desktop.
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.failed"),
  );
  // The failed status read is said in the sign-in dialog, with its code.
  await expect(target.locator(".sign-in")).toContainText("timed_out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await openLogs(target);
  await expect(target.locator(".source-banner.state-unreadable")).toBeVisible();
});

test("a missing log file is not an empty log", async ({ page: target }) => {
  await open(target, "logs-missing");
  await openLogs(target);
  await expect(
    target.locator('.source-banner.state-missing[data-source="python"]'),
  ).toHaveText(
    `${label("desktop.logs.source_python")}: ${label("desktop.logs.state_missing_detail")}`,
  );
  await expect(
    target.locator('.source-banner[data-source="manager"]'),
  ).toHaveCount(0);
  await expect(target.locator(".logview-list")).not.toContainText(
    label("desktop.logs.empty"),
  );
});

test("fixture records list every level, an unnamed source and a dropped count", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  await target
    .getByLabel(label("desktop.logs.minimum_level"))
    .selectOption({ label: label("desktop.logs.level_all") });
  for (const level of ["debug", "info", "warning", "error", "critical", "none"])
    await expect(
      target.locator(`.record.level-${level}`).first(),
      level,
    ).toBeVisible();
  await expect(target.locator(".record.source-manager")).toHaveCount(1);
  await expect(target.locator(".logview-list")).toContainText(
    label("desktop.logs.dropped", { count: 3 }),
  );
});

test("sign-out refused: the sign-in stays and the failure shows", async ({
  page: target,
}) => {
  await open(target, "sign-out-refused");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect.poll(calls(target, "signOut")).toBe(1);
  const account = target.getByRole("region", {
    name: label("desktop.settings.session"),
  });
  await expect(account).toContainText("timed_out");
  await expect(
    account.getByText(label("desktop.account.signed_in"), { exact: true }),
  ).toBeVisible();
});

test("session failure: the failure is written into the terminal and the tab says exited", async ({
  page: target,
}) => {
  await open(target, "session-failure");
  await expect(
    target.locator('[data-terminal="console"] .xterm-rows'),
  ).toContainText(label("desktop.session.failed", { reason: "read_failed" }));
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.console") }),
  ).toContainText(label("desktop.session.exited", { code: 1 }));
});

test("the documentation fixture is another origin and answers the bridge", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const frame = target.frameLocator(".docs-frame");
  await expect(frame.locator("h1")).toHaveText("Stand-in documentation");
  const docsUrl = new URL(
    (await target.locator(".docs-frame").getAttribute("src")) ?? "",
  );
  expect(docsUrl.origin).not.toBe(new URL(target.url()).origin);
  // The real bridge script answers a search through the page's controller.
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await palette.getByRole("combobox").fill("sign-in");
  const result = palette.getByRole("option", { name: /config sign-in-status/ });
  await expect(result).toBeVisible();
  await result.click();
  await expect(palette).toBeHidden();
  await expect(frame.locator("h1")).toHaveText("Second page");
});

test("the output language reaches the chrome and the documentation", async ({
  page: target,
}) => {
  await open(target, "signed-in", "&lang=es");
  await expect(target.locator("html")).toHaveAttribute("lang", "es");
  await expect(
    target.getByRole("navigation", {
      name: label("desktop.rail.label", {}, "es"),
    }),
  ).toBeVisible();
  await expect(
    target.frameLocator(".docs-frame").locator("html"),
  ).toHaveAttribute("lang", "es");
});

test("a console fixture session takes input and restarts after exit", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const rows = target.locator('[data-terminal="console"] .xterm-rows');
  await expect(rows).toContainText("PS C:\\Users\\demo>");
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  await target.keyboard.type("exit");
  await target.keyboard.press("Enter");
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.console") }),
  ).toContainText(label("desktop.session.exited", { code: 0 }));
  await target.keyboard.press("Enter");
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.console") }),
  ).not.toContainText(label("desktop.session.exited", { code: 0 }));
});

test("the palette's first section is the documentation's while a query searches it", async ({
  page: target,
}) => {
  // The packaged acceptance run reads documentation results from the first
  // section; an action that matches the same query must never stand there.
  await open(target, "empty");
  await target.keyboard.press("Control+KeyK");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.rail.logs"));
  const sections = palette.locator(".palette-results > section");
  await expect(sections).toHaveCount(2);
  await expect(sections.first().getByRole("option")).toHaveCount(0);
  await expect(sections.last().getByRole("option").first()).toContainText(
    label("desktop.rail.logs"),
  );
});

test("a small window at twice the text size keeps every area inside it", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1024, height: 640 });
  await open(target, "signed-in");
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
      main: box(".main-area")?.height ?? 0,
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
          return { left: box.left, right: box.right, width: box.width };
        })
        .sort((a, b) => a.left - b.left),
    );
  expect(controls.length).toBeGreaterThan(4);
  for (const [index, control] of controls.entries()) {
    expect(control.width, `control ${index}`).toBeGreaterThan(40);
    const next = controls[index + 1];
    if (next)
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

test("a bar that scrolls sideways shows that it goes on", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 520, height: 400 });
  await open(target, "signed-in");
  await openLogs(target);
  const bar = target.locator(".logview > div").first();
  const state = () =>
    bar.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        more: element.scrollWidth > element.clientWidth,
        start: parseFloat(style.getPropertyValue("--scroll-cue-start")),
        end: parseFloat(style.getPropertyValue("--scroll-cue-end")),
      };
    });
  // At its start there is more to the right only, and only that edge fades.
  expect(await state()).toMatchObject({ more: true, start: 0 });
  expect((await state()).end).toBeGreaterThan(0);
  // Part way along, both edges do.
  await bar.evaluate((element) => {
    element.scrollLeft = element.scrollWidth / 3;
  });
  await expect.poll(async () => (await state()).start).toBeGreaterThan(0);
  expect((await state()).end).toBeGreaterThan(0);
  // At its end, only the left.
  await bar.evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  await expect.poll(async () => (await state()).end).toBe(0);
  expect((await state()).start).toBeGreaterThan(0);
  // A bar with nothing beyond it fades nowhere.
  await target.setViewportSize({ width: 1440, height: 900 });
  await expect
    .poll(async () => {
      const wide = await target
        .locator(".logview > div")
        .first()
        .evaluate((element) => {
          const style = getComputedStyle(element);
          return (
            parseFloat(style.getPropertyValue("--scroll-cue-start") || "0") +
            parseFloat(style.getPropertyValue("--scroll-cue-end") || "0")
          );
        });
      return wide;
    })
    .toBe(0);
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

/** How many error records the log holds, as its bar counts them: a number
 * that grows as records arrive, whatever span is drawn. One generated record
 * in seven is an error. It stops growing once the ring is full. */
const errorsHeld = (target: Page) => async () =>
  Number(
    /\d+/.exec(
      (await target
        .locator(".logview [data-slot=badge][data-variant=danger]")
        .first()
        .textContent()) ?? "",
    )?.[0] ?? 0,
  );

// The log's Follow toggle and its list, with the pointer over the list.
async function overLog(target: Page) {
  const list = target.locator(".logview-list");
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await expect(list.locator(".record")).toHaveCount(400);
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  const box = await list.boundingBox();
  if (!box) throw new Error("The log's list is not on screen.");
  await target.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  return { list, follow };
}

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
  await target
    .getByLabel(label("desktop.logs.minimum_level"))
    .selectOption("0");
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
  for (let press = 0; press < 3; press++) await target.keyboard.press("PageUp");
  // Moving up from the end leaves it.
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  const up = await focusedSeq();
  expect(up).toBeLessThan(newest - 20);
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
  await target.keyboard.press("PageDown");
  expect(await focusedSeq()).toBeGreaterThan(next + 3);
  expect(await inView()).toBe(true);
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
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000&feed=30",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
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
      };
    });
    // On the newest record the log follows again, as it should.
    if (at.newest) break;
    expect(at.inView, `press ${press}`).toBe(true);
    await expect(follow, `press ${press}`).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  }
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
    .getByRole("combobox")
    .fill(label("desktop.pane.maximize_panel"));
  await target.keyboard.press("Enter");
  await expect(target.locator(".palette")).toHaveCount(0);
  await expect(follow).toBeFocused();
});

test("Follow is reached by the keyboard where the eye finds it, in each shape of the bar", async ({
  page: target,
}) => {
  const order = async () => {
    const follow = target.getByRole("button", {
      name: label("desktop.logs.follow"),
    });
    // One Follow is shown, however many places the bar keeps for it.
    await expect(follow).toHaveCount(1);
    return target.locator(".logview").evaluate((view, name) => {
      const controls = [
        ...view.querySelectorAll<HTMLElement>(
          ":scope > div:first-child :is(input, select, button)",
        ),
      ].filter((control) => control.offsetParent !== null);
      const at = controls.findIndex(
        (control) => control.textContent?.trim() === name,
      );
      const lefts = controls.map((control) =>
        Math.round(control.getBoundingClientRect().left),
      );
      const tops = controls.map((control) =>
        Math.round(control.getBoundingClientRect().top),
      );
      return {
        at,
        count: controls.length,
        // Among the controls of its own row, how many stand to its left.
        before: controls.filter(
          (_, index) =>
            Math.abs((tops[index] ?? 0) - (tops[at] ?? 0)) < 8 &&
            (lefts[index] ?? 0) < (lefts[at] ?? 0),
        ).length,
        rowmates: controls.filter(
          (_, index) => Math.abs((tops[index] ?? 0) - (tops[at] ?? 0)) < 8,
        ).length,
      };
    }, label("desktop.logs.follow"));
  };
  // A wide bar: one row, Follow last on it and last for the keyboard.
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in");
  await openLogs(target);
  await expect(target.locator(".logview-list .record").first()).toBeVisible();
  let found = await order();
  expect(found.at).toBe(found.count - 1);
  expect(found.before).toBe(found.rowmates - 1);
  // A narrow bar: two rows, Follow at the end of the first, after the level.
  await target.setViewportSize({ width: 700, height: 900 });
  found = await order();
  expect(found.at).toBe(2);
  expect(found.before).toBe(2);
  expect(found.rowmates).toBe(3);
  // A short panel: one row again, Follow first on it and first for the
  // keyboard, and still on screen when the keyboard has gone to the far end
  // of a bar that scrolls sideways.
  await target.setViewportSize({ width: 700, height: 420 });
  found = await order();
  expect(found.at).toBe(0);
  expect(found.before).toBe(0);
  const follow = target.getByRole("button", {
    name: label("desktop.logs.follow"),
  });
  await follow.focus();
  for (let press = 1; press < found.count; press++)
    await target.keyboard.press("Tab");
  await expect(follow).toBeInViewport({ ratio: 1 });
});

test("maximizing the bottom panel over the pane that holds the keyboard takes it into the panel", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(target.locator(".docs-frame")).toBeVisible();
  for (const from of ["tui", "docs"] as const) {
    if (from === "tui") {
      await target.locator('[data-terminal="tui"] .xterm-screen').click();
      await expect(tui(target)).toBeFocused();
    } else {
      await target.locator(".docs-frame").focus();
      await expect(target.locator(".docs-frame")).toBeFocused();
    }
    await target.keyboard.press("Control+Shift+KeyK");
    const palette = target.locator(".palette");
    await palette
      .getByRole("combobox")
      .fill(label("desktop.pane.maximize_panel"));
    await target.keyboard.press("Enter");
    await expect(target.locator(".pane-tui")).toBeHidden();
    // The view the panel's tab shows takes it: not the document, where no
    // key works, and not a pane that is no longer there.
    await expect(
      target.locator('[data-terminal="console"] textarea'),
    ).toBeFocused();
    // And back, for the next pane to start from.
    await target.keyboard.press("Control+Shift+KeyK");
    await palette.getByRole("combobox").fill(label("desktop.pane.restore"));
    await target.keyboard.press("Enter");
    await expect(target.locator(".pane-tui")).toBeVisible();
  }
});

test("Space on a record with no detail does not scroll the log", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000",
  );
  await openLogs(target);
  const { list, follow } = await overLog(target);
  await target.mouse.wheel(0, -1500);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // A record in view that has no detail to open.
  const plain = await list.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
      (candidate) =>
        candidate.getBoundingClientRect().top >= box.top &&
        !candidate.querySelector("[aria-expanded]"),
    );
    return Number(row?.dataset.seq);
  });
  await list.locator(`.record[data-seq="${plain}"]`).focus();
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

test("a pane's note that is cut for want of room still says all of itself", async ({
  page: target,
}) => {
  // A window at 200 percent, in the language with the longest words: the
  // note beside the TUI's title has room for a few letters.
  await target.setViewportSize({ width: 640, height: 450 });
  await open(target, "signed-out", "&lang=hu");
  await expect(target.locator(".sign-in input[type=password]")).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  const note = target.locator(".pane-tui .pane-note");
  const whole = label("desktop.account.signed_out", {}, "hu");
  await expect(note).toHaveText(whole);
  expect(
    await note.evaluate((element) => element.scrollWidth > element.clientWidth),
  ).toBe(true);
  // The title beside it is whole, the note says the rest to a pointer that
  // rests on it, and the pane itself says it in full.
  expect(
    await target
      .locator(".pane-tui .pane-title")
      .evaluate((element) => element.scrollWidth <= element.clientWidth),
  ).toBe(true);
  await expect(note).toHaveAttribute("title", whole);
  await expect(
    target.locator(".pane-tui").getByText(whole, { exact: true }).last(),
  ).toBeInViewport();
});

test("hiding the TUI from inside it leaves the keyboard in the window", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(target.locator(".docs-frame")).toBeVisible();
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await expect(tui(target)).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+T");
  await expect(target.locator(".pane-tui")).toBeHidden();
  // The pane that is left takes it: not the document, where no key works.
  await expect(target.locator(".docs-frame")).toBeFocused();
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

// Every element that says something about the account says the same thing:
// the TUI pane and its header, settings, and the actions the palette offers.
const ACCOUNT_STATES: {
  scenario: string;
  /** What the TUI pane's header and body say; null where the TUI runs. */
  saying: string | null;
  /** The header's session dot. */
  dot: string;
  badge: string;
  /** Buttons the pane and settings offer, and actions the palette lists. */
  offers: string[];
  withholds: string[];
}[] = [
  {
    scenario: "signed-out",
    saying: "desktop.account.signed_out",
    dot: "unavailable",
    badge: "desktop.account.signed_out",
    offers: ["desktop.signin.submit"],
    withholds: ["desktop.account.sign_out", "desktop.account.create_profile"],
  },
  {
    scenario: "signed-in",
    saying: null,
    dot: "running",
    badge: "desktop.account.signed_in",
    offers: ["desktop.account.sign_out"],
    withholds: ["desktop.signin.submit", "desktop.account.create_profile"],
  },
  {
    scenario: "no-profile",
    saying: "desktop.account.no_profile",
    dot: "unavailable",
    badge: "desktop.account.signed_out",
    offers: ["desktop.account.create_profile"],
    withholds: ["desktop.signin.submit", "desktop.account.sign_out"],
  },
  {
    // A locked profile is not answered by a password: nothing offers one.
    scenario: "profile-locked",
    saying: "desktop.account.signed_out",
    dot: "unavailable",
    badge: "desktop.account.signed_out",
    offers: ["desktop.signin.open_tui"],
    withholds: [
      "desktop.signin.submit",
      "desktop.account.sign_out",
      "desktop.account.create_profile",
    ],
  },
  {
    scenario: "runtime-unavailable",
    saying: "desktop.account.services_down",
    dot: "unavailable",
    badge: "desktop.account.services_down",
    offers: ["desktop.signin.open_tui"],
    withholds: [
      "desktop.signin.submit",
      "desktop.account.sign_out",
      "desktop.account.create_profile",
    ],
  },
];

for (const state of ACCOUNT_STATES)
  test(`${state.scenario}: every element reads the same account state`, async ({
    page: target,
  }) => {
    await open(target, state.scenario);
    // The dialog, where there is one, is put aside to look at the window.
    if (state.saying) {
      await expect(target.locator(".sign-in")).toBeVisible();
      await target.keyboard.press("Escape");
      await expect(target.locator(".sign-in")).toHaveCount(0);
    }
    const pane = target.locator(".pane-tui");
    await expect(pane.locator(".pane-head [data-phase]")).toHaveAttribute(
      "data-phase",
      state.dot,
    );
    if (state.saying) {
      await expect(pane.locator(".pane-head")).toContainText(
        label(state.saying),
      );
      await expect(pane.locator("[data-slot=empty]")).toContainText(
        label(state.saying),
      );
    } else {
      await expect(pane.locator(".xterm")).toHaveCount(1);
    }
    for (const key of state.offers.filter(
      (offer) => offer !== "desktop.account.sign_out",
    ))
      await expect(
        pane.getByRole("button", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        pane.getByRole("button", { name: label(key), exact: true }),
      ).toHaveCount(0);

    // The calendar page says the same, or shows the calendar.
    const calendarToggle = target
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.calendar.title") });
    await calendarToggle.click();
    const calendarRegion = target.getByRole("region", {
      name: label("desktop.calendar.title"),
    });
    if (state.saying)
      await expect(calendarRegion).toContainText(label(state.saying));
    else
      await expect(calendarRegion.getByRole("listitem").first()).toBeVisible();
    for (const key of state.offers.filter(
      (offer) => offer !== "desktop.account.sign_out",
    ))
      await expect(
        calendarRegion.getByRole("button", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        calendarRegion.getByRole("button", { name: label(key), exact: true }),
      ).toHaveCount(0);
    // Messages has a count only for a signed-in profile; otherwise it says
    // the same thing the panes say.
    const messages = target
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.rail.messages") });
    if (state.saying) {
      await expect(messages).toHaveAccessibleName(
        `${label("desktop.rail.messages")}, ${label(state.saying)}`,
      );
      await expect(messages.locator("[data-pin]")).toHaveCount(1);
    } else {
      await expect(messages.locator("[data-slot=badge]")).toHaveText("3");
    }
    await calendarToggle.click();
    await expect(calendarRegion).toHaveCount(0);

    // Settings: the session section says the same and offers the same.
    await target
      .getByRole("button", { name: label("desktop.rail.settings") })
      .click();
    const session = target.getByRole("region", {
      name: label("desktop.settings.session"),
    });
    await expect(
      session.getByText(label(state.badge), { exact: true }),
    ).toBeVisible();
    const settings = target.locator(".settings");
    for (const key of state.offers)
      await expect(
        settings.getByRole("button", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        settings.getByRole("button", { name: label(key), exact: true }),
      ).toHaveCount(0);
    await target.keyboard.press("Escape");

    // The palette lists the same actions, and no others of the account's.
    await target
      .getByRole("button", { name: label("desktop.rail.search") })
      .click();
    const palette = target.locator(".palette");
    for (const key of [...state.offers, ...state.withholds]) {
      await palette.getByRole("combobox").fill(label(key));
      const row = palette
        .locator(".palette-title")
        .filter({ hasText: new RegExp(`^${label(key)}$`) });
      await expect(row).toHaveCount(state.offers.includes(key) ? 1 : 0);
    }
  });

test("no-profile: the dialog offers the TUI's setup and no password field", async ({
  page: target,
}) => {
  await open(target, "no-profile");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(label("desktop.account.no_profile"));
  await expect(dialog).toContainText(label("desktop.account.no_profile_lead"));
  await expect(password(target)).toHaveCount(0);
  const setUp = dialog.getByRole("button", {
    name: label("desktop.account.create_profile"),
    exact: true,
  });
  await expect(setUp).toBeFocused();
  await setUp.click();
  // The TUI takes over: its own flow creates or chooses the profile.
  await expect(dialog).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(0);
});

const tui = (target: Page) => target.locator('[data-terminal="tui"] textarea');

// Wherever the TUI's own flow is chosen from, the keyboard follows it there.
for (const from of ["pane", "settings", "palette"] as const)
  test(`no-profile: setting up a profile from the ${from} puts the keyboard in the TUI`, async ({
    page: target,
  }) => {
    await open(target, "no-profile");
    await expect(target.locator(".sign-in")).toBeVisible();
    await target.keyboard.press("Escape");
    await expect(target.locator(".sign-in")).toHaveCount(0);
    const setUp = {
      name: label("desktop.account.create_profile"),
      exact: true,
    };
    if (from === "pane") {
      await target.locator(".pane-tui").getByRole("button", setUp).click();
    } else if (from === "settings") {
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .click();
      await target.locator(".settings").getByRole("button", setUp).click();
      await expect(target.locator(".settings")).toHaveCount(0);
    } else {
      await target
        .getByRole("button", { name: label("desktop.rail.search") })
        .click();
      const palette = target.locator(".palette");
      await palette.getByRole("combobox").fill(setUp.name);
      await target.keyboard.press("Enter");
      await expect(palette).toHaveCount(0);
    }
    await expect(tui(target)).toBeFocused();
  });

test("profile-locked: the pane says why and offers only the TUI", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password(target)).toHaveCount(0);
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  const pane = target.locator(".pane-tui");
  await expect(pane).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  const onward = pane.getByRole("button", {
    name: label("desktop.signin.open_tui"),
    exact: true,
  });
  await expect(onward).toBeFocused();
  await onward.click();
  await expect(tui(target)).toBeFocused();
  await expect.poll(calls(target, "signIn")).toBe(0);
});

test("runtime-unavailable: the dialog and settings say what the window says", async ({
  page: target,
}) => {
  await open(target, "runtime-unavailable");
  const dialog = target.locator(".sign-in");
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(dialog).not.toContainText(label("desktop.signin.title"));
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  // With no runtime to ask, the profile is not known: it is not said to be
  // none, and no section stands empty for it.
  const settings = target.locator(".settings");
  await expect(
    settings.getByRole("region", { name: label("desktop.signin.profile") }),
  ).toHaveCount(0);
  await expect(settings).not.toContainText(label("desktop.account.no_profile"));
  await expect(
    settings.getByRole("region", { name: label("desktop.settings.window") }),
  ).toBeVisible();
});

test("wrong-password: a refusal that was seen is not shown again", async ({
  page: target,
}) => {
  await open(target, "wrong-password");
  await password(target).fill("not-the-password");
  await submit(target).click();
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(label("desktop.signin.refused.invalid"));
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await target
    .locator(".pane-tui")
    .getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  await expect(password(target)).toBeFocused();
  await expect(dialog).not.toContainText(
    label("desktop.signin.refused.invalid"),
  );
});

test("throttled: a wait that is still running outlasts the dialog", async ({
  page: target,
}) => {
  await open(target, "throttled");
  await password(target).fill("anything");
  await submit(target).click();
  const dialog = target.locator(".sign-in");
  await expect(dialog.locator("button[type=submit]")).toBeDisabled();
  const left = async () =>
    Number(
      /\b(\d+)\b/.exec(
        (await dialog
          .locator('[data-slot=alert] span[aria-hidden="true"]')
          .textContent()) ?? "",
      )?.[1],
    );
  await expect.poll(left).toBeLessThan(30);
  const before = await left();
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await target
    .locator(".pane-tui")
    .getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  await expect(dialog.locator("button[type=submit]")).toBeDisabled();
  // The same wait, further along: not a new thirty seconds.
  const after = await left();
  expect(after).toBeGreaterThan(0);
  expect(after).toBeLessThanOrEqual(before);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("one Escape closes the dialog from a button showing its tooltip", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(password(target)).toBeFocused();
  // The reveal button follows the field; focused by keyboard, it shows its
  // tooltip, which is a layer above the dialog.
  await target.keyboard.press("Tab");
  await expect(target.getByRole("tooltip")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
});

test("sign-out-refused: the failure is said once, not again when settings reopens", async ({
  page: target,
}) => {
  await open(target, "sign-out-refused");
  const settingsButton = target.getByRole("button", {
    name: label("desktop.rail.settings"),
  });
  await settingsButton.click();
  const settings = target.locator(".settings");
  await settings
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(settings.getByRole("alert")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await settingsButton.click();
  await expect(settings).toBeVisible();
  await expect(settings.getByRole("alert")).toHaveCount(0);
  // The same however settings is closed: by its own button this time.
  await settings
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(settings.getByRole("alert")).toBeVisible();
  await settingsButton.click();
  await expect(settings).toHaveCount(0);
  await settingsButton.click();
  await expect(settings).toBeVisible();
  await expect(settings.getByRole("alert")).toHaveCount(0);
});

test("signing out leaves no running session showing in the TUI's header", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const dot = target.locator(".pane-tui .pane-head [data-phase]");
  await expect(dot).toHaveAttribute("data-phase", "running");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(dot).toHaveAttribute("data-phase", "unavailable");
  await expect(target.locator(".pane-tui .pane-head")).toContainText(
    label("desktop.account.signed_out"),
  );
});

test("the rail keeps its order: search, window toggles, shortcuts, panel toggles", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const names = await target
    .locator(".rail-group")
    .first()
    .getByRole("button")
    .evaluateAll((buttons) =>
      buttons.map((button) => button.getAttribute("aria-label") ?? ""),
    );
  // The packaged run reaches search and docs home by these two positions.
  expect(names.map((name) => name.split(",")[0])).toEqual(
    [
      "desktop.rail.search",
      "desktop.rail.docs_home",
      "desktop.rail.tui",
      "desktop.calendar.title",
      "desktop.rail.messages",
      "desktop.rail.aeat",
      "desktop.rail.console",
      "desktop.rail.python",
      "desktop.rail.logs",
    ].map((key) => label(key)),
  );
});

const calendarButton = (target: Page) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.calendar.title") });

/** How many times the shell has asked the host for the filing calendar. */
const calendarReads = (target: Page) => () =>
  target.evaluate(
    () =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter((made) =>
        made.startsWith("filingCalendar "),
      ).length ?? 0,
  );

/** The day the fixture calendar was evaluated on, at noon. */
const FIXTURE_DAY = new Date(2026, 9, 6, 12);

test("the filing calendar is a page of the first pane, read when it is shown", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(FIXTURE_DAY);
  await open(target, "signed-in");
  const pane = target.locator(".pane-docs");
  await expect(pane.locator(".docs-frame")).toBeVisible();
  // Nothing is read for a page nobody is looking at.
  expect(await calendarReads(target)()).toBe(0);
  await calendarButton(target).click();
  await expect(calendarButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(pane.locator(".pane-title")).toHaveText(
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

test("the calendar's months draw each filing window across the days it is open", async ({
  page: target,
}) => {
  // Short enough that the months before the current one cannot all be in
  // view with it: opening on it is something the page has to do.
  await target.setViewportSize({ width: 1280, height: 640 });
  await open(target, "signed-in");
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
      new Date(2026, 6, 1),
    ),
  );
  // It opens on the month the product evaluated in, with that day marked.
  const october = page.locator('.calendar-month[data-month="2026-10"]');
  await expect(october.getByRole("heading", { level: 2 })).toBeInViewport();
  await expect(page.locator(".calendar-grid-today")).toHaveText(["6"]);
  await expect(
    october.locator('[data-day="2026-10-06"] .calendar-grid-today'),
  ).toHaveCount(1);

  // Where on the page a day and a window are.
  const edges = async (locator: Locator) => {
    const box = (await locator.boundingBox())!;
    return { left: box.x, right: box.x + box.width, top: box.y };
  };
  const dayOf = (iso: string) => page.locator(`[data-day="${iso}"]`);
  // A window open from the first to the twentieth crosses four weeks where
  // the week begins on Sunday, and is drawn in each: from its first day to
  // the week's end, across two whole weeks, and up to its closing day.
  const window303 = october.locator('.calendar-bar[data-entry="303:2026-3T"]');
  await expect(window303).toHaveCount(4);
  const spans = [
    ["2026-10-01", "2026-10-03"],
    ["2026-10-04", "2026-10-10"],
    ["2026-10-11", "2026-10-17"],
    ["2026-10-18", "2026-10-20"],
  ] as const;
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
      `${label("desktop.calendar.modelo", { modelo: "303" })} 2026-3T`,
      short.formatRange(new Date(2026, 9, 1), new Date(2026, 9, 20)),
      label("desktop.calendar.state.due"),
    ].join(", "),
  );
  await expect(page.getByRole("button", { name: /303.* 2026-3T/ })).toHaveCount(
    1,
  );
  for (const index of [1, 2, 3]) {
    await expect(window303.nth(index)).toHaveAttribute("aria-hidden", "true");
    await expect(window303.nth(index)).toHaveAttribute("tabindex", "-1");
  }
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
  for (const key of ["111:2026-3T", "130:2026-3T", "303:2026-3T"])
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
    october.locator('.calendar-bar[data-entry="111:2026-3T"]').first(),
  ).toHaveAttribute("data-state", "filed");

  // A window whose opening was not reported is not guessed at: its closing
  // day alone is drawn, and it says the opening is not known.
  const unknown = page.locator('.calendar-bar[data-entry="349:2026-3T"]');
  await expect(unknown).toHaveCount(1);
  const closing = await edges(dayOf("2026-10-20"));
  const drawn = await edges(unknown);
  expect(Math.abs(drawn.left - closing.left)).toBeLessThanOrEqual(3);
  expect(Math.abs(drawn.right - closing.right)).toBeLessThanOrEqual(3);
  await expect(unknown).toHaveAccessibleName(
    new RegExp(
      `${short.format(new Date(2026, 9, 20))} \\(${label("desktop.calendar.window_unknown")}\\)`,
    ),
  );

  // A window that runs from one month into the next is drawn in both: the
  // fourth quarter's, moved from a Saturday to the Monday after.
  await expect(
    page.locator(
      '.calendar-month[data-month="2027-01"] .calendar-bar[data-entry="303:2026-4T"]',
    ),
  ).not.toHaveCount(0);
  await expect(
    page.locator(
      '.calendar-month[data-month="2027-02"] .calendar-bar[data-entry="303:2026-4T"]',
    ),
  ).toHaveCount(1);

  // What was observed stands on its own day: the profile's filings and the
  // agency's message, each said with its date and the product's sentence.
  const events = page.locator(".calendar-event");
  await expect(events).toHaveCount(3);
  const filed = dayOf("2026-10-02").locator(".calendar-event");
  await expect(filed).toHaveAttribute("data-event", "filing");
  await expect(filed).toHaveAccessibleName(
    `${new Intl.DateTimeFormat("en", { dateStyle: "full" }).format(
      new Date(2026, 9, 2),
    )}: ${label("desktop.calendar.event.filing")}. Modelo 111 2026-3T filed`,
  );
  await expect(dayOf("2026-09-03").locator(".calendar-event")).toHaveAttribute(
    "data-event",
    "message",
  );
  // Nothing was read a second time to draw the months.
  expect(await calendarReads(target)()).toBe(1);
});

test("the months begin the week on the day the language does", async ({
  page: target,
}) => {
  for (const [language, first] of [
    ["en", new Date(2026, 9, 4)],
    ["es", new Date(2026, 9, 5)],
    ["hu", new Date(2026, 9, 5)],
  ] as const) {
    await open(target, "signed-in", `&lang=${language}`);
    await target
      .getByRole("button", {
        name: label("desktop.calendar.title", {}, language),
        exact: true,
      })
      .click();
    const october = target.locator('.calendar-month[data-month="2026-10"]');
    // The first of its weekday letters, and the day under it in the first
    // whole week: a Sunday in English, a Monday in Spanish and Hungarian.
    await expect(
      october.locator("[aria-hidden=true] > span").first(),
    ).toHaveText(
      new Intl.DateTimeFormat(language, { weekday: "narrow" }).format(first),
    );
    const iso = "2026-10-0" + first.getDate();
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
    page.locator('.calendar-month[data-month="2026-10"] h2'),
  ).toBeInViewport();
  await expect(list.getByRole("separator")).toBeInViewport();
  expect(await list.evaluate((element) => element.scrollTop)).toBeGreaterThan(
    0,
  );

  // Chosen among the months, an obligation is marked in the list, and all
  // of its window is marked among the months.
  const bars = page.locator('.calendar-bar[data-entry="303:2026-4T"]');
  const row = list.locator('li[data-entry="303:2026-4T"]');
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
  const far = page.locator('.calendar-bar[data-entry="100:2026"]').first();
  await expect(far).not.toBeInViewport();
  await list.locator('li[data-entry="100:2026"]').getByRole("button").click();
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.pane.restore") })
    .click();
  await expect(view).toBeVisible();
  await expect(far).toHaveAttribute("aria-pressed", "true");
  await expect(far).toBeInViewport();
  await view
    .getByRole("radio", { name: label("desktop.calendar.view_list") })
    .click();
  const kept = page.locator('.calendar-list li[data-entry="100:2026"]');
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
    await calendarButton(target).click();
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
  const cell = found.page.locator('[data-day="2026-10-06"]');
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
  await target.clock.setFixedTime(new Date(2026, 9, 7, 9));
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
  const stale = found.page.locator('[data-day="2026-10-06"]');
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

test("the calendar says what its marks are, and has a way back to where it stands", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(FIXTURE_DAY);
  await target.setViewportSize({ width: 1280, height: 640 });
  await open(target, "signed-in");
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
  const october = page.locator('.calendar-month[data-month="2026-10"] h2');
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
  await target.clock.setFixedTime(new Date(2026, 9, 7, 9));
  await open(target, "signed-in");
  await calendarButton(target).click();
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
    .getByRole("combobox")
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

test("the months come back to the month the reader left them on, in a pane and beside the list", async ({
  page: target,
}) => {
  await open(target, "signed-in");
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
  const head = target.locator(".pane-docs .pane-head");
  // Maximized, the months are laid out anew beside the list: on January.
  await head
    .getByRole("button", { name: label("desktop.calendar.maximize") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  await expect(heading("2027-01")).toBeInViewport();
  await expect(heading("2026-10")).not.toBeInViewport();
  // And back in a pane, the same.
  await head
    .getByRole("button", { name: label("desktop.pane.restore") })
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
  await target.setViewportSize({ width: 1600, height: 900 });
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const head = target.locator(".pane-docs .pane-head");
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
      .getByRole("button", { name: label("desktop.calendar.maximize") })
      .click();
    await expect(page.locator(".calendar-aside")).toBeVisible();
    expect(
      Math.abs((await under(begins)) - left.begins),
      `maximized ${round}`,
    ).toBeLessThanOrEqual(1);
    await head
      .getByRole("button", { name: label("desktop.pane.restore") })
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
    .getByRole("button", { name: label("desktop.calendar.maximize") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  expect(Math.abs((await under(begins)) - chosenAt.begins)).toBeLessThanOrEqual(
    1,
  );
  await head
    .getByRole("button", { name: label("desktop.pane.restore") })
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
    .getByRole("button", { name: label("desktop.calendar.maximize") })
    .click();
  const aside = page.locator(".calendar-aside");
  await expect(aside).toBeVisible();
  expect(await aside.evaluate((element) => element.scrollTop)).toBe(0);
  await head
    .getByRole("button", { name: label("desktop.pane.restore") })
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
  // Tall enough that the months fit without scrolling until one is whole.
  await target.setViewportSize({ width: 1600, height: 1500 });
  await open(target, "signed-in", "&calendar=busy");
  await calendarButton(target).click();
  await target
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
  await calendarButton(target).click();
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
  const head = target.locator(".pane-docs .pane-head");
  await head
    .getByRole("button", { name: label("desktop.calendar.maximize") })
    .click();
  await expect(page.locator(".calendar-aside")).toBeVisible();
  expect(Math.abs((await top()) - inside)).toBeLessThanOrEqual(1);
  await head
    .getByRole("button", { name: label("desktop.pane.restore") })
    .click();
  await expect(page.locator(".calendar-aside")).toHaveCount(0);
  expect(Math.abs((await top()) - inside)).toBeLessThanOrEqual(1);
});

test("a calendar put away and brought back is as it was left", async ({
  page: target,
}) => {
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await open(target, "signed-in", "&calendar=busy");
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
  test(`a window's edge stands out from the card and from its own fill (${scheme})`, async ({
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
        if (!bar) return { state, card: 0, fill: 0 };
        const style = getComputedStyle(bar);
        const edge = over(rgba(style.borderTopColor), card);
        return {
          state,
          card: ratio(edge, card),
          fill: ratio(edge, over(rgba(style.backgroundColor), card)),
        };
      });
    });
    // Three to one is the least a part of a control needs to be made out.
    for (const { state, card, fill } of ratios) {
      expect(card, `${state} against the card`).toBeGreaterThanOrEqual(3);
      expect(fill, `${state} against its fill`).toBeGreaterThanOrEqual(3);
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
    .locator(".pane-docs .pane-head")
    .getByRole("button", { name: label("desktop.calendar.maximize") })
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
  // What is late and what is not known are told by the edge, and by a
  // mark where the window has room, with the hue gone.
  const late = page.locator('.calendar-bar[data-state="late"]').first();
  const unknown = page.locator('.calendar-bar[data-state="unknown"]').first();
  const due = page.locator('.calendar-bar[data-state="due"]').first();
  expect(await style(late, "border-top-style")).toBe("dashed");
  expect(await style(due, "border-top-style")).toBe("solid");
  await expect(late.locator("[data-slot=icon]")).toBeVisible();
  await expect(due.locator("[data-slot=icon]")).toHaveCount(0);
  // What is filed is the first a crowded week gives up: it is found with
  // its month drawn whole, hollow where what is due is filled, and with a
  // double edge here, where there is no fill to be hollow against.
  await page
    .locator('.calendar-month[data-month="2027-01"] .calendar-whole')
    .click();
  const filed = page.locator('.calendar-bar[data-state="filed"]').first();
  await expect(filed.locator("[data-slot=icon]")).toBeVisible();
  expect(await style(filed, "border-top-style")).toBe("double");
  expect(await style(filed, "border-top-width")).toBe("3px");
  // The unknown window of the fixture is one day wide and is found whole.
  await page
    .locator('.calendar-month[data-month="2027-02"] .calendar-whole')
    .click();
  expect(await style(unknown, "border-top-style")).toBe("dotted");
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

test("a calendar left on screen past midnight is read again for the new day", async ({
  page: target,
}) => {
  await target.clock.install({ time: new Date(2026, 9, 6, 23, 59, 40) });
  await open(target, "signed-in");
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

test("a crowded month shows each week's nearest deadlines and counts the rest, and can be drawn whole", async ({
  page: target,
}) => {
  // The day the crowded fixture was evaluated on.
  await target.clock.setFixedTime(new Date(2027, 0, 12, 12));
  await open(target, "signed-in", "&calendar=busy");
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

test("the documentation keeps its place under the calendar", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const frame = target.frameLocator(".docs-frame");
  await frame.getByRole("link", { name: "Second page" }).click();
  await expect(frame.getByRole("heading", { level: 1 })).not.toHaveText(
    "Stand-in documentation",
  );
  const second = await frame.getByRole("heading", { level: 1 }).textContent();
  await calendarButton(target).click();
  await expect(target.locator(".docs-frame")).toBeHidden();
  await expect(target.locator(".docs-frame")).toHaveCount(1);
  // Put away by the same button, or by the pane's own way back.
  await calendarButton(target).click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(calendarButton(target)).toHaveAttribute("aria-pressed", "false");
  await expect(frame.getByRole("heading", { level: 1 })).toHaveText(
    second ?? "",
  );
  await calendarButton(target).click();
  // The header speaks of the calendar while it shows it.
  const head = target.locator(".pane-docs .pane-head");
  await expect(
    head.getByRole("button", { name: label("desktop.calendar.maximize") }),
  ).toBeVisible();
  await expect(
    head.getByRole("button", { name: label("desktop.pane.maximize_docs") }),
  ).toHaveCount(0);
  await head
    .getByRole("button", { name: label("desktop.calendar.close") })
    .click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(target.locator(".pane-docs .pane-title")).toHaveText(
    label("desktop.pane.docs"),
  );
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
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .locator(".settings")
    .getByRole("button", {
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
  await expect(page.getByRole("alert")).toContainText("timed_out");
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
  await expect(page.getByRole("alert")).toContainText("timed_out");
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

test("the calendar's sign-in gets focus back when the dialog is put aside", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  // With the TUI hidden, its way back in is not on screen to fall back to.
  await target
    .locator(".pane-tui .pane-head")
    .getByRole("button")
    .last()
    .click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  const signIn = page.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  await signIn.click();
  await expect(password(target)).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(signIn).toBeFocused();
  // Signed in from here, the keyboard is in the calendar that loads.
  await signIn.click();
  await password(target).fill("demo");
  await submit(target).click();
  await expect(page.getByRole("listitem").first()).toBeVisible();
  await expect(page).toBeFocused();
});

test("signing out from the calendar leaves the keyboard on its page", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await page
    .getByRole("button", { name: label("desktop.calendar.refresh") })
    .focus();
  await target.keyboard.press("ControlOrMeta+k");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.account.sign_out"));
  await target.keyboard.press("Enter");
  await expect(page).toContainText(label("desktop.account.signed_out"));
  await expect(page.getByRole("listitem")).toHaveCount(0);
  await expect(page).toBeFocused();
});

test("the calendar's own actions replace the documentation's while it is shown", async ({
  page: target,
}) => {
  await target.clock.install();
  await open(target, "signed-in");
  await calendarButton(target).click();
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  for (const key of ["desktop.action.zoom_in", "desktop.action.docs_back"]) {
    await palette.getByRole("combobox").fill(label(key));
    await expect(
      palette.locator(".palette-title").filter({ hasText: label(key) }),
    ).toHaveCount(0);
  }
  await target.keyboard.press("Escape");
  // A zoom chord changes nothing that is not on screen. The layout is
  // saved a quarter of a second after a change: the clock is run past it.
  await target.keyboard.press("ControlOrMeta+=");
  await target.clock.runFor(2000);
  await calendarButton(target).click();
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  await palette.getByRole("combobox").fill(label("desktop.action.zoom_reset"));
  await expect(
    palette
      .locator(".palette-title")
      .filter({ hasText: label("desktop.action.zoom_reset") }),
  ).toHaveCount(1);
  expect(
    await target.evaluate(
      () =>
        JSON.parse(localStorage.getItem("cadrumo-shell-layout") ?? "{}").layout
          ?.zoom ?? 1,
    ),
  ).toBe(1);
});

test("the calendar chosen while the TUI is maximized takes the keyboard", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toBeFocused();
  await target
    .locator(".pane-tui .pane-head")
    .getByRole("button", { name: label("desktop.pane.maximize_tui") })
    .click();
  await expect(page).toBeHidden();
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await target.keyboard.press("ControlOrMeta+Shift+k");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.calendar.title"));
  await target.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
});

test("putting the calendar away from the rail leaves the keyboard on the rail", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await calendarButton(target).focus();
  await target.keyboard.press("Enter");
  await expect(
    target.getByRole("region", { name: label("desktop.calendar.title") }),
  ).toBeFocused();
  await calendarButton(target).focus();
  await target.keyboard.press("Enter");
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(calendarButton(target)).toBeFocused();
});

test("profile-locked: the dialog and settings say it and offer the TUI", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  // Not titled as a sign-in where there is nothing to sign in with.
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.account.signed_out"),
  );
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = target.locator(".settings");
  await expect(settings).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await settings
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(settings).toHaveCount(0);
  await expect(tui(target)).toBeFocused();
});

test("a refusal does not take the keyboard back from where the person moved it", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=wrong-password&latency=600");
  await password(target).fill("not-the-password");
  await target.keyboard.press("Enter");
  const dismiss = target
    .locator(".sign-in")
    .getByRole("button", { name: label("desktop.signin.dismiss") });
  await dismiss.focus();
  await expect(target.locator(".sign-in")).toContainText(
    label("desktop.signin.refused.invalid"),
  );
  await expect(dismiss).toBeFocused();
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
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(calendarButton(target)).toHaveCount(0);
  await expect(messagesButton(target)).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  for (const key of ["desktop.calendar.title", "desktop.rail.messages"]) {
    await palette.getByRole("combobox").fill(label(key));
    await expect(
      palette.locator(".palette-title").filter({ hasText: label(key) }),
    ).toHaveCount(0);
  }
  expect(await calls(target, "notifications")()).toBe(0);
});

const messagesButton = (target: Page) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.messages") });

const named = (key: string, values: Record<string, string | number> = {}) =>
  `${label("desktop.rail.messages")}, ${Object.entries(values).reduce(
    (text, [name, value]) => text.replace(`{${name}}`, String(value)),
    label(key),
  )}`;

test("the messages button counts what is unread and opens the TUI", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const button = messagesButton(target);
  // The count is in the name, not only in the corner.
  await expect(button).toHaveAccessibleName(
    named("desktop.messages.unread", { count: 3 }),
  );
  await expect(button.locator("[data-slot=badge]")).toHaveText("3");
  await expect(button.locator("[data-pin]")).toHaveCount(0);
  await expect.poll(calls(target, "notifications")).toBe(1);
  await button.click();
  await expect(tui(target)).toBeFocused();
  // Hidden, the TUI is shown again.
  await target
    .locator(".pane-tui .pane-head")
    .getByRole("button")
    .last()
    .click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await button.click();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await expect(tui(target)).toBeFocused();
});

test("the palette's messages action opens the TUI", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.rail.messages"));
  await target.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(tui(target)).toBeFocused();
});

test("messages are read at sign-in and dropped at sign-out, never while signed out", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const button = messagesButton(target);
  // Under the dialog the rail is out of the accessibility tree, so the
  // button is found by its attribute: no count, and the account's own
  // reason why.
  await expect(target.locator(".sign-in")).toBeVisible();
  const withheld = named("desktop.account.signed_out");
  const plain = target.locator(`.rail button[aria-label="${withheld}"]`);
  await expect(plain).toHaveCount(1);
  await expect(plain.locator("[data-slot=badge]")).toHaveCount(0);
  await expect(plain.locator("[data-pin=unknown]")).toHaveCount(1);
  expect(await calls(target, "notifications")()).toBe(0);
  await password(target).fill("demo");
  await submit(target).click();
  await expect(button).toHaveAccessibleName(
    named("desktop.messages.unread", { count: 3 }),
  );
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .locator(".settings")
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(button).toHaveAccessibleName(withheld);
  await expect(button.locator("[data-slot=badge]")).toHaveCount(0);
  await expect.poll(calls(target, "notifications")).toBe(1);
});

test("until the messages answer, the button shows them as not known", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=1500&bar=off");
  const button = messagesButton(target);
  // No count yet is not none unread: the hollow pin stands meanwhile.
  await expect(button.locator("[data-pin=unknown]")).toHaveCount(1);
  await expect(button.locator("[data-slot=badge]")).toHaveCount(0);
  await expect(button.locator("[data-slot=badge]")).toHaveText("3");
  await expect(button.locator("[data-pin]")).toHaveCount(0);
});

test("messages, with the TUI withheld, leads to the way in", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  // From the documentation's side of the window, with the TUI hidden.
  await target
    .locator(".pane-tui .pane-head")
    .getByRole("button")
    .last()
    .click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await messagesButton(target).click();
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeFocused();
});

for (const origin of [
  "start",
  "pane",
  "calendar",
  "palette",
  "settings",
] as const)
  test(`the dialog's way to the TUI takes the keyboard there, opened from the ${origin}`, async ({
    page: target,
  }) => {
    await open(target, "signed-out");
    const dialog = target.locator(".sign-in");
    await expect(dialog).toBeVisible();
    const signIn = { name: label("desktop.signin.submit"), exact: true };
    if (origin !== "start") {
      await target.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
    }
    if (origin === "pane") {
      await target.locator(".pane-tui").getByRole("button", signIn).click();
    } else if (origin === "calendar") {
      await calendarButton(target).click();
      await target
        .getByRole("region", { name: label("desktop.calendar.title") })
        .getByRole("button", signIn)
        .click();
    } else if (origin === "palette") {
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .focus();
      await target.keyboard.press("ControlOrMeta+k");
      await target
        .locator(".palette")
        .getByRole("combobox")
        .fill(label("desktop.signin.submit"));
      await target.keyboard.press("Enter");
    } else if (origin === "settings") {
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .click();
      await target.locator(".settings").getByRole("button", signIn).click();
    }
    await expect(password(target)).toBeFocused();
    await dialog
      .getByRole("button", {
        name: label("desktop.signin.open_tui"),
        exact: true,
      })
      .click();
    await expect(tui(target)).toBeFocused();
  });

test("admitted after the dialog was put aside, the keyboard goes to the TUI", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-out&latency=1200");
  await password(target).fill("demo");
  await target.keyboard.press("Enter");
  // Put aside while the answer is on its way.
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(tui(target)).toBeFocused();
});

test("tui-unavailable: a TUI that cannot start is not a way on", async ({
  page: target,
}) => {
  // Records keep arriving, so the shell is drawn again and again while a
  // wish for focus could still be granted.
  await open(target, "tui-unavailable", "&feed=200");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toBeVisible();
  await target.keyboard.press("Escape");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await page
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  // The person is told why, and is back where a sign-in is offered: not
  // left "continuing" in a TUI that never started.
  await expect(target.locator("[data-slot=toast]")).toContainText(
    "spawn_failed",
  );
  // Back at the gate, the dialog is offered again, as when a TUI exits,
  // and it holds the keyboard: nothing behind it has been given focus.
  await expect(dialog).toBeVisible();
  await expect(password(target)).toBeFocused();
  await target.keyboard.type("x");
  await expect(password(target)).toHaveValue("x");
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page).not.toContainText(label("desktop.account.in_tui"));
  await expect(page).toContainText(label("desktop.account.signed_out"));
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeVisible();
});

test("tui-unavailable: the dialog's own way to the TUI comes back to a dialog that holds the keyboard", async ({
  page: target,
}) => {
  await open(target, "tui-unavailable");
  const dialog = target.locator(".sign-in");
  await expect(password(target)).toBeFocused();
  await dialog
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(target.locator("[data-slot=toast]")).toContainText(
    "spawn_failed",
  );
  await expect(dialog).toBeVisible();
  // Past the moment in which a focus wished for the TUI could be granted,
  // with the shell drawn again inside it: each return to the window has
  // the account read again, and each answer draws the shell.
  const asked = calls(target, "signInStatus");
  const before = await asked();
  for (let draw = 0; draw < 4; draw++) {
    await target.evaluate(() => window.dispatchEvent(new Event("focus")));
    await target.waitForTimeout(330);
  }
  expect(await asked()).toBeGreaterThan(before + 2);
  await expect(password(target)).toBeFocused();
});

test("signing in from the calendar keeps the keyboard in the calendar, with the TUI beside it", async ({
  page: target,
}) => {
  await open(target, "signed-out", "&feed=200");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await password(target).fill("demo");
  await submit(target).click();
  await expect(page.locator(".calendar-bar").first()).toBeVisible();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  // The TUI has started beside it, and has not taken the keyboard, through
  // the moment in which it could have and several draws of the shell.
  const held = await errorsHeld(target)();
  await target.waitForTimeout(1300);
  expect(await errorsHeld(target)()).toBeGreaterThan(held);
  await expect(page).toBeFocused();
});

test("a view asked for while the sign-in dialog is leaving gets the keyboard", async ({
  page: target,
}) => {
  const filter = target.locator(".logview .filter-text");
  // Put aside, with the logs asked for before the dialog has gone.
  await open(target, "signed-out");
  await expect(password(target)).toBeFocused();
  await target.keyboard.press("Escape");
  await target.keyboard.press("Control+Shift+KeyL");
  await expect(filter).toBeFocused();
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(filter).toBeFocused();
});

test("a view asked for as a sign-in is admitted gets the keyboard, not the TUI", async ({
  page: target,
}) => {
  const filter = target.locator(".logview .filter-text");
  // The dialog is a moment in leaving; the chord is pressed in that moment,
  // by the page itself the instant the dialog starts to go.
  await open(target, "signed-out");
  await password(target).fill("demo");
  await target.evaluate(() => {
    const dialog = document.querySelector(".sign-in");
    if (!dialog) throw new Error("no sign-in dialog");
    new MutationObserver((_, observer) => {
      if (dialog.getAttribute("data-state") !== "closed") return;
      observer.disconnect();
      document.body.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "L",
          code: "KeyL",
          ctrlKey: true,
          shiftKey: true,
          bubbles: true,
          cancelable: true,
        }),
      );
    }).observe(dialog, { attributes: true, attributeFilter: ["data-state"] });
  });
  await target.keyboard.press("Enter");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(filter).toBeFocused();
});

test("with the TUI hidden, the sign-in dialog leaves the keyboard in the documentation", async ({
  page: target,
}) => {
  // The window was last used with the TUI hidden.
  await open(target, "signed-in");
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await target.keyboard.press("Control+Shift+KeyT");
  await expect(target.locator(".pane-tui")).toBeHidden();
  // Put aside: no pane holds a way in, so the pane that is shown takes it.
  await open(target, "signed-out");
  await expect(password(target)).toBeFocused();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(target.locator(".docs-frame")).toBeFocused();
  // Admitted: the same, where there is no TUI on screen to go on to.
  await open(target, "signed-out");
  await password(target).fill("demo");
  await submit(target).click();
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(target.locator(".docs-frame")).toBeFocused();
});

test("a calendar put away with no documentation behind it leaves the keyboard on the rail", async ({
  page: target,
}) => {
  await open(target, "error");
  await expect(target.locator(".sign-in")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".docs-frame")).toHaveCount(0);
  await target.keyboard.press("ControlOrMeta+Shift+D");
  await expect(
    target.getByRole("region", { name: label("desktop.calendar.title") }),
  ).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+D");
  await expect(target.locator(".calendar-page")).toHaveCount(0);
  // The rail hands focus given to it on to its own tab stop.
  await expect(target.locator(".rail :focus")).toHaveCount(1);
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

test("carrying on in the TUI, the calendar looks at the account again", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target
    .locator(".sign-in")
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(tui(target)).toBeFocused();
  const before = await calls(target, "signInStatus")();
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  // The window does not know how the TUI's sign-in went: it says so,
  // looks once on opening, and offers to look again.
  await expect(page).toContainText(label("desktop.account.in_tui"));
  await expect.poll(calls(target, "signInStatus")).toBe(before + 1);
  // Once: time enough for another passes, and there is none.
  await target.waitForTimeout(600);
  expect(await calls(target, "signInStatus")()).toBe(before + 1);
  const again = page.getByRole("button", {
    name: label("desktop.calendar.refresh"),
  });
  await again.click();
  // The button that asked keeps the keyboard while the account is read.
  await expect(again).toBeFocused();
  await expect.poll(calls(target, "signInStatus")).toBe(before + 2);
  await expect(again).not.toHaveAttribute("aria-busy");
  expect(await calendarReads(target)()).toBe(0);
});

test("signing out from a terminal leaves the keyboard on the way back in", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await expect(tui(target)).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+k");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.account.sign_out"));
  await target.keyboard.press("Enter");
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeFocused();
  // Signing out here is not a reason to ask for the password again.
  await expect(target.locator(".sign-in")).toHaveCount(0);
});

test("what is not known of the messages is said, never shown as none unread", async ({
  page: target,
}) => {
  // Never captured: not known to be none.
  await open(target, "empty");
  await expect(messagesButton(target)).toHaveAccessibleName(
    named("desktop.messages.never"),
  );
  await expect(messagesButton(target).locator("[data-slot=badge]")).toHaveCount(
    0,
  );
  // A hollow pin stands where a count would be: not a zero.
  await expect(messagesButton(target).locator("[data-pin]")).toHaveAttribute(
    "data-pin",
    "unknown",
  );
  // A read that failed says so, with its code.
  await open(target, "views-refused");
  await expect(messagesButton(target)).toHaveAccessibleName(
    named("desktop.messages.failed", { code: "timed_out" }),
  );
  await expect(messagesButton(target).locator("[data-pin]")).toHaveAttribute(
    "data-pin",
    "failed",
  );
  // The tooltip says what the name says.
  await messagesButton(target).hover();
  await expect(target.getByRole("tooltip")).toContainText("timed_out");
});

test("messages are read again when the window is returned to, at most once a minute", async ({
  page: target,
}) => {
  await target.clock.install();
  await open(target, "signed-in");
  await expect.poll(calls(target, "notifications")).toBe(1);
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  await target.clock.runFor(1000);
  expect(await calls(target, "notifications")()).toBe(1);
  await target.clock.runFor(61_000);
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(calls(target, "notifications")).toBe(2);
});

test("the palette opens the calendar, and choosing it again keeps it open", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  for (let round = 0; round < 2; round++) {
    await target
      .getByRole("button", { name: label("desktop.rail.search") })
      .click();
    const palette = target.locator(".palette");
    await palette.getByRole("combobox").fill(label("desktop.calendar.title"));
    await target.keyboard.press("Enter");
    await expect(palette).toHaveCount(0);
    await expect(page).toBeFocused();
  }
});

test("the AEAT shortcut opens the agency's site in the system browser", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await target
    .getByRole("button", { name: label("desktop.rail.aeat") })
    .click();
  await expect
    .poll(() =>
      target.evaluate(() =>
        (window.__scenarioHostCalls ?? []).filter((call) =>
          call.startsWith("openExternal "),
        ),
      ),
    )
    .toEqual(["openExternal https://sede.agenciatributaria.gob.es"]);
});

test("a shortcut the host cannot open says so", async ({ page: target }) => {
  await open(target, "error");
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.aeat") })
    .click();
  await expect(
    target.getByText(label("desktop.toast.open_failed")),
  ).toBeVisible();
});
