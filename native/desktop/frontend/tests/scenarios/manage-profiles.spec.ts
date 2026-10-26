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
  return openManagement(page);
}

async function openManagement(page: Page) {
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
  await expect(
    manager.getByText(label("desktop.signin.profiles_unread"), { exact: true }),
  ).toHaveCount(1);
  await expect(manager.getByRole("listitem")).toHaveCount(0);
  await expect(
    manager.getByRole("button", { name: label("desktop.profile.refresh") }),
  ).toBeVisible();
});

for (const name of [
  "A profile with a long name ".repeat(6).slice(0, 160).trim(),
  "A".repeat(160),
])
  for (const viewport of [
    { width: 360, height: 640 },
    { width: 640, height: 450 },
  ])
    test(`long profile names stay within management and confirmation at ${viewport.width}x${viewport.height} (${name.includes(" ") ? "words" : "unbroken"})`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.goto("/scenarios.html?scenario=first-run&latency=0&bar=off");
      const create = page.locator(".create-profile");
      await create
        .getByLabel(label("desktop.account.create.name"), { exact: true })
        .fill(name);
      await create
        .getByLabel(label("desktop.signin.password"), { exact: true })
        .fill("correct horse");
      await create
        .getByLabel(label("desktop.account.create.confirm"), { exact: true })
        .fill("correct horse");
      await create
        .getByRole("button", { name: label("desktop.account.create.submit") })
        .click();
      await expect(create).toHaveCount(0);
      const manager = await openManagement(page);
      const contained = async () => {
        const dialog = page.getByRole("dialog");
        expect(
          await dialog.evaluate((element) => {
            const box = element.getBoundingClientRect();
            return {
              withinWindow: box.left >= 0 && box.right <= innerWidth,
              horizontalOverflow: element.scrollWidth > element.clientWidth,
              controlsWithinDialog: Array.from(
                element.querySelectorAll("button, input"),
              )
                .filter((control) => control.getClientRects().length > 0)
                .every((control) => {
                  const at = control.getBoundingClientRect();
                  return at.left >= box.left && at.right <= box.right;
                }),
            };
          }),
        ).toEqual({
          withinWindow: true,
          horizontalOverflow: false,
          controlsWithinDialog: true,
        });
      };
      await expect(manager.getByText(name, { exact: true })).toBeVisible();
      await contained();
      await manager.getByRole("listitem").getByRole("button").click();
      await expect(page.getByRole("textbox")).toBeFocused();
      await contained();
      await expect(page.getByRole("checkbox")).not.toBeChecked();
      await expect(
        page.getByRole("button", {
          name: label("desktop.account.manage.delete"),
          exact: true,
        }),
      ).toBeDisabled();
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
