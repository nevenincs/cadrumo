import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { open, profileAction } from "../support/userProfilePage";

// Declaring the profile's setup complete: the person is told it is done, the
// action leaves once there is nothing left to finish, and a declaration the
// product does not take says why on the page.

const menu = (page: Page) =>
  page.locator(".user-profile-page").getByRole("button", {
    name: label("desktop.profile.action.menu"),
    exact: true,
  });
const completeItem = (page: Page) =>
  page.getByRole("menuitem", {
    name: label("desktop.profile.complete"),
    exact: true,
  });

test("completing the setup says so, and the action leaves with it", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(() => window.__scenarioProfile!.readyToComplete());
  const before = await page.evaluate(() => window.__scenarioProfile!.writes());

  await profileAction(page, "desktop.profile.complete");
  await expect(
    page
      .getByRole("status")
      .getByText(label("desktop.profile.setup_completed_notice")),
  ).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(
    before + 1,
  );

  // Nothing is left to finish, so the menu no longer offers it, and no
  // second declaration is sent.
  await menu(page).click();
  await expect(
    page.getByRole("menuitem", {
      name: label("desktop.profile.action.refresh"),
      exact: true,
    }),
  ).toBeVisible();
  await expect(completeItem(page)).toHaveCount(0);
  await page.keyboard.press("Escape");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(
    before + 1,
  );
});

test("a completion the product refuses says why and stays on offer", async ({
  page,
}) => {
  // ANTI-VACUITY: the completion notice is the settled declaration's, not
  // something every click draws.
  await open(page);
  await page.evaluate(() => window.__scenarioProfile!.readyToComplete());
  await page.evaluate(() => window.__scenarioProfile!.refuse());

  await profileAction(page, "desktop.profile.complete");
  await expect(
    page
      .locator(".user-profile-page")
      .getByRole("alert")
      .filter({ hasText: label("desktop.profile.refused") }),
  ).toBeVisible();
  await expect(
    page.getByText(label("desktop.profile.setup_completed_notice")),
  ).toHaveCount(0);
  await menu(page).click();
  await expect(completeItem(page)).toBeVisible();
});
