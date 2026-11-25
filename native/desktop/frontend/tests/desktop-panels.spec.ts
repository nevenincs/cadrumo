import { expect, test } from "@playwright/test";
import { seedLayout } from "./support/layout";
import { openLogFilters, openPanelTab, panelToggle } from "./support/panel";
import { label } from "./support/strings";
import { revealTui, signInHost, signInState } from "./support/desktopShell";

test.beforeEach(async ({ page: target }) => {
  // Start each test from the default layout, once: a reload inside a test must
  // still see what that test stored.
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("a fresh layout keeps the TUI closed after sign-in", async ({ page }) => {
  await signInHost(page);
  // Nothing arranged yet: every choice is the default.
  await page.evaluate(() => localStorage.setItem("cadrumo-shell-layout", "{}"));
  await page.reload();
  await page.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "" },
    ),
  );
  await page
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret");
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(page.getByLabel(label("desktop.signin.password"))).toHaveCount(
    0,
  );
  await expect(page.locator(".pane-tui")).toBeHidden();
  // A count of none cannot be waited for; the saved-layout case below goes
  // through the same sign-in and sees this count reach one.
  expect((await signInState(page)).tuiStarts).toBe(0);
});

test("a saved open and maximized TUI comes back as saved, once signed in", async ({
  page,
}) => {
  await seedLayout(page, {
    prefs: { fontSize: "large" },
    layout: {
      page: "docs",
      tuiShown: true,
      maximized: "tui",
      splitRatio: 0.7,
      agentRatio: 0.3,
    },
  });
  await signInHost(page);
  // Signed out, the account withholds the TUI's session: nothing starts.
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  expect((await signInState(page)).tuiStarts).toBe(0);
  await expect(page.locator(".pane-tui .xterm")).toHaveCount(0);
  await page.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "" },
    ),
  );
  await page
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret");
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(page.getByLabel(label("desktop.signin.password"))).toHaveCount(
    0,
  );
  // Signed in, the saved arrangement stands: the TUI is open, maximized and
  // started once, and nothing saved was rewritten.
  await expect.poll(async () => (await signInState(page)).tuiStarts).toBe(1);
  await expect(page.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(page.locator(".pane-tui")).toBeVisible();
  await expect(page.locator(".pane-docs")).toBeHidden();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = JSON.parse(localStorage.getItem("cadrumo-shell-layout")!);
        return [
          state.layout.tuiShown,
          state.layout.maximized,
          state.layout.splitRatio,
          state.layout.agentRatio,
          state.prefs.fontSize,
        ];
      }),
    )
    .toEqual([true, "tui", 0.7, 0.3, "large"]);
  // Hiding and showing it again keeps the one session.
  await revealTui(page);
  await revealTui(page);
  expect((await signInState(page)).tuiStarts).toBe(1);
});

test("terminal cursor replies survive output arriving before session opening completes", async ({
  page,
}) => {
  await signInHost(page);
  await page.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      {
        submitCode: "",
        deferTui: true,
      },
    );
  });
  await page
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await page
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(page.getByLabel(label("desktop.signin.password"))).toHaveCount(
    0,
  );
  expect((await signInState(page)).tuiStarts).toBe(0);
  await revealTui(page);
  await expect.poll(async () => (await signInState(page)).tuiStarts).toBe(1);
  // Let xterm consume the cursor query while the host still holds the open reply.
  await page.evaluate(async () => {
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    (
      window as unknown as { __signInTest: { releaseTui: () => void } }
    ).__signInTest.releaseTui();
  });
  await expect
    .poll(async () => (await signInState(page)).terminalWrites)
    .toEqual(["\u001b[1;1R"]);
});

for (const [severity, value] of [
  ["DEBUG", "0"],
  ["INFO", "1"],
  ["ERROR", "3"],
] as const) {
  test(`the log view starts and resets at the host's ${severity} level`, async ({
    page,
  }) => {
    await signInHost(page, false, false, false, true, severity);
    await page.keyboard.press("ControlOrMeta+Shift+KeyL");
    await openLogFilters(page);
    const selector = page.getByLabel(label("desktop.logs.minimum_level"));
    await expect(selector).toHaveValue(value);
    await selector.selectOption("2");
    await page.keyboard.press("Escape");
    await page.keyboard.press("ControlOrMeta+Shift+KeyK");
    await page.locator("[cmdk-input]").fill(label("desktop.action.logs_reset"));
    await page
      .locator("[cmdk-item]")
      .filter({ hasText: label("desktop.action.logs_reset") })
      .click();
    await openLogFilters(page);
    await expect(selector).toHaveValue(value);
  });
}

test("a package without documentation says so and keeps every terminal working", async ({
  page: target,
}) => {
  await signInHost(target, true, false, false, false);
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.docs.not_bundled"),
  );
  await expect(target.locator(".pane-docs")).not.toContainText(
    /built|compiled|Everything else works/,
  );
  await target.keyboard.press("Escape");
  await expect(target.locator(".pane-tui")).toContainText(
    "Sign in to open your workspace.",
  );
  await expect(target.locator(".pane-tui")).not.toContainText(
    /\blocked\b|\bTUI\b/,
  );
  await expect(target.locator(".docs-frame")).toHaveCount(0);
  await target.keyboard.press("Escape");
  for (const kind of ["console", "python"] as const) {
    await openPanelTab(target, kind);
    await expect(
      target.locator(`[data-terminal="${kind}"]`).locator("textarea"),
    ).toBeFocused();
  }
  expect((await signInState(target)).terminalStarts).toEqual([
    "console",
    "python",
  ]);
});

test("optional terminals start on first opening and survive hiding and switching", async ({
  page: target,
}) => {
  await signInHost(target);
  await expect(target.locator(".sign-in")).toBeVisible();
  expect((await signInState(target)).terminalStarts).toEqual([]);
  await expect(target.locator("section.panel")).toBeHidden();
  await expect(target.locator(".xterm")).toHaveCount(0);
  await target.keyboard.press("Escape");
  for (const kind of ["console", "python"] as const) {
    await openPanelTab(target, kind);
    const pane = target.locator(`[data-terminal="${kind}"]`);
    await expect(pane.locator("textarea")).toBeFocused();
    await expect(pane.locator(".xterm")).toHaveCount(1);
    await pane.locator(".xterm").evaluate((element) => {
      element.setAttribute("data-session-marker", "retained");
    });
    await panelToggle(target).click();
    await expect(pane).toBeHidden();
    await expect(pane.locator("textarea")).not.toBeFocused();
  }
  for (const kind of ["console", "python"] as const) {
    await openPanelTab(target, kind);
    const pane = target.locator(`[data-terminal="${kind}"]`);
    await expect(pane.locator("textarea")).toBeFocused();
    await expect(pane.locator(".xterm")).toHaveAttribute(
      "data-session-marker",
      "retained",
    );
  }
  expect((await signInState(target)).terminalStarts).toEqual([
    "console",
    "python",
  ]);
  expect((await signInState(target)).terminalCloses).toBe(0);
});

test("a previously open panel restores its visibility and chosen tab", async ({
  page: target,
}) => {
  await target.addInitScript(() => {
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({ layout: { panelOpen: true, tab: "python" } }),
    );
  });
  await signInHost(target);
  await expect(target.locator(".sign-in")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator("section.panel")).toBeVisible();
  await expect
    .poll(async () => (await signInState(target)).terminalStarts)
    .toEqual(["python"]);
  await expect(target.locator('[data-terminal="console"] .xterm')).toHaveCount(
    0,
  );
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
});
