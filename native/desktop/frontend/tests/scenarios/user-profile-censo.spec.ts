import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { profileStated } from "../support/profileFixture";
import { open, band, row, save } from "../support/userProfilePage";

test("Censo checks saved prerequisites and edits the missing identity", async ({
  page,
}) => {
  await open(page);
  const region = band(page);
  await expect(region).toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toHaveCount(0);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.identity"),
      exact: true,
    })
    .click();
  const editor = page.getByRole("dialog", {
    name: "Tax ID (NIF/NIE/CIF)",
    exact: true,
  });
  await editor.getByRole("textbox").fill("X0001500M");
  await save(editor).click();
  await expect(region).not.toContainText(
    label("auth.sync.requirement.profile_tax_id_required"),
  );
  await expect(region).toContainText(
    label("auth.sync.requirement.auth_method_required"),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(0);
});

test("a Censo review is shown on the details it changes and saves only after approval", async ({
  page,
}) => {
  const profile = await open(page, "censo-ready");
  const started = Date.now();
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.review_count", { count: 3 }),
    })
    .click();
  const address = row(profile, "contact.fiscal_address");
  await expect(address).toBeFocused();
  await expect(address).toContainText("Calle Nueva 1");
  await expect(address).toContainText(label("desktop.profile.censo.preserve"));
  await expect(
    profile.getByText(label("desktop.profile.censo.preserve"), { exact: true }),
  ).toHaveCount(2);
  const cadastral = row(profile, "contact.fiscal_address_cadastral_reference");
  await expect(cadastral).toContainText(label("desktop.profile.censo.adopt"));
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
  console.log(
    JSON.stringify({
      benchmark: "censo_browser_review",
      elapsed_ms: Date.now() - started,
    }),
  );
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.done"));
  await expect(cadastral).toContainText("1234567UF7613S0001AB");
  await expect(
    cadastral.getByTitle(label("desktop.profile.censo.source")),
  ).toBeVisible();
  // The address the review preserved is the one the profile already held.
  await expect(address).toContainText(profileStated("contact.fiscal_address"));
  await expect(address).not.toContainText("Calle Nueva 1");
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(1);
  await region
    .getByRole("button", {
      name: label("desktop.profile.dismiss"),
      exact: true,
    })
    .click();
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    }),
  ).toBeEnabled();
});

test("an uncertain Censo start is not silently retried", async ({ page }) => {
  await open(page, "censo-uncertain");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.unknown_start"),
  );
  await region
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(
    label("desktop.profile.censo.unknown_start"),
  );
  await expect(pull).toHaveCount(0);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("an initially unknown status recovers the admitted operation", async ({
  page,
}) => {
  await open(page, "censo-initial-unknown");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.unknown"));
  await page.evaluate(() => window.__scenarioCenso!.releaseStatus());
  await expect(region).toContainText(
    label("desktop.profile.censo.review_count", { count: 3 }),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
});

test("a late readiness check does not erase a profile refusal", async ({
  page,
}) => {
  await open(page, "censo-refused");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  await page.evaluate(() => window.__scenarioCenso!.holdReadiness());
  await region
    .getByRole("button", {
      name: label("desktop.profile.refresh"),
      exact: true,
    })
    .click();
  await pull.click();
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  await page.evaluate(() => window.__scenarioCenso!.releaseReadiness());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.readinessChecks()))
    .toBe(2);
  await expect(region).toContainText(
    label("desktop.profile.censo.profile_mismatch"),
  );
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(2);
});

test("the profile page reads a pull it was left from before it offers another", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  const pull = region.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  const review = region.getByRole("button", {
    name: label("desktop.profile.censo.review_count", { count: 3 }),
  });
  await pull.click();
  await expect(review).toBeVisible();
  const rail = page.locator(".rail");
  await rail
    .getByRole("button", { name: label("desktop.calendar.title"), exact: true })
    .click();
  await page
    .getByRole("button", { name: label("desktop.navigation.leave.discard") })
    .click();
  await expect(page.locator(".user-profile-page")).not.toBeVisible();
  // Back on the page while the host's answer is on its way: nothing can be
  // started until it comes.
  await page.evaluate(() => window.__scenarioCenso!.holdStatus());
  await rail
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(pull).toBeDisabled();
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  await page.evaluate(() => window.__scenarioCenso!.releaseStatus());
  await expect(review).toBeVisible();
  await expect(pull).toHaveCount(0);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  expect(await page.evaluate(() => window.__scenarioCenso!.pulls())).toBe(1);
});

test("discarding Censo changes does not write profile data", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.reject"),
      exact: true,
    })
    .click();
  await expect(region).toContainText(label("desktop.profile.censo.stopped"));
  await expect(page.locator(".user-profile-page")).not.toContainText(
    "Calle Nueva 1",
  );
  expect(await page.evaluate(() => window.__scenarioProfile!.writes())).toBe(0);
});

test("Censo progress notifications coalesce without starting another pull", async ({
  page,
}) => {
  await open(page, "censo-ready");
  const region = band(page);
  await region
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  await expect(page.locator(".user-profile-page")).toContainText(
    "Calle Nueva 1",
  );
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.statuses()))
    .toBeGreaterThan(0);
  const before = await page.evaluate(() => window.__scenarioCenso!.statuses());
  await page.evaluate(() => window.__scenarioCenso!.burst());
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.statuses()))
    .toBe(before + 2);
  expect(await page.evaluate(() => window.__scenarioCenso!.starts())).toBe(1);
  await expect(
    region.getByRole("button", {
      name: label("desktop.profile.censo.apply"),
      exact: true,
    }),
  ).toBeEnabled();
});
