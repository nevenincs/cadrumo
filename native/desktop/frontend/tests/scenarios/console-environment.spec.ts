import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { open, startFromDocs } from "../support/scenarioShell";

// The console carries the signed-in profile's environment: when the host
// reports that it changed, an idle console starts again at once and a
// running one asks to be restarted. The notice's words come from the
// generated chrome catalogue; where it does not hold a key yet, label()
// answers the key itself, so the notice is found by its slot and role.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const hostCalls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

const callsOf = async (target: Page, prefix: string) =>
  (await hostCalls(target)).filter((call) => call.startsWith(prefix)).length;

/** The terminal calls made from now on, in order, without their sizes. */
const terminalCallsSince = async (target: Page, from: number) =>
  (await hostCalls(target))
    .slice(from)
    .filter(
      (call) =>
        call.startsWith("openTerminal ") || call.startsWith("terminalClose "),
    )
    .map((call) => call.split(" ").slice(0, 2).join(" "));

const emit = (target: Page, payload: unknown) =>
  target.evaluate((value) => {
    window.__scenarioConsoleEnvironment?.emit(value);
  }, payload);

const notice = (target: Page) =>
  target.locator('[data-slot="console-environment-notice"][role="status"]');

const restartDoor = (target: Page) =>
  notice(target).getByRole("button", {
    name: label("desktop.session.restart_console"),
    exact: true,
  });

const consoleRows = (target: Page) =>
  target.locator('[data-terminal="console"] .xterm-rows');

const consoleTab = (target: Page) =>
  target.getByRole("tab", { name: label("desktop.rail.console"), exact: true });

/** Ends the console's process from inside it, as the person would. */
const exitConsole = async (target: Page) => {
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  await target.keyboard.type("exit");
  await target.keyboard.press("Enter");
  await expect
    .poll(
      async () =>
        (await consoleTab(target).getAttribute("aria-description")) ?? "",
    )
    .toContain(label("desktop.session.exited", { code: 0 }));
};

const subscribed = (target: Page) =>
  expect.poll(() => callsOf(target, "observeConsoleEnvironment")).toBe(1);

test("an idle console is closed and opened again once, and the new session is shown", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
  await subscribed(target);
  await exitConsole(target);
  const from = (await hostCalls(target)).length;
  await emit(target, { revision: "rev-1" });
  await expect
    .poll(() => terminalCallsSince(target, from))
    .toEqual(["terminalClose console", "openTerminal console"]);
  // The new session is the one shown: its prompt takes input again.
  await expect
    .poll(
      async () =>
        (await consoleTab(target).getAttribute("aria-description")) ?? "",
    )
    .not.toContain(label("desktop.session.exited", { code: 0 }));
  await expect(consoleRows(target)).not.toContainText(
    label("desktop.session.exit_line", { code: 0 }),
  );
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  await target.keyboard.type("echo relaunched");
  await target.keyboard.press("Enter");
  await expect(consoleRows(target)).toContainText("relaunched");
  await expect(notice(target)).toHaveCount(0);
});

test("a running console is never closed for a change: it asks for a restart, and the door restarts it", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
  await subscribed(target);
  const from = (await hostCalls(target)).length;
  await emit(target, { revision: "rev-1" });
  await expect(notice(target)).toBeVisible();
  await expect(notice(target)).toContainText(
    label("desktop.session.environment_changed"),
  );
  // Nothing was closed or opened: the running process is the person's.
  expect(await terminalCallsSince(target, from)).toEqual([]);
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  await target.keyboard.type("echo still here");
  await target.keyboard.press("Enter");
  await expect(consoleRows(target)).toContainText("still here");
  expect(await terminalCallsSince(target, from)).toEqual([]);

  await restartDoor(target).click();
  await expect
    .poll(() => terminalCallsSince(target, from))
    .toEqual(["terminalClose console", "openTerminal console"]);
  await expect(notice(target)).toHaveCount(0);
  await expect(consoleRows(target)).not.toContainText("still here");
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
});

test("the same revision again does nothing more, and a malformed payload is refused", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
  await subscribed(target);
  await exitConsole(target);
  const from = (await hostCalls(target)).length;
  await emit(target, { revision: "rev-1" });
  await expect
    .poll(() => terminalCallsSince(target, from))
    .toEqual(["terminalClose console", "openTerminal console"]);
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
  await emit(target, { revision: "rev-1" });
  // Neither a payload with more than the revision, nor one without it,
  // nor a revision that is not a token reaches the window.
  await emit(target, { revision: "rev-2", environment: { HOME: "x" } });
  await emit(target, { revision: "" });
  await emit(target, { revision: 2 });
  await emit(target, "rev-2");
  await emit(target, null);
  await expect(notice(target)).toHaveCount(0);
  expect(await terminalCallsSince(target, from)).toEqual([
    "terminalClose console",
    "openTerminal console",
  ]);
  // A running console with the same revision again asks only once.
  await emit(target, { revision: "rev-3" });
  await expect(notice(target)).toHaveCount(1);
  await emit(target, { revision: "rev-3" });
  await expect(notice(target)).toHaveCount(1);
  expect(await terminalCallsSince(target, from)).toEqual([
    "terminalClose console",
    "openTerminal console",
  ]);
});

test("the Python and TUI terminals are left alone, idle or running", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await expect(consoleRows(target)).toContainText("PS C:\\Users\\demo>");
  await subscribed(target);
  await showTui(target);
  await expect(
    target.locator('[data-terminal="tui"] .xterm-rows'),
  ).toContainText("Simulated TUI session");
  await target
    .getByRole("tab", { name: label("desktop.rail.python"), exact: true })
    .click();
  const python = target.locator('[data-terminal="python"] .xterm-rows');
  await expect(python).toContainText(">>>");
  await target.locator('[data-terminal="python"] .xterm-screen').click();
  await target.keyboard.type("exit()");
  await target.keyboard.press("Enter");
  await expect(python).toContainText(
    label("desktop.session.exit_line", { code: 0 }),
  );
  const from = (await hostCalls(target)).length;
  await emit(target, { revision: "rev-1" });
  // The console is running: it asks, and nothing else moves.
  await expect(notice(target)).toHaveCount(1);
  await target.waitForTimeout(200);
  expect(await terminalCallsSince(target, from)).toEqual([]);
  await expect(python).toContainText(
    label("desktop.session.exit_line", { code: 0 }),
  );
});
