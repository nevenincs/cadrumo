import { expect, test } from "@playwright/test";
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

test("throttling counts down and sign-in opens the TUI only on request", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "THROTTLED", retryAfterSeconds: 2 },
    ),
  );
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  const submit = target.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  await submit.click();
  await expect(submit).toBeDisabled();
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(submit).toBeEnabled({ timeout: 5000 });
  expect((await signInState(target)).submissions).toBe(1);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "", retryAfterSeconds: null },
    ),
  );
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await submit.click();
  await expect(target.getByLabel(label("desktop.signin.password"))).toHaveCount(
    0,
  );
  expect((await signInState(target)).tuiStarts).toBe(0);
  await revealTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  expect((await signInState(target)).tuiStarts).toBe(1);
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { deferStatus: true },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  expect((await signInState(target)).signOuts).toBe(0);
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus(),
  );
  // Signing out here leaves the signed-out pane; the dialog is not thrown
  // back at the person who has just chosen to sign out.
  await expect(
    target.getByText(label("desktop.signin.signed_out_lead")),
  ).toBeVisible();
  // The product kept the saved automation setting and reports that no issued
  // key can admit: the menu, still open on the sign-out, says nothing of
  // access that is not there.
  await expect(
    target
      .locator(".account-menu")
      .getByRole("menuitem", { name: label("desktop.signin.submit") }),
  ).toBeVisible();
  await expect(
    target.getByText(label("desktop.account.remaining_access")),
  ).toHaveCount(0);
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  await expect.poll(async () => (await signInState(target)).tuiCloses).toBe(1);
  await target.evaluate(async () => {
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus();
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
  });
  await target.keyboard.press("Escape");
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeFocused();
  expect((await signInState(target)).tuiStarts).toBe(1);
});

test("a locked profile is said beside the sign-in form, which stays available and never leads to the TUI", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      {
        refusal: { code: "PROFILE_LOCKED", retryAfterSeconds: null },
        submitCode: "PROFILE_LOCKED",
      },
    );
    window.dispatchEvent(new Event("focus"));
  });
  const dialog = target.locator(".sign-in");
  const gate = target.locator(".pane-tui [data-slot=empty]");
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  const submit = dialog.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  // Said in the dialog, with the form beside it and no way to the TUI.
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password).toBeVisible();
  await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  // Put aside, the pane behind it says the same, with the way to try again.
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await revealTui(target);
  await expect(gate).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  const again = gate.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  await expect(again).toBeVisible();
  await expect(gate.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  await again.click();
  await expect(password).toBeFocused();
  // A try is refused again, said again, and the form is still there.
  await password.fill("secret á漢");
  await submit.click();
  await expect
    .poll(async () => (await signInState(target)).submissions)
    .toBe(1);
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password).toBeEnabled();
  expect((await signInState(target)).tuiStarts).toBe(0);
  // The profile is unlocked in the host: the next try signs in.
  const reads = (await signInState(target)).statusReads as number;
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { refusal: null, submitCode: "" },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect
    .poll(async () => (await signInState(target)).statusReads)
    .toBeGreaterThan(reads);
  await password.fill("secret á漢");
  await submit.click();
  await expect(password).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  expect((await signInState(target)).tuiStarts).toBe(1);
  expect((await signInState(target)).submissions).toBe(2);
});

// A refusal is the reason the last try failed. Whatever its code, the dialog
// and the account menu still offer sign-in afterwards, and neither sends the
// person to the TUI to unlock, recover or sign in.
const REFUSALS = {
  PROFILE_LOCKED: label("desktop.signin.refused.profile_locked"),
  KEYRING_UNAVAILABLE: label("desktop.signin.refused.keyring_unavailable"),
  session_not_persisted: label("desktop.signin.refused.keyring_unavailable"),
  CREDENTIAL_REJECTED: label("desktop.signin.refused.invalid"),
  // The wait runs down, so only the words before it are fixed.
  THROTTLED:
    label("desktop.signin.refused.throttled").split("{seconds}")[0]?.trim() ??
    "",
} as const;

