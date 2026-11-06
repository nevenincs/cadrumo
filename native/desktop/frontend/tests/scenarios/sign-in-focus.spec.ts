import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import {
  startFromDocs,
  open,
  password,
  submit,
  calls,
  tui,
} from "../support/scenarioShell";
import { errorsHeld } from "../support/scenarioLogView";
import { calendarButton } from "../support/scenarioRail";

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
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

for (const origin of [
  "start",
  "pane",
  "calendar",
  "palette",
  "header",
] as const)
  test(`the dialog opened from the ${origin} holds the keyboard in the password field and offers no way to the TUI`, async ({
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
      await showTui(target);
      await target.locator(".pane-tui").getByRole("button", signIn).click();
    } else if (origin === "calendar") {
      await calendarButton(target).click();
      await target
        .getByRole("region", { name: label("desktop.calendar.title") })
        .getByRole("button", signIn)
        .click();
    } else if (origin === "palette") {
      await target
        .getByRole("button", {
          name: label("desktop.rail.settings"),
          exact: true,
        })
        .focus();
      await target.keyboard.press("ControlOrMeta+k");
      await target
        .locator(".palette")
        .getByRole("combobox", { name: label("desktop.palette.label") })
        .fill(label("desktop.signin.submit"));
      await target.keyboard.press("Enter");
    } else if (origin === "header") {
      await target
        .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
        .click();
      await target
        .locator(".account-menu")
        .getByRole("menuitem", signIn)
        .click();
    }
    await expect(password(target)).toBeFocused();
    await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
  });

test("admitted after the dialog was put aside, the keyboard goes to the TUI", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-out&latency=1200");
  // The TUI is opened first, so it is there to start once admitted.
  await expect(password(target)).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await showTui(target);
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await password(target).fill("demo");
  await target.keyboard.press("Enter");
  // Put aside while the answer is on its way.
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(tui(target)).toBeFocused();
});

// How many times the TUI was asked for: a gated window starts none.
const tuiStarts = (target: Page) => () =>
  target.evaluate(
    () =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter((made) =>
        made.startsWith("openTerminal tui"),
      ).length ?? 0,
  );

test("tui-unavailable: signed out, sign-in is the only way on and no TUI is asked for", async ({
  page: target,
}) => {
  // Records keep arriving, so the shell is drawn again and again while a
  // wish for focus could still be granted.
  await open(target, "tui-unavailable", "&feed=200");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  await target.keyboard.press("Escape");
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toContainText(label("desktop.account.signed_out"));
  await expect(page.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeVisible();
  // Shown while nobody is signed in, the TUI pane offers the sign-in and
  // starts nothing.
  await showTui(target);
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeVisible();
  expect(await tuiStarts(target)()).toBe(0);
});

test("tui-unavailable: the dialog keeps the keyboard while the account is read again", async ({
  page: target,
}) => {
  await open(target, "tui-unavailable");
  await expect(password(target)).toBeFocused();
  // With the shell drawn again inside the moment in which a focus wished for
  // the TUI could be granted: each return to the window has the account read
  // again, and each answer draws the shell.
  const asked = calls(target, "signInStatus");
  const before = await asked();
  for (let draw = 0; draw < 4; draw++) {
    await target.evaluate(() => window.dispatchEvent(new Event("focus")));
    await target.waitForTimeout(330);
  }
  expect(await asked()).toBeGreaterThan(before + 2);
  await expect(password(target)).toBeFocused();
  expect(await tuiStarts(target)()).toBe(0);
});

test("signing in from the calendar keeps the keyboard in the calendar, with the TUI beside it", async ({
  page: target,
}) => {
  await open(target, "signed-out", "&feed=200");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await showTui(target);
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
  // The TUI is on screen, its way in asked for, so it is there to start.
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await showTui(target);
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  // The dialog is a moment in leaving; the chord is pressed in that moment,
  // by the page itself the instant the dialog starts to go.
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
  await seedLayout(target);
  // A launch never opens the TUI.
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

test("signing out from a terminal leaves the keyboard on the way back in", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await showTui(target);
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await expect(tui(target)).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+k");
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.account.sign_out"));
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
