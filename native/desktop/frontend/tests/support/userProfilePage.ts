import { expect, type Locator, type Page } from "@playwright/test";
import { label } from "./strings";
import { PROFILE_SURNAMES } from "./profileFixture";

// The profile page as a person reaches and works it in the scenario window.

export async function open(
  page: Page,
  scenario = "user-profile",
  language = "en",
) {
  await page.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off&lang=${language}`,
  );
  await page
    .locator(".rail")
    .getByRole("button", {
      name: label("desktop.profile.title", {}, language),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText(
    PROFILE_SURNAMES,
  );
  return page.locator(".user-profile-page");
}

export const band = (page: Page) =>
  page.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });

export const row = (profile: Locator, path: string) =>
  profile.locator(`[data-nav="${path}"]`);

export const editButton = (profile: Locator, field: string) =>
  profile.getByRole("button", {
    name: label("desktop.profile.edit_field", { field }),
    exact: true,
  });

export const save = (dialog: Locator) =>
  dialog.getByRole("button", {
    name: label("desktop.profile.save"),
    exact: true,
  });

export const aeatEditor = (page: Page) =>
  page.getByRole("dialog", {
    name: label("desktop.profile.action.aeat_access"),
    exact: true,
  });

/** Chooses an item of the profile's actions menu. */
export async function profileAction(page: Page, key: string) {
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.action.menu"),
      exact: true,
    })
    .click();
  await page.getByRole("menuitem", { name: label(key), exact: true }).click();
}

export async function goToSection(page: Page, title: string) {
  await page
    .locator(".user-profile-page")
    .getByRole("button", {
      name: label("desktop.profile.sections"),
      exact: true,
    })
    .click();
  await page.getByRole("menuitem", { name: title }).click();
}
