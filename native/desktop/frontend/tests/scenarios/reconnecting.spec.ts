import { expect, test } from "@playwright/test";
import { label } from "../support/strings";

// While the runtime keeps the window's session suspended after the profile's
// worker was lost, the person is not signed out. The window says it
// reconnects, and asks for the password only when the saved sign-in could not
// bring the session back.

const notice = '[data-slot="reconnecting"]';

test("a session waiting for the saved sign-in says it reconnects and signs nobody out", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=reconnecting&latency=0&bar=off");
  const reconnecting = page.locator(notice);
  await expect(reconnecting).toBeVisible();
  await expect(reconnecting).toContainText(
    label("desktop.account.reconnecting"),
  );
  await expect(reconnecting).toContainText(
    label("desktop.account.reconnecting_lead"),
  );
  // Nothing to type yet: the window presents the saved sign-in by itself.
  await expect(
    reconnecting.getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(page.locator(".sign-in")).toHaveCount(0);
  // The profile stays signed in: its menu still names it, and offers sign-out.
  await expect(page.locator(".titlebar .profile-name")).toBeVisible();
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).not.toContain("signOut");
  expect(calls).not.toContain("signIn");
});

test("a session that only the password can bring back opens the password form and returns by it", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=reconnecting-password&latency=0&bar=off",
  );
  const dialog = page.locator(".sign-in");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText(label("desktop.signin.reconnect_title"), { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByText(label("desktop.signin.reconnect_lead"), { exact: true }),
  ).toBeVisible();
  // It is not the form that signs in to another profile or makes one.
  await expect(dialog.getByRole("combobox")).toHaveCount(0);
  await expect(
    dialog.getByText(label("desktop.account.new_profile"), { exact: true }),
  ).toHaveCount(0);
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await expect(password).toBeFocused();
  await password.fill("anything");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(notice)).toHaveCount(0);
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => call === "signIn")).toHaveLength(1);
  expect(calls).not.toContain("signOut");
});

test("a refused password leaves the session waiting for another", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=reconnecting-wrong-password&latency=0&bar=off",
  );
  const dialog = page.locator(".sign-in");
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await password.fill("wrong");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(
    dialog.getByText(label("desktop.signin.refused.invalid"), { exact: true }),
  ).toBeVisible();
  await expect(password).toHaveValue("");
  await expect(page.locator(notice)).toBeVisible();
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).not.toContain("signOut");
});

test("a password form put aside is opened again from the notice", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=reconnecting-password&latency=0&bar=off",
  );
  const dialog = page.locator(".sign-in");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  const reconnecting = page.locator(notice);
  await expect(reconnecting).toBeVisible();
  await reconnecting
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(dialog).toBeVisible();
});
