import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The shell by keyboard alone: tab stops, arrow-key patterns, shortcuts, and
// where focus goes when a surface opens and closes.

const open = (target: Page, scenario = "signed-in") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const rail = (target: Page) =>
  target.getByRole("navigation", { name: label("desktop.rail.label") });

const focusedWithin = (area: Locator) => area.locator(":focus");

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the rail is one tab stop and the arrow keys move within it", async ({
  page: target,
}) => {
  await open(target);
  const buttons = rail(target).getByRole("button");
  await buttons.first().focus();
  await target.keyboard.press("ArrowDown");
  await expect(buttons.nth(1)).toBeFocused();
  await target.keyboard.press("End");
  await expect(buttons.last()).toBeFocused();
  await target.keyboard.press("Home");
  await expect(buttons.first()).toBeFocused();
  // One stop: Tab leaves the rail instead of walking its buttons.
  await target.keyboard.press("Tab");
  await expect(focusedWithin(rail(target))).toHaveCount(0);
});

test("a rail button names itself to a keyboard user", async ({
  page: target,
}) => {
  await open(target);
  await rail(target).getByRole("button").first().focus();
  await expect(target.getByRole("tooltip")).toContainText(
    label("desktop.rail.search"),
  );
});

test("the panel tabs follow the arrow keys and keep focus in the row", async ({
  page: target,
}) => {
  await open(target);
  const tab = (key: string) => target.getByRole("tab", { name: label(key) });
  await tab("desktop.rail.console").focus();
  await target.keyboard.press("ArrowRight");
  await expect(tab("desktop.rail.python")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(tab("desktop.rail.python")).toBeFocused();
  await expect(target.locator('[data-terminal="python"]')).toBeVisible();
  await target.keyboard.press("ArrowRight");
  await expect(tab("desktop.rail.logs")).toBeFocused();
  await expect(target.locator("#panel-logs")).toBeVisible();
  // Enter hands the keyboard to the chosen view.
  await target.keyboard.press("ArrowLeft");
  await expect(tab("desktop.rail.python")).toBeFocused();
  await target.keyboard.press("Enter");
  await expect(
    target.locator('[data-terminal="python"] textarea'),
  ).toBeFocused();
});

test("both splitters move by the arrow keys and report their position", async ({
  page: target,
}) => {
  await open(target);
  for (const [name, back] of [
    [label("desktop.split.resize"), "ArrowLeft"],
    [label("desktop.panel.resize"), "ArrowUp"],
  ] as const) {
    const handle = target.getByRole("separator", { name });
    await handle.focus();
    const before = Number(await handle.getAttribute("aria-valuenow"));
    await target.keyboard.press(back);
    await expect
      .poll(async () => Number(await handle.getAttribute("aria-valuenow")))
      .not.toBe(before);
    await expect(handle).toBeFocused();
  }
});

test("the palette opens by chord, runs by Enter and returns focus", async ({
  page: target,
}) => {
  await open(target);
  const opener = rail(target).getByRole("button").nth(1);
  await opener.focus();
  await target.keyboard.press("Control+KeyK");
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(palette.getByRole("combobox")).toBeFocused();
  // The arrow keys move the choice while focus stays in the input.
  const options = palette.getByRole("option");
  await expect(options.first()).toHaveAttribute("aria-selected", "true");
  await target.keyboard.press("ArrowDown");
  await expect(options.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(palette.getByRole("combobox")).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(palette).toBeHidden();
  await expect(opener).toBeFocused();
});

test("settings opens on the current choice, moves by arrows and returns focus", async ({
  page: target,
}) => {
  await open(target);
  const opener = rail(target).getByRole("button", {
    name: label("desktop.rail.settings"),
  });
  await opener.focus();
  await target.keyboard.press("Enter");
  const appearance = target.getByRole("radiogroup", {
    name: label("desktop.settings.appearance"),
  });
  await expect(
    appearance.getByRole("radio", {
      name: label("desktop.settings.follow_docs"),
    }),
  ).toBeFocused();
  // Held for a moment, as a person holds a key: the group checks the radio
  // that focus arrives on while the arrow is still down.
  await target.keyboard.press("ArrowRight", { delay: 60 });
  await expect(
    appearance.getByRole("radio", { name: label("desktop.settings.light") }),
  ).toHaveAttribute("aria-checked", "true");
  await target.keyboard.press("Escape");
  await expect(target.locator(".settings")).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("the shell's chords reach their actions from the chrome", async ({
  page: target,
}) => {
  await open(target);
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Shift+KeyT");
  await expect(target.locator(".pane-tui")).toBeHidden();
  await target.keyboard.press("Control+Shift+KeyT");
  await expect(target.locator(".pane-tui")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Backquote");
  await expect(target.locator("section.panel")).toBeHidden();
  await target.keyboard.press("Control+Shift+Digit3");
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  await target.keyboard.press("Control+Shift+KeyM");
  await expect(target.locator(".main-area")).toBeHidden();
  await target.keyboard.press("Control+Shift+KeyM");
  await expect(target.locator(".main-area")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Comma");
  await expect(target.locator(".settings")).toBeVisible();
});

test("a focused terminal keeps its own keys and yields only the global chords", async ({
  page: target,
}) => {
  await open(target);
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  // Ctrl+K belongs to the terminal: the palette stays closed.
  await target.keyboard.press("Control+KeyK");
  await expect(target.locator(".palette")).toHaveCount(0);
  await target.keyboard.press("Control+Shift+KeyK");
  await expect(target.locator(".palette")).toBeVisible();
});

test("the sign-in dialog keeps Tab inside it and Escape hands focus on", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const dialog = target.locator(".sign-in");
  await expect(target.locator("#profile-password")).toBeFocused();
  for (let press = 0; press < 8; press++) {
    await target.keyboard.press("Tab");
    await expect(focusedWithin(dialog)).toHaveCount(1);
  }
  for (let press = 0; press < 8; press++) {
    await target.keyboard.press("Shift+Tab");
    await expect(focusedWithin(dialog)).toHaveCount(1);
  }
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeFocused();
});

test("the reveal control shows and hides the password by keyboard", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const field = target.locator("#profile-password");
  await field.fill("a secret");
  await expect(field).toHaveAttribute("type", "password");
  await target
    .getByRole("button", { name: label("desktop.signin.show_password") })
    .press("Enter");
  await expect(field).toHaveAttribute("type", "text");
  await target
    .getByRole("button", { name: label("desktop.signin.hide_password") })
    .press("Space");
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).toHaveValue("a secret");
});

test("a log record's detail opens and closes by keyboard", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const toggle = target.getByRole("button", {
    name: label("desktop.logs.details"),
  });
  await toggle.focus();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await target.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(target.locator(".record pre")).toContainText("Traceback");
});

test("the menu stand-in follows the arrow keys and closes on Escape", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  await target.locator(".record").first().click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await expect(menu.getByRole("menuitem").first()).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(menu).toBeHidden();
});
