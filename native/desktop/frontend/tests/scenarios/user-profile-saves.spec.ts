import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { PROFILE_SURNAMES } from "../support/profileFixture";
import { SCENARIO_PASSWORD } from "../../src/dev/fixtures/password";
import {
  open,
  editButton,
  save,
  profileAction,
  goToSection,
} from "../support/userProfilePage";

// How the profile page saves: external changes, conflicts, repeatable entries, refusals and uncertain saves.

test("external changes refresh once, preserve drafts and block stale saves", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Unsaved draft");
  await page.evaluate(() =>
    window.__scenarioProfile!.update("Changed by the agent"),
  );
  await expect(profile).toContainText("Changed by the agent");
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Unsaved draft",
  );
  await expect(save(dialog)).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.burst());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 2);
});

test("a server conflict refreshes the profile without discarding the draft or retrying", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Keep this draft");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.conflict());
  await save(dialog).click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Keep this draft",
  );
  await expect(save(dialog)).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("repeatable entries can be updated and removed with confirmation", async ({
  page,
}) => {
  const profile = await open(page);
  await goToSection(page, "Business activities");
  const activities = profile.getByRole("region", {
    name: "Business activities",
  });
  await expect(activities).toContainText(label("desktop.profile.entries_none"));
  await activities
    .getByRole("button", { name: label("desktop.profile.add"), exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Business activities",
    exact: true,
  });
  const description = dialog.getByRole("textbox", {
    name: "Activity description",
    exact: true,
  });
  await description.fill("First Partner");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await activities
    .getByRole("button", {
      name: label("desktop.profile.action.edit_entry"),
      exact: true,
    })
    .click();
  await expect(description).toHaveValue("First Partner");
  await description.fill("Updated Partner");
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(activities).toContainText("Updated Partner");
  const remove = activities.getByRole("button", {
    name: label("desktop.profile.remove"),
    exact: true,
  });
  await remove.click();
  await expect(dialog).toContainText(label("desktop.profile.remove_help"));
  await dialog
    .getByRole("button", { name: label("desktop.profile.cancel"), exact: true })
    .last()
    .click();
  await expect(activities).toContainText("Updated Partner");
  // Delete on a focused entry asks the same question.
  await activities.locator("[data-kind='row']").focus();
  await page.keyboard.press("Delete");
  await dialog
    .getByRole("button", { name: label("desktop.profile.remove"), exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(activities).not.toContainText("Updated Partner");
  await expect(activities).toContainText(label("desktop.profile.entries_none"));
});

test("a refused save keeps the draft without claiming success", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Keep my draft");
  await page.evaluate(() => window.__scenarioProfile!.refuse());
  await save(dialog).click();
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.profile.refused"),
  );
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Keep my draft",
  );
});

test("uncertain saves require an explicit refresh before retrying", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog
    .getByLabel("Given name", { exact: true })
    .fill("Recovered draft");
  await page.evaluate(() => window.__scenarioProfile!.uncertain());
  await save(dialog).click();
  await expect(dialog.getByRole("alert")).toContainText(
    label("desktop.profile.unknown"),
  );
  await expect(save(dialog)).toBeDisabled();
  await dialog
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await expect(save(dialog)).toBeEnabled();
  await expect(dialog.getByLabel("Given name", { exact: true })).toHaveValue(
    "Recovered draft",
  );
  await save(dialog).click();
  await expect(dialog).toHaveCount(0);
  await expect(profile).toContainText("Recovered draft");
});

test("signing out hides private data even when an old read completes later", async ({
  page,
}) => {
  const profile = await open(page);
  // The account picker may retain its public profile label after sign-out;
  // use a distinct private field value to detect disclosure from an old read.
  const privateName = "Private taxpayer detail";
  await page.evaluate(
    (name) => window.__scenarioProfile!.update(name),
    privateName,
  );
  await expect(profile).toContainText(privateName);
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await profileAction(page, "desktop.profile.action.refresh");
  await page
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await page
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toHaveCount(0);
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(page.getByText(privateName, { exact: true })).toHaveCount(0);
});

test("the password changes only with the current one, and an unconfirmed change is not retried", async ({
  page,
}) => {
  await open(page);
  await profileAction(page, "desktop.profile.password.title");
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.password.title"),
    exact: true,
  });
  const fill = async (current: string, next: string, again = next) => {
    await dialog
      .getByLabel(label("desktop.profile.password.current"), { exact: true })
      .fill(current);
    await dialog
      .getByLabel(label("desktop.profile.password.new"), { exact: true })
      .fill(next);
    await dialog
      .getByLabel(label("desktop.profile.password.again"), { exact: true })
      .fill(again);
    await dialog
      .getByRole("button", {
        name: label("desktop.profile.password.title"),
        exact: true,
      })
      .click();
  };
  const changes = () =>
    page.evaluate(() => window.__scenarioPassword!.changes());
  await fill(SCENARIO_PASSWORD, "a new password", "another password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.account.create.mismatch"),
  );
  await fill(SCENARIO_PASSWORD, "short");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.account.create.password_short", { min: 8 }),
  );
  expect(await changes()).toBe(0);
  await fill("not the password", "a new password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.profile.password.rejected"),
  );
  // Nothing typed is kept once it has been sent.
  await expect(
    dialog.getByLabel(label("desktop.profile.password.current"), {
      exact: true,
    }),
  ).toHaveValue("");
  await fill(SCENARIO_PASSWORD, "a new password");
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByRole("status")
      .getByText(label("desktop.profile.password.changed")),
  ).toBeVisible();
  expect(await changes()).toBe(2);
  await page.evaluate(() => window.__scenarioPassword!.uncertain());
  await profileAction(page, "desktop.profile.password.title");
  await fill(SCENARIO_PASSWORD, "a newer password");
  await expect(dialog.getByRole("alert")).toHaveText(
    label("desktop.profile.password.unknown"),
  );
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.password.title"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await changes()).toBe(3);
});