for (const [code, said] of Object.entries(REFUSALS))
  test(`${code}: said as the reason of the last try, with sign-in still offered and no way to the TUI`, async ({
    page: target,
  }) => {
    await signInHost(target);
    await target.evaluate((code) => {
      Object.assign(
        (window as unknown as { __signInTest: object }).__signInTest,
        {
          submitCode: code,
          retryAfterSeconds: code === "THROTTLED" ? 30 : null,
        },
      );
    }, code);
    const dialog = target.locator(".sign-in");
    const password = dialog.getByLabel(label("desktop.signin.password"), {
      exact: true,
    });
    const signIn = { name: label("desktop.signin.submit"), exact: true };
    await password.fill("secret á漢");
    await dialog.getByRole("button", signIn).click();
    await expect
      .poll(async () => (await signInState(target)).submissions)
      .toBe(1);
    // The reason is said, the form is still there, and the TUI is not offered.
    await expect(dialog).toContainText(said);
    await expect(password).toBeVisible();
    await expect(dialog.getByRole("button", signIn)).toBeVisible();
    await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);

    // Put aside, the account menu still offers sign-in, and not the TUI.
    await target.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await target
      .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
      .click();
    const menu = target.locator(".account-menu");
    await expect(menu.getByRole("menuitem", signIn)).toBeVisible();
    await expect(menu.getByRole("menuitem", { name: /TUI/ })).toHaveCount(0);
    // What outlasts the attempt is still said there.
    if (code !== "CREDENTIAL_REJECTED") await expect(menu).toContainText(said);

    // And it opens the form again.
    await menu.getByRole("menuitem", signIn).click();
    await expect(dialog).toBeVisible();
    await expect(password).toBeVisible();
    expect((await signInState(target)).tuiStarts).toBe(0);
  });

test("saved sign-in recovery requires a fresh password and names the selected profile", async ({
  page: target,
}) => {
  await signInHost(target, true, false, false, true, "INFO", [
    { name: "Test profile", active: true },
    { name: "Perfil á漢", active: false },
  ]);
  const dialog = target.locator(".sign-in");
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await dialog
    .getByLabel(label("desktop.signin.profile"), { exact: true })
    .selectOption({ label: "Perfil á漢" });
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      {
        submitCode: "session_not_persisted",
        deferSavedClear: true,
      },
    ),
  );
  await password.fill("secret á漢");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(dialog).toContainText(
    label("desktop.signin.refused.keyring_unavailable"),
  );
  const clear = dialog.getByRole("button", {
    name: label("desktop.signin.clear_saved"),
    exact: true,
  });
  await expect(clear).toBeVisible();
  await expect(dialog).toContainText(label("desktop.signin.clear_saved_lead"));
  await expect(password).toHaveValue("");
  await clear.click();
  expect((await signInState(target)).savedClearCalls).toBe(0);
  await password.fill("secret á漢");
  await clear.click();
  await expect
    .poll(async () => (await signInState(target)).savedClearCalls)
    .toBe(1);
  await expect(password).toHaveValue("");
  const pending = dialog
    .locator('button[type="button"]')
    .filter({ hasText: label("desktop.signin.clearing_saved") });
  await expect(pending).toBeDisabled();
  await pending.evaluate((button: HTMLButtonElement) => button.click());
  const inFlight = await signInState(target);
  expect(inFlight.savedClearCalls).toBe(1);
  expect(inFlight.savedClearRawPassword).toBe(true);
  expect(inFlight.savedClearToken).toBe(true);
  expect(inFlight.savedClearFieldEmpty).toBe(true);
  expect(inFlight.savedClearProfile).toBe(encodeURIComponent("Perfil á漢"));
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseSavedClear: () => void } }
    ).__signInTest.releaseSavedClear(),
  );
  await expect(dialog).toContainText(label("desktop.signin.saved_cleared"));
  await expect
    .poll(async () => (await signInState(target)).savedClearSecretWiped)
    .toBe(true);
  const completed = await signInState(target);
  expect(completed.submissions).toBe(1);
  expect(completed.tuiStarts).toBe(0);
  await expect(password).toHaveValue("");
});

