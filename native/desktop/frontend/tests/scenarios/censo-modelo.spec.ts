import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The Modelo page offers the one Censo flow the command palette offers: it
// opens the profile page and starts the pull, or reattaches to the one that
// is running or awaiting review. It never starts a second.

async function openDeclarations(page: Page, scenario = "censo-ready") {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await expect(page.locator(".rail")).toBeVisible();
  await page.locator("[data-rail=declarations]").click();
  await expect(page.locator(".declarations-census")).toBeVisible();
}

const band = (page: Page) =>
  page.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });

const review = (page: Page) =>
  band(page).getByRole("button", {
    name: label("desktop.profile.censo.review_count", { count: 3 }),
  });

test("the Modelo page's census entry starts the one Censo flow on the profile page", async ({
  page,
}) => {
  await openDeclarations(page);
  await expect(page.locator(".declarations-census")).toHaveText(
    label("desktop.profile.censo.title"),
  );
  await page.locator(".declarations-census").click();
  await expect(page.locator(".user-profile-page")).toContainText("Soler Vidal");
  await expect(review(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("leaving the profile page keeps the review until the person answers, and the entry reattaches to it", async ({
  page,
}) => {
  await openDeclarations(page);
  await page.locator(".declarations-census").click();
  await expect(review(page)).toBeVisible();
  // The review is the pull's; leaving asks, and staying keeps it as it was.
  await page.locator("[data-rail=declarations]").click();
  await page
    .getByRole("button", { name: label("desktop.navigation.leave.stay") })
    .first()
    .click();
  await expect(review(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  // Leaving without answering does not end the pull: the host still holds it,
  // and the entry brings the page back to it instead of pulling again.
  await page.locator("[data-rail=declarations]").click();
  await page
    .getByRole("button", { name: label("desktop.navigation.leave.discard") })
    .click();
  await page.locator(".declarations-census").click();
  await expect(review(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  expect(await page.evaluate(() => window.__scenarioCenso!.pulls())).toBe(1);
  // Answering ends that pull; the entry then asks for a new one.
  await band(page)
    .getByRole("button", { name: label("desktop.profile.censo.reject") })
    .click();
  await page.locator("[data-rail=declarations]").click();
  await page.locator(".declarations-census").click();
  await expect(review(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.pulls())).toBe(2);
});

test("a pull the check refuses is explained by the band and not started", async ({
  page,
}) => {
  await openDeclarations(page, "censo-nie");
  await page.locator(".declarations-census").click();
  await expect(band(page)).toBeVisible();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(0);
});
