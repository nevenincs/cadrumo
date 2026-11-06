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

// The account states (no profile, locked, runtime unavailable, wrong password): every element of the window reads the same state.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

// Every element that says something about the account says the same thing:
// the TUI pane and its header, settings, and the actions the palette offers.
const ACCOUNT_STATES: {
  scenario: string;
  /** What the TUI pane's header and body say; null where the TUI runs. */
  saying: string | null;
  /** The header's session dot. */
  dot: string;
  badge: string;
  /** Buttons the pane and settings offer, and actions the palette lists. */
  offers: string[];
  withholds: string[];
}[] = [
  {
    scenario: "signed-out",
    saying: "desktop.account.signed_out",
    dot: "unavailable",
    badge: "desktop.account.signed_out",
    offers: ["desktop.signin.submit"],
    withholds: ["desktop.account.sign_out"],
  },
  {
    scenario: "signed-in",
    saying: null,
    dot: "running",
    badge: "desktop.account.signed_in",
    offers: ["desktop.account.sign_out"],
    withholds: ["desktop.signin.submit"],
  },
  {
    // A host that cannot make a profile has nothing to offer with none, and
    // does not send the person to the TUI to make one.
    scenario: "no-profile",
    saying: "desktop.account.no_profile",
    dot: "unavailable",
    badge: "desktop.account.signed_out",
    offers: [],
    withholds: ["desktop.signin.submit", "desktop.account.sign_out"],
  },
  {
    // A status that carries a refusal leaves the sign-in state unknown: the
    // runtime's presence can outlive this desktop's session. The refusal
    // says why the last try failed, and the way to try again stays beside it.
    scenario: "profile-locked",
    saying: "desktop.account.unknown",
    dot: "unavailable",
    badge: "desktop.account.unknown",
    offers: ["desktop.signin.submit"],
    withholds: ["desktop.account.sign_out"],
  },
  {
    scenario: "runtime-unavailable",
    saying: "desktop.account.services_down",
    dot: "unavailable",
    badge: "desktop.account.services_down",
    offers: [],
    withholds: ["desktop.signin.submit", "desktop.account.sign_out"],
  },
];

