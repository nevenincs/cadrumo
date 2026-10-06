import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The profile a person signs in to: shown, chosen and created in the
// window, on the scenario host. Presentation evidence only: the profiles
// are made up and nothing here reaches a product or a runtime.

const open = (target: Page, scenario: string) =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const dialog = (target: Page) => target.locator(".sign-in");

const password = (target: Page) => target.locator("#profile-password");

const submit = (target: Page) =>
  dialog(target).getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });

const choice = (target: Page) =>
  dialog(target).getByLabel(label("desktop.signin.profile"), { exact: true });

const form = (target: Page) => dialog(target).locator(".create-profile");

const nameField = (target: Page) =>
  form(target).getByLabel(label("desktop.account.create.name"), {
    exact: true,
  });

const newPassword = (target: Page) =>
  form(target).getByLabel(label("desktop.signin.password"), { exact: true });

const repeated = (target: Page) =>
  form(target).getByLabel(label("desktop.account.create.confirm"), {
    exact: true,
  });

const createButton = (target: Page) =>
  form(target).getByRole("button", {
    name: label("desktop.account.create.submit"),
    exact: true,
  });

/** The host calls made so far whose line starts with `call`. */
const calls = (target: Page, call: string) => () =>
  target.evaluate(
    (name) =>
      (
        window as unknown as { __scenarioHostCalls?: string[] }
      ).__scenarioHostCalls?.filter(
        (made) => made === name || made.startsWith(`${name} `),
      ).length ?? 0,
    call,
  );

const everyCall = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __scenarioHostCalls?: string[] })
        .__scenarioHostCalls ?? [],
  );

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("several profiles: the profile is a labelled choice with the selected one chosen, and one submission signs in to it", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(choice(target)).toBeVisible();
  await expect(choice(target).locator("option:checked")).toHaveText(
    "Demo profile",
  );
  await expect(choice(target).locator("option")).toHaveCount(3);
  // The keyboard starts in the password, not in the choice.
  await expect(password(target)).toBeFocused();
  await password(target).fill("anything");
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
  expect(await everyCall(target)).toContain("signInProfile 1");
});

test("another profile chosen is the one signed in to, and the one the window then names", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await choice(target).selectOption({ label: "Ana Soler Vidal" });
  await password(target).fill("anything");
  await password(target).press("Enter");
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
  const made = await everyCall(target);
  expect(made).toContain("signInProfile 2");
  expect(made).not.toContain("signInProfile 1");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = target.locator(".settings");
  await expect(
    settings.getByRole("region", { name: label("desktop.signin.profile") }),
  ).toContainText("Ana Soler Vidal");
  // Using another profile is said where the sign-out is.
  await expect(settings.locator(".switch-hint")).toHaveText(
    label("desktop.account.switch_hint"),
  );
});

