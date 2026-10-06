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

test("the password can be typed as soon as the status is known, before the profiles have been read", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-out&latency=1500&bar=off");
  // The status has answered and the list has not: the selected profile is
  // named, and its password field has the keyboard.
  await expect(password(target)).toBeFocused();
  await expect(dialog(target).locator("select")).toHaveCount(0);
  await expect(
    dialog(target).getByRole("group", {
      name: label("desktop.signin.profile"),
    }),
  ).toContainText("Demo profile");
  await password(target).pressSequentially("typed early");
  // The list arrives: the choice appears, and nothing typed is lost.
  await expect(choice(target).locator("option")).toHaveCount(3);
  await expect(choice(target).locator("option:checked")).toHaveText(
    "Demo profile",
  );
  await expect(password(target)).toBeFocused();
  await expect(password(target)).toHaveValue("typed early");
});

test("with no profile selected the window waits for the list before it says there is none", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=choose-profile&latency=1200&bar=off",
  );
  // Not the form that creates a profile, shown and then taken away.
  await expect(target.locator(".pane-tui")).toContainText(
    label("desktop.signin.checking"),
  );
  await expect(form(target)).toHaveCount(0);
  await expect(choice(target).locator("option:not([disabled])")).toHaveCount(3);
  await expect(form(target)).toHaveCount(0);
});