for (const state of ACCOUNT_STATES)
  test(`${state.scenario}: every element reads the same account state`, async ({
    page: target,
  }) => {
    await open(target, state.scenario);
    // The dialog, where there is one, is put aside to look at the window.
    if (state.saying) {
      await expect(target.locator(".sign-in")).toBeVisible();
      await target.keyboard.press("Escape");
      await expect(target.locator(".sign-in")).toHaveCount(0);
    }
    await showTui(target);
    const pane = target.locator(".pane-tui");
    await expect(target.locator("#tab-tui [data-phase]")).toHaveAttribute(
      "data-phase",
      state.dot,
    );
    if (state.saying) {
      await expect(target.locator("#tab-tui")).toHaveAttribute(
        "aria-description",
        label(state.saying),
      );
      await expect(pane.locator("[data-slot=empty]")).toContainText(
        label(state.saying),
      );
    } else {
      await expect(pane.locator(".xterm")).toHaveCount(1);
    }
    for (const key of state.offers.filter(
      (offer) => offer !== "desktop.account.sign_out",
    ))
      await expect(
        pane.getByRole("button", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        pane.getByRole("button", { name: label(key), exact: true }),
      ).toHaveCount(0);
    // Where the account withholds the TUI, nothing in the gate offers it as
    // a way in.
    if (state.saying)
      await expect(
        pane.locator("[data-slot=empty]").getByRole("button", { name: /TUI/ }),
      ).toHaveCount(0);

    // The calendar page says the same, or shows the calendar.
    const calendarToggle = target
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.calendar.title") });
    await calendarToggle.click();
    const calendarRegion = target.getByRole("region", {
      name: label("desktop.calendar.title"),
    });
    if (state.saying)
      await expect(calendarRegion).toContainText(label(state.saying));
    else
      await expect(calendarRegion.getByRole("listitem").first()).toBeVisible();
    for (const key of state.offers.filter(
      (offer) => offer !== "desktop.account.sign_out",
    ))
      await expect(
        calendarRegion.getByRole("button", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        calendarRegion.getByRole("button", { name: label(key), exact: true }),
      ).toHaveCount(0);
    if (state.saying)
      await expect(
        calendarRegion.getByRole("button", { name: /TUI/ }),
      ).toHaveCount(0);
    // Messages has a count only for a signed-in profile; otherwise it says
    // the same thing the panes say.
    const messages = target
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.rail.messages") });
    if (state.saying) {
      await expect(messages).toHaveAccessibleName(
        `${label("desktop.rail.messages")}, ${label(state.saying)}`,
      );
      await expect(messages.locator("[data-pin]")).toHaveCount(1);
    } else {
      await expect(messages.locator("[data-slot=badge]")).toHaveText("3");
    }
    await calendarToggle.click();
    await expect(calendarRegion).toHaveCount(0);

    // The header is the account surface; Settings has no account controls.
    await target
      .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
      .click();
    const accountMenu = target.locator(".account-menu");
    await expect(accountMenu).toContainText(
      label(
        state.scenario === "no-profile"
          ? "desktop.account.no_profile"
          : state.badge,
      ),
    );
    for (const key of state.offers)
      await expect(
        accountMenu.getByRole("menuitem", { name: label(key), exact: true }),
      ).toBeVisible();
    for (const key of state.withholds)
      await expect(
        accountMenu.getByRole("menuitem", { name: label(key), exact: true }),
      ).toHaveCount(0);
    await expect(
      accountMenu.getByRole("menuitem", { name: /TUI/ }),
    ).toHaveCount(0);
    await target.keyboard.press("Escape");

    // The palette lists the same actions, and no others of the account's.
    await target
      .getByRole("button", { name: label("desktop.rail.search") })
      .click();
    const palette = target.locator(".palette");
    for (const key of [...state.offers, ...state.withholds]) {
      await palette
        .getByRole("combobox", { name: label("desktop.palette.label") })
        .fill(label(key));
      const row = palette
        .locator(".palette-title")
        .filter({ hasText: new RegExp(`^${label(key)}$`) });
      await expect(row).toHaveCount(state.offers.includes(key) ? 1 : 0);
    }
  });

test("no-profile: the dialog says there is none, with no password field and no way to the TUI", async ({
  page: target,
}) => {
  await open(target, "no-profile");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(label("desktop.account.no_profile"));
  await expect(dialog).toContainText(label("desktop.account.no_profile_lead"));
  await expect(dialog).not.toContainText(/TUI/);
  await expect(password(target)).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /TUI/ })).toHaveCount(0);
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
  await expect.poll(calls(target, "signIn")).toBe(0);
});

// With no profile, and a host that cannot make one, no element sends the
// person to the TUI to set one up: the pane, the header and the palette say
// there is none and offer nothing else.
test("no-profile: the pane, the header and the palette do not offer to set a profile up in the TUI", async ({
  page: target,
}) => {
  await open(target, "no-profile");
  await expect(target.locator(".sign-in")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  const gate = target.locator(".pane-tui [data-slot=empty]");
  await expect(gate).toContainText(label("desktop.account.no_profile"));
  await expect(gate).toContainText(label("desktop.account.no_profile_lead"));
  await expect(gate.getByRole("button")).toHaveCount(0);
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  const menu = target.locator(".account-menu");
  await expect(menu).toContainText(label("desktop.account.no_profile"));
  // Nothing to set up or sign in to; the About entry is not a profile action.
  await expect(
    menu.getByRole("menuitem").filter({
      hasNotText: label("desktop.about.open"),
    }),
  ).toHaveCount(0);
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.locator(".palette");
  for (const key of ["desktop.account.new_profile", "desktop.signin.submit"]) {
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label(key));
    await expect(
      palette
        .locator(".palette-title")
        .filter({ hasText: new RegExp(`^${label(key)}$`) }),
    ).toHaveCount(0);
  }
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
});

test("profile-locked: the pane says why and still offers sign-in, never the TUI", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(password(target)).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await showTui(target);
  const pane = target.locator(".pane-tui");
  await expect(pane).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  const onward = pane.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  await expect(onward).toBeFocused();
  await expect(
    pane.locator("[data-slot=empty]").getByRole("button", { name: /TUI/ }),
  ).toHaveCount(0);
  await onward.click();
  await expect(password(target)).toBeFocused();
  await expect.poll(calls(target, "signIn")).toBe(0);
});

