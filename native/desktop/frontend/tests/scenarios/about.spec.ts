import { expect, test } from "@playwright/test";
import { ABOUT_FIXTURE } from "../../src/dev/fixtures/about";
import { label } from "../support/strings";

const open = "/scenarios.html?scenario=signed-in&latency=0&bar=off";

test("Settings states the version and opens the About dialog with the installation's facts", async ({
  page,
}) => {
  await page.goto(open);
  await page
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  const row = page.locator(".settings [data-about-open]");
  await expect(row).toContainText(
    label("desktop.about.version_row", {
      version: ABOUT_FIXTURE.display_version!,
    }),
  );
  await expect(row).toContainText("Cadrumo 9.8.7+2031010203.debug");
  await row.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: label("desktop.about.title"),
  });
  await expect(dialog).toBeVisible();
  // Literal English, so a missing catalogue key (shown as the key) fails.
  await expect(
    dialog.getByRole("heading", { name: "About Cadrumo" }),
  ).toBeVisible();
  for (const heading of [
    "Application",
    "Runtime",
    "Managers",
    "Agent",
    "Tools",
  ])
    await expect(
      dialog.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  await expect(dialog.locator("[data-about-version]")).toContainText(
    `${ABOUT_FIXTURE.product} ${ABOUT_FIXTURE.display_version}`,
  );
  for (const value of [
    ABOUT_FIXTURE.build_id!,
    ABOUT_FIXTURE.build_date!,
    ABOUT_FIXTURE.channel!,
    ABOUT_FIXTURE.target!,
    ABOUT_FIXTURE.python!,
    ABOUT_FIXTURE.agent!.version!,
    ABOUT_FIXTURE.tools.node!,
  ])
    await expect(dialog).toContainText(value);
  for (const key of [
    "desktop.about.application",
    "desktop.about.runtime",
    "desktop.about.managers",
    "desktop.about.agent",
    "desktop.about.tools",
  ])
    await expect(
      dialog.getByRole("heading", { name: label(key), exact: true }),
    ).toBeVisible();
  // The lists stay closed until opened, and hold every entry with its version.
  const dependencies = dialog.locator('[data-about-list="dependencies"]');
  await expect(dependencies).not.toHaveAttribute("open", "");
  await dependencies.locator("summary").click();
  for (const { name, version } of ABOUT_FIXTURE.agent!.dependencies)
    await expect(
      dependencies.getByRole("listitem").filter({ hasText: name }),
    ).toContainText(version);
  const packages = dialog.locator('[data-about-list="distributions"]');
  await packages.locator("summary").click();
  await expect(packages.getByRole("listitem")).toHaveCount(
    ABOUT_FIXTURE.distributions.length,
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("About copies a plain-text version report and opens from the account menu", async ({
  page,
}) => {
  await page.goto(open);
  await page
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await page
    .getByRole("menuitem", { name: label("desktop.about.open"), exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.about.title"),
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: label("desktop.about.copy"), exact: true })
    .click();
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).toContain("about");
  expect(
    calls.filter((call) => call.startsWith("writeClipboard")),
  ).toHaveLength(1);
});
