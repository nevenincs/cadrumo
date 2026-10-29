import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

async function openApp(page: Page, scenario = "censo-ready") {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await expect(page.locator(".rail")).toBeVisible();
  // Any page but the profile: the census pull is asked for from there.
  await page
    .locator(".rail")
    .getByRole("button", {
      name: label("desktop.calendar.title"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).not.toBeVisible();
}

const band = (page: Page) =>
  page.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });

const palette = (page: Page) =>
  page.getByRole("dialog", { name: label("desktop.palette.label") });

const pullOption = (page: Page) =>
  palette(page).getByRole("option", {
    name: label("desktop.profile.censo.title"),
    exact: true,
  });

async function chooseFromPalette(page: Page) {
  await page.keyboard.press("Control+k");
  await expect(palette(page)).toBeVisible();
  await page.keyboard.type("census");
  await expect(pullOption(page)).toHaveCount(1);
  await pullOption(page).click();
}

test("the palette starts the one Censo flow from a page that is not the profile", async ({
  page,
}) => {
  await openApp(page);
  await chooseFromPalette(page);
  await expect(page.locator(".user-profile-page")).toContainText("Soler Vidal");
  await expect(
    band(page).getByRole("button", {
      name: label("desktop.profile.censo.review_count", { count: 3 }),
    }),
  ).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("choosing it again while a pull awaits review reattaches and does not pull again", async ({
  page,
}) => {
  await openApp(page);
  await chooseFromPalette(page);
  const review = band(page).getByRole("button", {
    name: label("desktop.profile.censo.review_count", { count: 3 }),
  });
  await expect(review).toBeVisible();
  await chooseFromPalette(page);
  await expect(review).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("the palette lists the Censo pull once on the profile page and starts it there", async ({
  page,
}) => {
  await openApp(page);
  await page
    .locator(".rail")
    .getByRole("button", {
      name: label("desktop.profile.title"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText("Soler Vidal");
  await page.keyboard.press("Control+k");
  await page.keyboard.type("census");
  await expect(pullOption(page)).toHaveCount(1);
  await pullOption(page).click();
  await expect(
    band(page).getByRole("button", {
      name: label("desktop.profile.censo.review_count", { count: 3 }),
    }),
  ).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("a pull the check refuses is explained by the band and not started", async ({
  page,
}) => {
  await openApp(page, "censo-nie");
  await chooseFromPalette(page);
  await expect(band(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(0);
});