test("several profiles and none selected: no password is sent until a profile is chosen", async ({
  page: target,
}) => {
  await open(target, "choose-profile");
  await expect(choice(target)).toBeVisible();
  await expect(choice(target)).toHaveValue("");
  await password(target).fill("anything");
  await password(target).press("Enter");
  // Nothing was sent: the choice is asked for, and the password is kept.
  await expect(choice(target)).toBeFocused();
  await expect(choice(target)).toHaveAttribute("aria-invalid", "true");
  await expect(dialog(target).locator("[data-slot=field-error]")).toHaveText(
    label("desktop.signin.choose_profile"),
  );
  await expect(password(target)).toHaveValue("anything");
  expect(await calls(target, "signIn")()).toBe(0);

  await choice(target).selectOption({ label: "Taller Ribera, S.L." });
  await expect(choice(target)).not.toHaveAttribute("aria-invalid", "true");
  await expect(dialog(target).locator("[data-slot=field-error]")).toHaveCount(
    0,
  );
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("one profile: it is named under its own label, with nothing to choose", async ({
  page: target,
}) => {
  await open(target, "one-profile");
  const named = dialog(target).getByRole("group", {
    name: label("desktop.signin.profile"),
  });
  await expect(named).toContainText("Demo profile");
  await expect(named.locator("[data-slot=label]")).toBeVisible();
  await expect(dialog(target).locator("select")).toHaveCount(0);
  await expect(password(target)).toBeFocused();
});

test("profiles that cannot be read: it is said, and the password goes to the profile the status names", async ({
  page: target,
}) => {
  await open(target, "profiles-unreadable");
  await expect(dialog(target)).toContainText(
    label("desktop.signin.profiles_unread"),
  );
  await expect(
    dialog(target).getByRole("group", {
      name: label("desktop.signin.profile"),
    }),
  ).toContainText("Demo profile");
  await password(target).fill("anything");
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
  // No profile was named: the product's selected one is signed in to.
  expect(await calls(target, "signInProfile")()).toBe(0);
});

test("first run: the dialog is the form that creates a profile, and nothing is sent while something is wrong", async ({
  page: target,
}) => {
  await open(target, "first-run");
  await expect(dialog(target)).toContainText(
    label("desktop.account.create.title"),
  );
  await expect(nameField(target)).toBeFocused();
  await expect(dialog(target).locator("#profile-password")).toHaveCount(0);
  // Nothing to go back to: there is no profile to sign in to.
  await expect(
    form(target).getByRole("button", {
      name: label("desktop.account.create.back"),
    }),
  ).toHaveCount(0);

  await createButton(target).click();
  await expect(nameField(target)).toBeFocused();
  await expect(nameField(target)).toHaveAttribute("aria-invalid", "true");
  await expect(form(target)).toContainText(
    label("desktop.account.create.name_missing"),
  );

  await nameField(target).fill("Marta Ruiz Ferrer");
  await newPassword(target).fill("short");
  await repeated(target).fill("short");
  await repeated(target).press("Enter");
  await expect(newPassword(target)).toBeFocused();
  await expect(form(target)).toContainText(
    label("desktop.account.create.password_short", { min: 8 }),
  );

  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct house");
  await repeated(target).press("Enter");
  await expect(repeated(target)).toBeFocused();
  await expect(form(target)).toContainText(
    label("desktop.account.create.mismatch"),
  );
  // What was typed is kept for the person to correct.
  await expect(newPassword(target)).toHaveValue("correct horse");
  expect(await calls(target, "createProfile")()).toBe(0);
});

test("first run: one submission creates the profile, and only its password then signs in", async ({
  page: target,
}) => {
  await open(target, "first-run");
  await nameField(target).fill("  Marta Ruiz Ferrer ");
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await createButton(target).click();

  // Created and selected, and not signed in: the sign-in form for it.
  await expect(password(target)).toBeFocused();
  await expect(password(target)).toHaveValue("");
  await expect(dialog(target).getByRole("status")).toHaveText(
    label("desktop.account.create.done", { name: "Marta Ruiz Ferrer" }),
  );
  await expect(
    dialog(target).getByRole("group", {
      name: label("desktop.signin.profile"),
    }),
  ).toContainText("Marta Ruiz Ferrer");
  await expect.poll(calls(target, "createProfile")).toBe(1);
  expect(await calls(target, "signIn")()).toBe(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);

  await password(target).fill("correct horse");
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect.poll(calls(target, "signIn")).toBe(1);
  expect(await calls(target, "createProfile")()).toBe(1);

  // Neither the name nor the password is in what the host was told.
  const made = (await everyCall(target)).join("\n");
  expect(made).not.toContain("Marta");
  expect(made).not.toContain("correct");
  expect(made).toContain("createProfile 17 characters");
});

test("a refused creation is said once, clears both passwords and is not tried again", async ({
  page: target,
}) => {
  await open(target, "create-refused");
  await nameField(target).fill("Marta Ruiz Ferrer");
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await repeated(target).press("Enter");

  await expect(form(target)).toContainText(
    label("desktop.account.create.name_taken"),
  );
  await expect(nameField(target)).toBeFocused();
  await expect(nameField(target)).toHaveValue("Marta Ruiz Ferrer");
  await expect(newPassword(target)).toHaveValue("");
  await expect(repeated(target)).toHaveValue("");
  await expect.poll(calls(target, "createProfile")).toBe(1);
  // Left alone, it stays one attempt.
  await target.waitForTimeout(300);
  expect(await calls(target, "createProfile")()).toBe(1);
  expect(await calls(target, "signIn")()).toBe(0);
});

test("a new profile is offered beside sign-in, refuses a name already in use, and gives the way back", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await dialog(target)
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(nameField(target)).toBeFocused();
  await expect(dialog(target).locator("#profile-password")).toHaveCount(0);

  // Another profile's name, in another case: said before anything is sent.
  await nameField(target).fill("demo PROFILE");
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await createButton(target).click();
  await expect(form(target)).toContainText(
    label("desktop.account.create.name_taken"),
  );
  expect(await calls(target, "createProfile")()).toBe(0);

  await form(target)
    .getByRole("button", { name: label("desktop.account.create.back") })
    .click();
  await expect(password(target)).toBeFocused();
  await expect(choice(target).locator("option:checked")).toHaveText(
    "Demo profile",
  );

  // Put aside and opened again, the dialog is the sign-in, not the form.
  await dialog(target)
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(nameField(target)).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(dialog(target)).toHaveCount(0);
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(password(target)).toBeFocused();
  await expect(form(target)).toHaveCount(0);
});

test("a profile created beside others is the one then chosen for sign-in", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await dialog(target)
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await nameField(target).fill("Marta Ruiz Ferrer");
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await createButton(target).click();
  await expect(password(target)).toBeFocused();
  await expect(choice(target).locator("option")).toHaveCount(4);
  await expect(choice(target).locator("option:checked")).toHaveText(
    "Marta Ruiz Ferrer",
  );
  await password(target).fill("correct horse");
  await submit(target).click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  expect(await everyCall(target)).toContain("signInProfile 4");
});

test("first run: the pane, settings and the palette all lead to the form in the window", async ({
  page: target,
}) => {
  await open(target, "first-run");
  await target.keyboard.press("Escape");
  await expect(dialog(target)).toHaveCount(0);

  const pane = target.locator(".pane-tui");
  await expect(pane).toContainText(label("desktop.account.first_run_lead"));
  await pane
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(nameField(target)).toBeFocused();
  await target.keyboard.press("Escape");

  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .locator(".settings")
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(target.locator(".settings")).toHaveCount(0);
  await expect(nameField(target)).toBeFocused();
  await target.keyboard.press("Escape");

  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox")
    .fill(label("desktop.account.new_profile"));
  await palette
    .getByRole("option", { name: label("desktop.account.new_profile") })
    .click();
  await expect(nameField(target)).toBeFocused();
  expect(await calls(target, "openTerminal tui")()).toBe(0);
});

test("signed out with profiles: the palette's new profile opens the form, not the sign-in", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox")
    .fill(label("desktop.account.new_profile"));
  await palette
    .getByRole("option", { name: label("desktop.account.new_profile") })
    .click();
  await expect(nameField(target)).toBeFocused();
  await expect(dialog(target)).toContainText(
    label("desktop.account.create.title"),
  );
});
