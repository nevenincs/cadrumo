import { expect, test } from "@playwright/test";
import { label } from "../support/strings";

test("calendar profile details are optional and the profile link opens the registered view", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=user-profile&latency=0&bar=off&lang=en",
  );
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.calendar.title"), exact: true })
    .click();
  const calendar = page.locator(".calendar-page");
  await expect(
    calendar.getByText(label("desktop.profile.notice.incomplete")),
  ).toBeVisible();
  const toggle = calendar.getByRole("button", {
    name: label("desktop.profile.notice.show_details"),
  });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(
    calendar.getByText(
      "The foral territory is not set, so common-territory dates are used.",
    ),
  ).toHaveCount(0);
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(
    calendar.getByText(
      "The foral territory is not set, so common-territory dates are used.",
    ),
  ).toBeVisible();
  await expect(calendar.getByText("Tax ID (NIF/NIE/CIF)")).toBeVisible();
  await page.keyboard.press("Space");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  const link = calendar.getByRole("link", {
    name: label("desktop.profile.notice.open_profile"),
  });
  await expect(link).toHaveAttribute("href", "cadrumo://view/profile");
  expect(
    await link.evaluate((element) =>
      element.dispatchEvent(
        new MouseEvent("auxclick", {
          bubbles: true,
          cancelable: true,
          button: 1,
        }),
      ),
    ),
  ).toBe(false);
  await expect(calendar).toBeVisible();
  await link.click({ modifiers: ["Control"] });
  const profile = page.locator(".user-profile-page");
  await expect(
    profile.getByText(label("desktop.profile.notice.incomplete")),
  ).toBeVisible();
  await expect(
    profile.getByRole("button", {
      name: label("desktop.profile.notice.show_details"),
    }),
  ).toHaveAttribute("aria-expanded", "false");
});

test("calendar evidence remains visible when the profile is complete", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=user-profile&calendar=evidence&latency=0&bar=off&lang=en",
  );
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.calendar.title"), exact: true })
    .click();
  const calendar = page.locator(".calendar-page");
  await expect(
    calendar.getByText(label("desktop.profile.notice.incomplete")),
  ).toBeVisible();
  await page.evaluate(() => window.__scenarioProfile!.complete());
  await expect(
    calendar.getByText(label("desktop.profile.notice.incomplete")),
  ).toHaveCount(0);
  await expect(
    calendar.getByText(label("desktop.calendar.notice.attention")),
  ).toBeVisible();
  await expect(
    calendar.getByText(label("desktop.profile.notice.attention")),
  ).toHaveCount(0);
  await calendar
    .getByRole("button", { name: label("desktop.profile.notice.show_details") })
    .click();
  await expect(
    calendar.getByText("The filing receipt has not been verified."),
  ).toBeVisible();
  await expect(
    calendar.getByText(label("desktop.profile.notice.missing_fields")),
  ).toHaveCount(0);
});

test("missing fields remain attention even when setup is complete, and collapse for another profile", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=user-profile&calendar=ahead&latency=0&bar=off&lang=en",
  );
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.calendar.title"), exact: true })
    .click();
  const calendar = page.locator(".calendar-page");
  await expect(
    calendar.getByText(label("desktop.profile.notice.incomplete")),
  ).toBeVisible();
  await page.evaluate(() => window.__scenarioProfile!.completeWithMissing());
  await expect(
    calendar.getByText(label("desktop.profile.notice.attention")),
  ).toBeVisible();
  await calendar
    .getByRole("button", { name: label("desktop.profile.notice.show_details") })
    .click();
  await expect(calendar.getByText("Tax ID (NIF/NIE/CIF)")).toBeVisible();
  await page.evaluate(() => window.__scenarioProfile!.changeIdentity());
  await expect(
    calendar.getByRole("button", {
      name: label("desktop.profile.notice.show_details"),
    }),
  ).toHaveAttribute("aria-expanded", "false");
  await expect(calendar.getByText("Tax ID (NIF/NIE/CIF)")).toHaveCount(0);
  await page.evaluate(() => window.__scenarioProfile!.complete());
  await expect(
    calendar.getByText(label("desktop.profile.notice.attention")),
  ).toHaveCount(0);
});
