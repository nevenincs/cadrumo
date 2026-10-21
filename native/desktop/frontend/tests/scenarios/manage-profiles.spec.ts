import { test, expect, type Page } from "@playwright/test";
import { label } from "../support/strings";

async function manage(page: Page, scenario = "signed-in") {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  const signin = page.locator(".sign-in");
  if (scenario !== "signed-in") await expect(signin).toBeVisible();
  if (await signin.isVisible())
    await signin
      .getByRole("button", { name: label("desktop.signin.dismiss") })
      .click();
  await page.locator(".profile-trigger").click();
  await page
    .getByRole("menuitem", { name: label("desktop.account.manage.title") })
    .click();
  return page.getByRole("dialog", {
    name: label("desktop.account.manage.title"),
    exact: true,
  });
}

test("deletion requires the exact profile name and an independent acknowledgement", async ({
  page,
}) => {
  const manager = await manage(page);
  const row = manager.getByRole("listitem").first();
  const name = await row.locator("span").first().innerText();
  await row.getByRole("button").click();
  const review = page.getByRole("dialog", {
    name: label("desktop.account.manage.delete_title", { name }),
  });
  const remove = review.getByRole("button", {
    name: label("desktop.account.manage.delete"),
    exact: true,
  });
  await expect(remove).toBeDisabled();
  await review.getByRole("textbox").fill(name.toUpperCase());
  await review.getByRole("checkbox").check();
  await expect(remove).toBeDisabled();
  await review.getByRole("textbox").fill(name);
  await review.getByRole("checkbox").uncheck();
  await expect(remove).toBeDisabled();
  await review.getByRole("checkbox").check();
  await remove.click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: label("desktop.account.manage.deleted", { name }) }),
  ).toBeVisible();
  await expect(
    manager.getByRole("listitem").filter({ hasText: name }),
  ).toHaveCount(0);
});

test("cancelling preserves the profile and clears confirmation for the next attempt", async ({
  page,
}) => {
  const manager = await manage(page);
  const row = manager.getByRole("listitem").first();
  const name = await row.locator("span").first().innerText();
  await row.getByRole("button").click();
  await page.getByRole("textbox").fill(name);
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", {
      name: label("desktop.account.manage.cancel"),
      exact: true,
    })
    .click();
  await expect(row).toBeVisible();
  await row.getByRole("button").click();
  await expect(page.getByRole("textbox")).toHaveValue("");
  await expect(page.getByRole("checkbox")).not.toBeChecked();
});

test("management offers the existing create profile form after sign-out", async ({
  page,
}) => {
  const manager = await manage(page);
  await manager
    .getByRole("button", {
      name: label("desktop.account.manage.sign_out_create"),
    })
    .click();
  await manager
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(page.locator(".create-profile")).toBeVisible();
});

test("the last selected profile can be removed without a password", async ({
  page,
}) => {
  const manager = await manage(page, "one-profile");
  const row = manager.getByRole("listitem");
  const name = await row.locator("span").first().innerText();
  await row.getByRole("button").click();
  await page.getByRole("textbox").fill(name);
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", {
      name: label("desktop.account.manage.delete"),
      exact: true,
    })
    .click();
  await expect(manager).toContainText(label("desktop.account.no_profile"));
  await manager
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  await expect(page.locator(".create-profile")).toBeVisible();
});

test("an unreadable profile inventory offers no deletion targets", async ({
  page,
}) => {
  const manager = await manage(page, "profiles-unreadable");
  await expect(manager.getByRole("alert")).toContainText(
    label("desktop.signin.profiles_unread"),
  );
  await expect(manager.getByRole("listitem")).toHaveCount(0);
  await expect(
    manager.getByRole("button", { name: label("desktop.profile.refresh") }),
  ).toBeVisible();
});

for (const locale of ["es", "ca", "hu"]) {
  test(`deletion confirmation is translated in ${locale}`, async ({ page }) => {
    await page.goto(
      `/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=${locale}`,
    );
    await page.locator(".profile-trigger").click();
    await page
      .getByRole("menuitem", {
        name: label("desktop.account.manage.title", {}, locale),
      })
      .click();
    const manager = page.getByRole("dialog", {
      name: label("desktop.account.manage.title", {}, locale),
      exact: true,
    });
    await manager.getByRole("listitem").first().getByRole("button").click();
    await expect(
      page.getByRole("checkbox", {
        name: label("desktop.account.manage.acknowledge", {}, locale),
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: label("desktop.account.manage.delete", {}, locale),
        exact: true,
      }),
    ).toBeDisabled();
    await expect(page.getByRole("dialog")).not.toContainText(
      /desktop\.account|Ã|�/,
    );
  });
}
