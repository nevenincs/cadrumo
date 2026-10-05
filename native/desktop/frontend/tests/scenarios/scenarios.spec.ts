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
  await expect(
    target.getByText(label("desktop.signin.refused.profile_locked")),
  ).toBeVisible();
  await target
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
  await expect(
    target.getByText(label("desktop.signin.refused.runtime_unavailable")),
  ).toBeVisible();
  await expect(password(target)).toHaveCount(0);
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
  await expect(
    target.getByText(label("desktop.signin.checking")),
  ).toBeVisible();
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
    name: label("desktop.account.title"),
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
