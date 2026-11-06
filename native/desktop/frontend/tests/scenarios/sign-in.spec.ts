import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import {
  startFromDocs,
  open,
  password,
  submit,
  calls,
} from "../support/scenarioShell";

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
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
  await expect.poll(calls(target, "signIn")).toBe(1);
  // Signing in starts no terminal: the TUI starts when it is asked for.
  await expect(password(target)).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
  await showTui(target);
  await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
    "Simulated TUI session",
  );
});

test("signing in: the pending state stays up", async ({ page: target }) => {
  await open(target, "signing-in");
  await password(target).fill("anything");
  await submit(target).click();
  // Nothing is disabled while the answer is awaited, so focus stays put.
  await expect(password(target)).toHaveAttribute("readonly", "");
  await expect(
    target.getByRole("button", { name: label("desktop.signin.submitting") }),
  ).toHaveAttribute("aria-busy", "true");
  await target.keyboard.press("Tab");
  await expect(target.locator(".sign-in").locator(":focus")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("signed in: the TUI runs and the account can sign out", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await showTui(target);
  await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
    "Simulated TUI session",
  );
  await expect(password(target)).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(
    target.getByText(label("desktop.signin.signed_out_lead")),
  ).toBeVisible();
  await expect(password(target)).toHaveCount(0);
  await target.keyboard.press("Escape");
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(password(target)).toBeFocused();
});

// After signing out, signing in is offered by every element that offers it,
// and none of them sends the person to the TUI: sign-in is Cadrumo's and the
// runtime's, and the TUI cannot be operated by someone who is signed out.
for (const way of ["menu", "pane", "palette"] as const)
  test(`signing out, then signing in again from the ${way}: sign-in is offered everywhere and the TUI nowhere`, async ({
    page: target,
  }) => {
    await open(target, "signed-in");
    await showTui(target);
    await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
      "Simulated TUI session",
    );
    const profileMenu = target.getByRole("button", {
      name: label("desktop.titlebar.profile_menu"),
    });
    await profileMenu.click();
    await target
      .getByRole("menuitem", {
        name: label("desktop.account.sign_out"),
        exact: true,
      })
      .click();
    await expect.poll(calls(target, "signOut")).toBe(1);

    // The menu that signed out is still open, and offers sign-in.
    const menu = target.locator(".account-menu");
    const signIn = { name: label("desktop.signin.submit"), exact: true };
    await expect(menu.getByRole("menuitem", signIn)).toBeVisible();
    await expect(menu.getByRole("menuitem", { name: /TUI/ })).toHaveCount(0);
    await expect(
      menu.getByRole("menuitem", {
        name: label("desktop.account.sign_out"),
        exact: true,
      }),
    ).toHaveCount(0);
    if (way === "menu") {
      await menu.getByRole("menuitem", signIn).click();
    } else {
      await target.keyboard.press("Escape");
      await expect(menu).toHaveCount(0);
    }

    // Put aside or not, the dialog is there to be asked for, and the pane
    // behind it offers the same.
    const dialog = target.locator(".sign-in");
    if (way !== "menu") {
      await expect(dialog).toHaveCount(0);
      const pane = target.locator(".pane-tui");
      await expect(pane).toContainText(label("desktop.account.signed_out"));
      await expect(pane.getByRole("button", signIn)).toBeVisible();
      await expect(
        pane.locator("[data-slot=empty]").getByRole("button", { name: /TUI/ }),
      ).toHaveCount(0);
      if (way === "pane") {
        await pane.getByRole("button", signIn).click();
      } else {
        await target
          .getByRole("button", { name: label("desktop.rail.search") })
          .click();
        await target
          .locator(".palette")
          .getByRole("combobox", { name: label("desktop.palette.label") })
          .fill(label("desktop.signin.submit"));
        await target.keyboard.press("Enter");
      }
    }

    // The form is there, and no way to the TUI beside it.
    await expect(dialog).toBeVisible();
    await expect(password(target)).toBeFocused();
    await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
    await password(target).fill("anything");
    await submit(target).click();
    await expect.poll(calls(target, "signIn")).toBe(1);

    // Signed in again: the TUI is back, and so is the way to sign out.
    await expect(target.locator(".pane-tui .xterm-rows")).toContainText(
      "Simulated TUI session",
    );
    await expect(dialog).toHaveCount(0);
    await profileMenu.click();
    await expect(
      target.locator(".account-menu").getByRole("menuitem", {
        name: label("desktop.account.sign_out"),
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      target.locator(".account-menu").getByRole("menuitem", signIn),
    ).toHaveCount(0);
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
  // The status read that follows a refusal has settled and the field is
  // usable again: nothing else was sent.
  await expect(password(target)).toBeEnabled();
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("throttled: the wait is shown and submission is held", async ({
  page: target,
}) => {
  await open(target, "throttled");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(submit(target)).toBeDisabled();
  // The wait counts down from the host's thirty seconds.
  const shown = async () =>
    Number(
      /\b(\d+)\b/.exec(
        (await target.locator(".sign-in").textContent()) ?? "",
      )?.[1],
    );
  await expect.poll(shown).toBeGreaterThan(0);
  await expect.poll(shown).toBeLessThanOrEqual(30);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("profile locked: the refusal shows beside the form, which signs in as ever", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password(target)).toBeVisible();
  await expect(submit(target)).toBeEnabled();
  await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  await password(target).fill("anything");
  await submit(target).click();
  // This host refuses every try: the reason is said again and the form is
  // still there for the next.
  await expect.poll(calls(target, "signIn")).toBe(1);
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password(target)).toBeEnabled();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
});

test("runtime unavailable: said plainly, with submission disabled", async ({
  page: target,
}) => {
  await open(target, "runtime-unavailable");
  await expect(target.locator(".sign-in").getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(password(target)).toHaveCount(0);
  await expect(submit(target)).toHaveCount(0);
});

test("unsupported: no sign-in view, and the TUI starts", async ({
  page: target,
}) => {
  await open(target, "unsupported");
  await showTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(password(target)).toHaveCount(0);
});

test("sign-out refused: the sign-in stays and the failure shows", async ({
  page: target,
}) => {
  await open(target, "sign-out-refused");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect.poll(calls(target, "signOut")).toBe(1);
  const account = target.locator(".account-menu");
  await expect(account).toContainText(label("desktop.account.sign_out_failed"));
  await expect(account).not.toContainText("timed_out");
  await expect(
    account.getByText(label("desktop.account.signed_in"), { exact: true }),
  ).toBeVisible();
});
