import { expect, test, type Page } from "@playwright/test";
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
  await expect(target.locator(".source-banner.state-missing")).toHaveText(
    label("desktop.logs.state_missing_detail"),
  );
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
        .filter((control) => !control.closest(".logview-list"))
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
  expect(
    await target
      .locator(".logview")
      .evaluate((view) => view.scrollHeight - view.clientHeight),
  ).toBeLessThanOrEqual(1);
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
  await target.waitForTimeout(500);
  await expect(list).toBeFocused();
  await expect(follow).toHaveAttribute("aria-pressed", "true");
  // An arrow key goes on to the record Tab would reach.
  await target.keyboard.press("ArrowUp");
  await expect(list.locator(".record:focus")).toHaveCount(1);
});

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
  for (let notch = 0; notch < 40; notch++) await target.mouse.wheel(0, -2);
  await expect(follow).toHaveAttribute("aria-pressed", "false");
  // And the view stays where the wheel left it while records arrive.
  const gap = () =>
    list.evaluate(
      (element) =>
        element.scrollHeight - element.scrollTop - element.clientHeight,
    );
  const before = await gap();
  await target.waitForTimeout(600);
  expect(await gap()).toBeGreaterThan(before);
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
    await target.keyboard.press("End");
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    await expect(list.locator(".record")).toHaveCount(400);
    await expect(list.locator(".record:focus")).toHaveCount(1);
  }
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
  // Far more arrives than the span may hold.
  await target.waitForTimeout(4000);
  const drawn = await list.locator(".record").count();
  expect(drawn).toBeLessThanOrEqual(2000);
  expect(drawn).toBeGreaterThan(400);
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

test("the filing calendar is a page of the first pane, read when it is shown", async ({
  page: target,
}) => {
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
  // The obligations, by month, each with the product's own reading.
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(4);
  await expect(
    page.getByRole("listitem").filter({ hasText: "2026-3T" }),
  ).toHaveCount(4);
  const late = page
    .getByRole("listitem")
    .filter({ hasText: "2026-2T" })
    .first();
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
      ([kind, count]) => `${label(`desktop.calendar.state.${kind}`)}${count}`,
    ),
  );
  // How far each is: lateness in the product's own days, a near date in
  // days, a far one in months.
  const said = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  await expect(late).toContainText(said.format(-78, "day"));
  await expect(
    page.getByRole("listitem").filter({ hasText: "2026-3T" }).last(),
  ).toContainText(said.format(14, "day"));
  await expect(
    page.getByRole("listitem").filter({ hasText: "2026-4T" }),
  ).toContainText(said.format(4, "month"));
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
  // Settled first: the refusals so far have each had the account read.
  await expect
    .poll(async () => {
      const count = await calls(target, "signInStatus")();
      await target.waitForTimeout(150);
      return count === (await calls(target, "signInStatus")()) ? count : -1;
    })
    .toBeGreaterThan(0);
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
  // saved a quarter of a second after a change, so it is given that long.
  await target.keyboard.press("ControlOrMeta+=");
  await target.waitForTimeout(500);
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

test("the dialog's way to the TUI takes the keyboard there, wherever it was opened from", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await calendarButton(target).click();
  await target
    .getByRole("region", { name: label("desktop.calendar.title") })
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await target
    .locator(".sign-in")
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(tui(target)).toBeFocused();
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
  await page
    .getByRole("button", { name: label("desktop.calendar.refresh") })
    .click();
  await expect.poll(calls(target, "signInStatus")).toBe(before + 2);
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
