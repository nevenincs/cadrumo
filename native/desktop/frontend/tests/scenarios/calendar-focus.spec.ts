import { expect, test } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import {
  startFromDocs,
  open,
  password,
  submit,
} from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("the documentation keeps its place under the calendar", async ({
  page: target,
}) => {
  await seedLayout(target);
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
  const head = target.locator('[data-dock-header="docs"]');
  await expect(
    head.getByRole("button", { name: label("desktop.dock.expand") }),
  ).toBeVisible();
  await expect(
    head.getByRole("button", { name: label("desktop.pane.maximize_docs") }),
  ).toHaveCount(0);
  await head.getByRole("button", { name: label("desktop.dock.close") }).click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.pane.docs"),
  );
});

test("the calendar's sign-in gets focus back when the dialog is put aside", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  // The TUI is not opened on launch, so its way back in is not on screen to
  // fall back to.
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
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.account.sign_out"));
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
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label(key));
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
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.action.zoom_reset"));
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
  await showTui(target);
  await calendarButton(target).click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toBeFocused();
  await target
    .locator('[data-dock-header="tui"]')
    .getByRole("button", { name: label("desktop.dock.expand") })
    .click();
  await expect(page).toBeHidden();
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await target.keyboard.press("ControlOrMeta+Shift+k");
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.calendar.title"));
  await target.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
});

test("putting the calendar away from the rail leaves the keyboard on the rail", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
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

for (const [beside, tuiShown] of [
  ["the rail", false],
  ["the TUI's way in", true],
] as const)
  test(`a calendar put away with no documentation behind it leaves the keyboard on ${beside}`, async ({
    page: target,
  }) => {
    // The calendar's pane goes with it: the keyboard goes to the next column
    // on screen with something to focus, else to the rail.
    await seedLayout(target, {
      layout: { agentShown: false, docsShown: false, page: "docs" },
    });
    await open(target, "error");
    await expect(target.locator(".sign-in")).toBeVisible();
    await target.keyboard.press("Escape");
    if (tuiShown) await showTui(target);
    await expect(target.locator(".docs-frame")).toHaveCount(0);
    await target.keyboard.press("ControlOrMeta+Shift+D");
    await expect(
      target.getByRole("region", { name: label("desktop.calendar.title") }),
    ).toBeFocused();
    await target.keyboard.press("ControlOrMeta+Shift+D");
    await expect(target.locator(".calendar-page")).toHaveCount(0);
    // The rail hands focus given to it on to its own tab stop.
    await expect(
      target.locator(tuiShown ? ".pane-tui :focus" : ".rail :focus"),
    ).toHaveCount(1);
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
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label("desktop.calendar.title"));
    await target.keyboard.press("Enter");
    await expect(palette).toHaveCount(0);
    await expect(page).toBeFocused();
  }
});