test("runtime-unavailable: the dialog and settings say what the window says", async ({
  page: target,
}) => {
  await open(target, "runtime-unavailable");
  const dialog = target.locator(".sign-in");
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.account.services_down"),
  );
  await expect(dialog).not.toContainText(label("desktop.signin.title"));
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  // With no runtime to ask, the profile is not known: it is not said to be
  // none, and no section stands empty for it.
  const settings = target.locator(".settings");
  await expect(
    settings.getByRole("region", { name: label("desktop.signin.profile") }),
  ).toHaveCount(0);
  await expect(settings).not.toContainText(label("desktop.account.no_profile"));
  await expect(
    settings.getByRole("region", { name: label("desktop.settings.window") }),
  ).toBeVisible();
});

test("wrong-password: a refusal that was seen is not shown again", async ({
  page: target,
}) => {
  await open(target, "wrong-password");
  await password(target).fill("not-the-password");
  await submit(target).click();
  const dialog = target.locator(".sign-in");
  await expect(dialog).toContainText(label("desktop.signin.refused.invalid"));
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await showTui(target);
  await target
    .locator(".pane-tui")
    .getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  await expect(password(target)).toBeFocused();
  await expect(dialog).not.toContainText(
    label("desktop.signin.refused.invalid"),
  );
});

test("throttled: a wait that is still running outlasts the dialog", async ({
  page: target,
}) => {
  await open(target, "throttled");
  await password(target).fill("anything");
  await submit(target).click();
  const dialog = target.locator(".sign-in");
  await expect(dialog.locator("button[type=submit]")).toBeDisabled();
  const left = async () =>
    Number(
      /\b(\d+)\b/.exec(
        (await dialog
          .locator('[data-slot=alert] span[aria-hidden="true"]')
          .textContent()) ?? "",
      )?.[1],
    );
  await expect.poll(left).toBeLessThan(30);
  const before = await left();
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await showTui(target);
  await target
    .locator(".pane-tui")
    .getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  await expect(dialog.locator("button[type=submit]")).toBeDisabled();
  // The same wait, further along: not a new thirty seconds.
  const after = await left();
  expect(after).toBeGreaterThan(0);
  expect(after).toBeLessThanOrEqual(before);
  await expect.poll(calls(target, "signIn")).toBe(1);
});

test("one Escape closes the dialog from a button showing its tooltip", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(password(target)).toBeFocused();
  // The reveal button follows the field; focused by keyboard, it shows its
  // tooltip, which is a layer above the dialog.
  await target.keyboard.press("Tab");
  await expect(target.getByRole("tooltip")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
});

test("sign-out-refused: the failure is said once, not again when the account menu reopens", async ({
  page: target,
}) => {
  await open(target, "sign-out-refused");
  const settingsButton = target.getByRole("button", {
    name: label("desktop.titlebar.profile_menu"),
  });
  await settingsButton.click();
  const settings = target.locator(".account-menu");
  await settings
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(settings.getByRole("alert")).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await settingsButton.click();
  await expect(settings).toBeVisible();
  await expect(settings.getByRole("alert")).toHaveCount(0);
  // A click outside dismisses the menu and the failure it has shown.
  await settings
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(settings.getByRole("alert")).toBeVisible();
  await target.mouse.click(8, 200);
  await expect(settings).toHaveCount(0);
  await settingsButton.click();
  await expect(settings).toBeVisible();
  await expect(settings.getByRole("alert")).toHaveCount(0);
});

test("signing out leaves no running session showing in the TUI's header", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await showTui(target);
  const dot = target.locator("#tab-tui [data-phase]");
  await expect(dot).toHaveAttribute("data-phase", "running");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(dot).toHaveAttribute("data-phase", "unavailable");
  await expect(target.locator("#tab-tui")).toHaveAttribute(
    "aria-description",
    label("desktop.account.signed_out"),
  );
});

test("profile-locked: the dialog and the account menu say it and still offer sign-in", async ({
  page: target,
}) => {
  await open(target, "profile-locked");
  const dialog = target.locator(".sign-in");
  // Titled as a sign-in: a locked profile is signed in to like any other.
  await expect(dialog.getByRole("heading")).toHaveText(
    label("desktop.signin.title"),
  );
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  const settings = target.locator(".account-menu");
  await expect(settings).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  await expect(settings.getByRole("menuitem", { name: /TUI/ })).toHaveCount(0);
  await settings
    .getByRole("menuitem", {
      name: label("desktop.signin.submit"),
      exact: true,
    })
    .click();
  await expect(settings).toHaveCount(0);
  await expect(password(target)).toBeFocused();
  await expect.poll(calls(target, "signIn")).toBe(0);
});