test("signed in, the window does not read the profiles it has no use for", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(calls(target, "signInStatus")).toBeGreaterThan(1);
  expect(await calls(target, "profiles")()).toBe(0);
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

for (const from of ["settings", "palette"] as const)
  test(`switching profile from ${from} signs out once and goes on to the choice of another`, async ({
    page: target,
  }) => {
    await open(target, "signed-in");
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    if (from === "settings") {
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .click();
      await target
        .locator(".settings")
        .getByRole("button", { name: label("desktop.account.switch_profile") })
        .click();
    } else {
      await target
        .getByRole("button", { name: label("desktop.rail.search") })
        .click();
      const palette = target.locator(".palette");
      await palette
        .getByRole("combobox")
        .fill(label("desktop.account.switch_profile"));
      await palette
        .getByRole("option", { name: label("desktop.account.switch_profile") })
        .click();
    }
    // Signed out, and asked: the sign-in, with its choice, over the window.
    await expect(password(target)).toBeFocused();
    await expect(target.locator(".settings")).toHaveCount(0);
    await expect(choice(target).locator("option:checked")).toHaveText(
      "Demo profile",
    );
    expect(await calls(target, "signOut")()).toBe(1);

    await choice(target).selectOption({ label: "Taller Ribera, S.L." });
    await password(target).fill("anything");
    await submit(target).click();
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    expect(await everyCall(target)).toContain("signInProfile 3");
    expect(await calls(target, "signOut")()).toBe(1);
    expect(await calls(target, "signIn")()).toBe(1);
  });

test("a switch whose sign-out fails says so where it was asked, and asks for no password", async ({
  page: target,
}) => {
  await open(target, "sign-out-refused");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = target.locator(".settings");
  await settings
    .getByRole("button", { name: label("desktop.account.switch_profile") })
    .click();
  await expect(settings.getByRole("alert")).toBeVisible();
  await expect(dialog(target)).toHaveCount(0);
  await expect(
    settings.getByRole("button", { name: label("desktop.account.sign_out") }),
  ).toBeVisible();
  expect(await calls(target, "signOut")()).toBe(1);
  expect(await calls(target, "signIn")()).toBe(0);
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

test("while a profile is being created the form says how long it takes, and nothing can be sent twice", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=first-run&latency=1500&bar=off");
  await nameField(target).fill("Marta Ruiz Ferrer");
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await repeated(target).press("Enter");
  // Pending: the wait is said, and the fields hold without being disabled.
  await expect(form(target).locator(".create-wait")).toHaveText(
    label("desktop.account.create.wait"),
  );
  await expect(nameField(target)).toHaveAttribute("readonly", "");
  await expect(newPassword(target)).toHaveValue("");
  await form(target).locator("button[type=submit]").click({ force: true });
  await nameField(target).press("Enter");
  await expect(password(target)).toBeFocused({ timeout: 10000 });
  expect(await calls(target, "createProfile")()).toBe(1);
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

// The longest a label may be, in words and as one unbroken run: every
// control of the surfaces that show it stays inside them.
for (const [kind, long] of [
  [
    "of many words",
    "Explotaciones Agropecuarias y Ganaderas del Valle Medio del Guadalquivir, Sociedad Cooperativa Andaluza de Segundo Grado y Compañía"
      .padEnd(160, " y Compañía")
      .slice(0, 160)
      .trim(),
  ],
  ["of one unbroken run", "Contribuyente".repeat(12).slice(0, 150)],
] as const)
  for (const size of [
    { width: 1280, height: 800 },
    { width: 640, height: 450 },
  ])
    test(`a very long profile name ${kind} keeps every control inside its surface (${size.width}x${size.height})`, async ({
      page: target,
    }) => {
      await target.setViewportSize(size);
      await open(target, "signed-out");
      const inside = (surface: string) =>
        target.evaluate((selector) => {
          const frame = document.querySelector(selector);
          if (!frame) return [`no ${selector}`];
          const box = frame.getBoundingClientRect();
          const out: string[] = [];
          if (box.left < 0 || box.right > innerWidth)
            out.push(`${selector} leaves the window`);
          for (const control of frame.querySelectorAll(
            "button, input, select, [role=radio]",
          )) {
            if (!(control as HTMLElement).offsetParent) continue;
            const at = control.getBoundingClientRect();
            if (at.width === 0) continue;
            if (at.left < box.left - 1 || at.right > box.right + 1)
              out.push(
                `${(control.getAttribute("aria-label") ?? control.textContent ?? control.tagName).trim().slice(0, 24)}: ${Math.round(at.left)}-${Math.round(at.right)} outside ${Math.round(box.left)}-${Math.round(box.right)}`,
              );
          }
          return out;
        }, surface);

      await dialog(target)
        .getByRole("button", { name: label("desktop.account.new_profile") })
        .click();
      await nameField(target).fill(long);
      await newPassword(target).fill("correct horse");
      await repeated(target).fill("correct horse");
      await repeated(target).press("Enter");
      await expect(password(target)).toBeFocused();
      // Created: said in the notice and chosen in the choice, both inside.
      await expect(dialog(target).getByRole("status")).toContainText(
        long.slice(0, 40),
      );
      expect(await inside(".sign-in")).toEqual([]);

      await password(target).fill("correct horse");
      await submit(target).click();
      await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .click();
      const settings = target.locator(".settings");
      // The name is cut, with the whole of it as its title; signing out
      // and switching are where they can be pressed.
      await expect(settings.locator(`[title="${long}"]`)).toBeVisible();
      await expect(
        settings.getByRole("button", {
          name: label("desktop.account.sign_out"),
        }),
      ).toBeInViewport({ ratio: 1 });
      await expect(
        settings.getByRole("button", {
          name: label("desktop.account.switch_profile"),
        }),
      ).toBeInViewport({ ratio: 1 });
      expect(await inside(".settings")).toEqual([]);
    });

test("one control shows both passwords of the form, and the keyboard meets each stop once", async ({
  page: target,
}) => {
  await open(target, "first-run");
  const show = form(target).getByRole("button", {
    name: label("desktop.signin.show_password"),
  });
  await expect(show).toHaveCount(1);
  await newPassword(target).fill("correct horse");
  await repeated(target).fill("correct horse");
  await expect(newPassword(target)).toHaveAttribute("type", "password");
  await expect(repeated(target)).toHaveAttribute("type", "password");
  await show.click();
  await expect(newPassword(target)).toHaveAttribute("type", "text");
  await expect(repeated(target)).toHaveAttribute("type", "text");
  await form(target)
    .getByRole("button", { name: label("desktop.signin.hide_password") })
    .click();
  await expect(repeated(target)).toHaveAttribute("type", "password");

  // From the name, Tab by Tab: no two stops of the dialog share a name.
  await nameField(target).focus();
  const stops: string[] = [];
  for (let press = 0; press < 12; press++) {
    await target.keyboard.press("Tab");
    const stop = await target.evaluate(() => {
      const held = document.activeElement as HTMLElement;
      const named = held.id
        ? document.querySelector(`label[for="${held.id}"]`)?.textContent
        : null;
      return `${held.tagName}:${(held.getAttribute("aria-label") ?? named ?? held.textContent ?? "").trim()}`;
    });
    if (
      stops.includes(stop) ||
      stop.endsWith(label("desktop.account.create.name"))
    )
      break;
    stops.push(stop);
  }
  expect(stops).toHaveLength(5);
  expect(new Set(stops).size).toBe(stops.length);
});

test("in forced colours the form's main action is still drawn as a button", async ({
  page: target,
}) => {
  await target.emulateMedia({ forcedColors: "active" });
  for (const scenario of ["first-run", "signed-out"]) {
    await open(target, scenario);
    const action = dialog(target).locator("button[type=submit]");
    await expect(action).toBeVisible();
    const edge = await action.evaluate((button) => {
      const style = getComputedStyle(button);
      return {
        width: parseFloat(style.borderTopWidth),
        style: style.borderTopStyle,
      };
    });
    expect(edge.width, scenario).toBeGreaterThanOrEqual(1);
    expect(edge.style, scenario).toBe("solid");
  }
});
