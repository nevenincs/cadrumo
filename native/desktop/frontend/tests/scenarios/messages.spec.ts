import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  startFromDocs,
  open,
  password,
  submit,
  calls,
  tui,
} from "../support/scenarioShell";
import { messagesButton } from "../support/scenarioRail";

// The messages button: unread counts, opening the TUI, and the unknown and withheld states.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

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
    .locator('[data-dock-header="tui"]')
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
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.rail.messages"));
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
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .locator(".account-menu")
    .getByRole("menuitem", {
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
  // From the documentation's side of the window, with the TUI not opened.
  await expect(target.locator(".pane-tui")).toBeHidden();
  await messagesButton(target).click();
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeFocused();
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
  // A read that failed says so, without its code.
  await open(target, "views-refused");
  await expect(messagesButton(target)).toHaveAccessibleName(
    named("desktop.messages.failed"),
  );
  await expect(messagesButton(target).locator("[data-pin]")).toHaveAttribute(
    "data-pin",
    "failed",
  );
  // The tooltip says what the name says.
  await messagesButton(target).hover();
  await expect(target.getByRole("tooltip")).toContainText(
    label("desktop.messages.failed"),
  );
  await expect(target.getByRole("tooltip")).not.toContainText("timed_out");
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
