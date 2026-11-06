import { expect, test } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open, tui } from "../support/scenarioShell";

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("session failure: the failure is written into the terminal and the tab says exited", async ({
  page: target,
}) => {
  await open(target, "session-failure");
  const rows = target.locator('[data-terminal="console"] .xterm-rows');
  await expect(rows).toContainText(
    label("desktop.session.failed", {
      reason: label("desktop.session.reason.output"),
    }),
  );
  await expect(rows).not.toContainText("read_failed");
  // A docked tab carries its session's state in its description.
  const tab = target.getByRole("tab", { name: label("desktop.rail.console") });
  await expect
    .poll(() => tab.getAttribute("aria-description"))
    .toContain(label("desktop.session.exited", { code: 1 }));
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
  const consoleTab = target.getByRole("tab", {
    name: label("desktop.rail.console"),
    exact: true,
  });
  const exited = label("desktop.session.exited", { code: 0 });
  await expect
    .poll(async () => (await consoleTab.getAttribute("aria-description")) ?? "")
    .toContain(exited);
  await target.keyboard.press("Enter");
  await expect
    .poll(async () => (await consoleTab.getAttribute("aria-description")) ?? "")
    .not.toContain(exited);
  await target.keyboard.type("echo restarted");
  await target.keyboard.press("Enter");
  await expect(rows).toContainText("restarted");
});

test("maximizing the bottom panel over the pane that holds the keyboard takes it into the panel", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await expect(target.locator(".docs-frame")).toBeVisible();
  await showTui(target);
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
      .getByRole("combobox", { name: label("desktop.palette.label") })
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
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label("desktop.pane.restore"));
    await target.keyboard.press("Enter");
    await expect(target.locator(".pane-tui")).toBeVisible();
  }
});

test("a narrow tab keeps the full session state accessible without repeating its title", async ({
  page: target,
}) => {
  await seedLayout(target);
  // At a narrow width the state belongs to the tab description and tooltip.
  await target.setViewportSize({ width: 640, height: 450 });
  await open(target, "signed-out", "&lang=hu");
  await expect(target.locator(".sign-in input[type=password]")).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await showTui(target, { lang: "hu" });
  const note = target.locator("#tab-tui");
  const whole = label("desktop.account.signed_out", {}, "hu");
  await expect(note).toHaveAttribute("aria-description", whole);
  await expect(note).toHaveText(label("desktop.pane.tui", {}, "hu"));
  await expect(note).toHaveAttribute(
    "title",
    `${label("desktop.pane.tui", {}, "hu")} · ${whole}`,
  );
  await expect(target.locator(".pane-tui .pane-title")).toHaveCount(0);
  await expect(
    target.locator(".pane-tui").getByText(whole, { exact: true }).last(),
  ).toBeInViewport();
});

test("hiding the TUI from inside it leaves the keyboard in the window", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await expect(target.locator(".docs-frame")).toBeVisible();
  await showTui(target);
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await expect(tui(target)).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+T");
  await expect(target.locator(".pane-tui")).toBeHidden();
  // The pane that is left takes it: not the document, where no key works.
  await expect(target.locator(".docs-frame")).toBeFocused();
});

test("the rail keeps its order: search, window toggles, shortcuts, panel toggle", async ({
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
  // The packaged run reaches search by its position. The window's columns
  // follow in the order they are laid out by default.
  expect(names.map((name) => name.split(",")[0])).toEqual(
    [
      "desktop.rail.search",
      "desktop.rail.agent",
      "desktop.rail.tui",
      "desktop.rail.docs",
      "desktop.profile.title",
      "desktop.aeat_sync.title",
      "desktop.ledger.title",
      "workspace.declarations.destination.overview",
      "desktop.calendar.title",
      "desktop.rail.messages",
      "desktop.browser.title",
      "desktop.rail.aeat",
      "desktop.panel.label",
    ].map((key) => label(key)),
  );
});