test("saved sign-in recovery keeps a wrong-password refusal and permits retry", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      {
        submitCode: "session_not_persisted",
        savedClearError: "CREDENTIAL_REJECTED",
      },
    ),
  );
  const dialog = target.locator(".sign-in");
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await password.fill("secret á漢");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  const clear = dialog.getByRole("button", {
    name: label("desktop.signin.clear_saved"),
    exact: true,
  });
  await expect(clear).toBeVisible();
  await password.fill("secret á漢");
  await clear.click();
  await expect(dialog).toContainText(label("desktop.signin.refused.invalid"));
  await expect(dialog).not.toContainText(label("desktop.signin.saved_cleared"));
  await expect(password).toHaveValue("");
  await expect(clear).toBeVisible();
  await expect
    .poll(async () => (await signInState(target)).savedClearSecretWiped)
    .toBe(true);
  const result = await signInState(target);
  expect(result.savedClearCalls).toBe(1);
  expect(result.submissions).toBe(1);
  expect(result.tuiStarts).toBe(0);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { savedClearError: "", savedClearSecretWiped: false },
    ),
  );
  await password.fill("secret á漢");
  await clear.click();
  await expect(dialog).toContainText(label("desktop.signin.saved_cleared"));
  await expect
    .poll(async () => (await signInState(target)).savedClearSecretWiped)
    .toBe(true);
  expect((await signInState(target)).savedClearCalls).toBe(2);
  expect((await signInState(target)).submissions).toBe(1);
});

test("saved sign-in recovery never claims success with no profile", async ({
  page: target,
}) => {
  await signInHost(target, true, false, false, true, "INFO", []);
  await expect(target.locator(".sign-in")).not.toContainText(
    label("desktop.signin.saved_cleared"),
  );
  expect((await signInState(target)).savedClearCalls).toBe(0);
});

test("the end of the TUI's session reads the account again", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "" },
    ),
  );
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await target
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  expect((await signInState(target)).tuiStarts).toBe(0);
  await revealTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  const reads = (await signInState(target)).statusReads as number;
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { exitTui: () => void } }
    ).__signInTest.exitTui(),
  );
  await expect
    .poll(async () => (await signInState(target)).statusReads)
    .toBeGreaterThan(reads);
});

test("runtime-unavailable remains distinct from unknown presence", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { presence: "unknown", runtimeAvailable: false },
    );
    window.dispatchEvent(new Event("focus"));
  });
  // The dialog says it in the words the rest of the window uses, and does
  // not say the presence is merely unknown.
  const dialog = target.locator(".sign-in");
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(target.locator(".pane-tui")).toContainText(
    label("desktop.account.services_down"),
  );
  await expect(target.getByText(label("desktop.account.unknown"))).toHaveCount(
    0,
  );
  // With no runtime to ask, a password is not asked for.
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  expect((await signInState(target)).submissions).toBe(0);
  expect((await signInState(target)).tuiStarts).toBe(0);
});

test("unsupported platforms hide desktop sign-in and Account", async ({
  page: target,
}) => {
  await signInHost(target, false);
  await revealTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await expect(
    target.locator(".account-menu").getByRole("menuitem", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toHaveCount(0);
});

test("the desktop host reads the profile's calendar and message counts", async ({
  page: target,
}) => {
  await signInHost(target, false);
  await revealTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  const messages = target.locator('[data-rail="messages"]');
  await expect(messages).toBeVisible();
  // The count the host passes on, and nothing of the rows behind it.
  await expect(messages).toContainText("2");
  await target.locator('[data-rail="calendar"]').click();
  const page = target.locator(".calendar-page");
  await expect(page).toBeVisible();
  await expect(page).toContainText("303");
  const reads = (await signInState(target)).viewReads as Record<
    string,
    unknown
  >[];
  expect(reads.map((read) => read.command)).toContain(
    "profile_views_notifications",
  );
  const calendarRead = reads.find(
    (read) => read.command === "profile_views_calendar",
  );
  expect(calendarRead?.language).toBe("en");
  expect(calendarRead?.token).toBe("a".repeat(64));
  expect(String(calendarRead?.from)).toMatch(/^\d{4}-\d{2}-01$/);
  expect(String(calendarRead?.to)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});