test("a save waits for a pending refresh and submits the unchanged draft once", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  await dialog.getByLabel("Given name", { exact: true }).fill("Queued draft");
  await page.evaluate(() => {
    window.__scenarioProfile!.deferRead();
    window.__scenarioProfile!.burst();
  });
  await expect(profile).toContainText(label("desktop.profile.loading"));
  await save(dialog).click();
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.saving"),
      exact: true,
    }),
  ).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(dialog).toHaveCount(0);
  await expect(profile).toContainText("Queued draft");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
});

test("a committed save stays busy through readback and coalesced observations", async ({
  page,
}) => {
  const profile = await open(page);
  await editButton(profile, "Given name").click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  const input = dialog.getByLabel("Given name", { exact: true });
  await input.fill("Saved after readback");
  const before = await page.evaluate(() => window.__scenarioProfile!.reads());
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await save(dialog).click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 1);
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.saving"),
      exact: true,
    }),
  ).toBeDisabled();
  await expect(input).toBeDisabled();
  await expect(
    dialog.getByRole("button", {
      name: label("desktop.profile.cancel"),
      exact: true,
    }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  // Even an additional form submission cannot replay the committed edit.
  await dialog.locator("form").evaluate((form) => {
    if (form instanceof HTMLFormElement) form.requestSubmit();
  });
  await page.evaluate(() => window.__scenarioProfile!.burst());
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  expect(await page.evaluate(() => window.__scenarioProfile!.reads())).toBe(
    before + 1,
  );
  await page.evaluate(() => {
    window.__scenarioProfile!.releaseRead();
    window.__scenarioProfile!.deferRead();
  });
  await expect
    .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
    .toBe(before + 2);
  await expect(input).toBeDisabled();
  await expect(dialog).toBeVisible();
  await page.evaluate(() => window.__scenarioProfile!.releaseRead());
  await expect(dialog).toHaveCount(0);
  await expect(profile.locator("header")).toContainText("Saved after readback");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await editButton(profile, "Given name").click();
  await expect(input).toBeEnabled();
});

for (const code of [
  "unavailable",
  "refused",
  "not_signed_in",
  "unknown",
  "conflict",
] as const)
  test(`a committed save with ${code} readback unlocks and refreshes without replay`, async ({
    page,
  }) => {
    const profile = await open(page);
    await editButton(profile, "Given name").click();
    const dialog = page.getByRole("dialog", {
      name: "Given name",
      exact: true,
    });
    await dialog
      .getByLabel("Given name", { exact: true })
      .fill("Already saved");
    const before = await page.evaluate(() => window.__scenarioProfile!.reads());
    await page.evaluate(() => window.__scenarioProfile!.deferRead());
    await save(dialog).click();
    await expect
      .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
      .toBe(before + 1);
    await expect(
      dialog.getByRole("button", {
        name: label("desktop.profile.saving"),
        exact: true,
      }),
    ).toBeDisabled();
    await page.evaluate(
      (failure) => window.__scenarioProfile!.rejectRead(failure),
      code,
    );
    await expect(dialog).toHaveCount(0);
    await expect(profile.getByRole("alert")).toContainText(
      label("desktop.profile.saved_unread"),
    );
    await expect(profile).not.toContainText(label("desktop.profile.loading"));
    expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(
      1,
    );
    const refresh = profile.getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    });
    await expect(refresh).toBeEnabled();
    await refresh.click();
    await expect
      .poll(() => page.evaluate(() => window.__scenarioProfile!.reads()))
      .toBe(before + 2);
    await expect(profile.locator("header")).toContainText("Already saved");
    await expect(profile.getByRole("alert")).toHaveCount(0);
    expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(
      1,
    );
  });

test("a failed pending profile read leaves loading and allows a retry", async ({
  page,
}) => {
  const profile = await open(page);
  await page.evaluate(() => window.__scenarioProfile!.deferRead());
  await profileAction(page, "desktop.profile.action.refresh");
  await expect(profile).toContainText(label("desktop.profile.loading"));
  await page.evaluate(() => window.__scenarioProfile!.rejectRead());
  await expect(profile.getByRole("alert")).toContainText(
    label("desktop.profile.unavailable"),
  );
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
  await expect(profile).toContainText(PROFILE_SURNAMES);
  const refresh = profile.getByRole("button", {
    name: label("desktop.profile.refresh"),
    exact: true,
  });
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await expect(profile).toContainText(PROFILE_SURNAMES);
  await expect(profile.getByRole("alert")).toHaveCount(0);
  await expect(profile).not.toContainText(label("desktop.profile.loading"));
});
