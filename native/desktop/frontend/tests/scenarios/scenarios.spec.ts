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

// The call list sits in the collapsed scenario bar, so it is read by
// structure: a closed disclosure has no accessible content to query by role.
const calls = (target: Page, call: string) =>
  target
    .locator(".scenario-bar-calls li")
    .filter({ hasText: new RegExp(`^${call}$`) });

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
  await expect(calls(target, "signIn")).toHaveCount(1);
});

test("signing in: the pending state stays up", async ({ page: target }) => {
  await open(target, "signing-in");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(password(target)).toBeDisabled();
  await expect(
    target.getByRole("button", { name: label("desktop.signin.submitting") }),
  ).toBeDisabled();
  await expect(calls(target, "signIn")).toHaveCount(1);
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
  await expect(password(target)).toBeVisible();
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
  await target.waitForTimeout(500);
  await expect(calls(target, "signIn")).toHaveCount(1);
});

test("throttled: the wait is shown and submission is held", async ({
  page: target,
}) => {
  await open(target, "throttled");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(submit(target)).toBeDisabled();
  await expect(target.locator(".sign-in")).toContainText(/\b(30|29)\b/);
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
  await expect(submit(target)).toBeDisabled();
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
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.unavailable"),
  );
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

test("fixture records list every level and an unnamed source", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  await expect(target.locator(".record.level-critical")).toHaveCount(1);
  await expect(target.locator(".record.source-manager")).toHaveCount(1);
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
