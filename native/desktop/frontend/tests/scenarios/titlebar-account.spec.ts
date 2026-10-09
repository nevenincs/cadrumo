import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { identity } from "../../../scripts/configuration.mjs";

test("Settings has no account switcher and sign out appears only in the header menu", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await page
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = page.locator(".settings");
  await expect(settings).toBeVisible();
  await expect(settings).not.toContainText("Demo profile");
  await expect(
    settings.getByText(label("desktop.account.sign_out"), { exact: true }),
  ).toHaveCount(0);
  await expect(
    settings.getByText(label("desktop.account.switch_profile"), {
      exact: true,
    }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  const trigger = page.getByRole("button", {
    name: label("desktop.titlebar.profile_menu"),
  });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const menu = page.getByRole("menu");
  await expect(
    menu.getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    }),
  ).toHaveCount(1);
  await expect(
    menu.getByRole("menuitem", { name: "Ana Soler Vidal", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
});

test("the header chooses the named credential target and never signs out twice", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const trigger = page.getByRole("button", {
    name: label("desktop.titlebar.profile_menu"),
  });
  await trigger.click();
  await page
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await page
    .getByRole("menuitem", { name: "Ana Soler Vidal", exact: true })
    .click();
  const dialog = page.locator(".sign-in");
  await expect(
    dialog.getByLabel(label("desktop.signin.profile"), { exact: true }),
  ).toHaveValue("Ana Soler Vidal");
  const password = dialog.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await expect(password).toBeFocused();
  await password.fill("anything");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(page.locator(".titlebar .profile-name")).toHaveText(
    "Ana Soler Vidal",
  );
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => call === "signOut")).toHaveLength(1);
  expect(calls).toContain("signInProfile 2");
});

test("header sizing leaves the workspace and panel inside the client window", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&bar=off&latency=0");
  await page.getByRole("button", { name: label("desktop.rail.logs") }).click();
  await page.evaluate(() =>
    document.documentElement.style.setProperty("--titlebar-height", "4rem"),
  );
  await expect
    .poll(() =>
      page
        .locator(".titlebar")
        .evaluate((bar) => bar.getBoundingClientRect().height),
    )
    .toBe(64);
  await expect
    .poll(() =>
      page
        .locator(".shell")
        .evaluate((shell) => shell.getBoundingClientRect().bottom),
    )
    .toBe(1050);
  await expect(page.locator(".panel")).toBeInViewport({ ratio: 1 });
});

for (const width of [1440, 520, 360]) {
  test(`header controls and brand stay centered at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole("heading", { level: 1 })).toHaveAccessibleName(
      identity().name,
    );
    const geometry = await page.locator(".titlebar").evaluate((header) => {
      const bounds = header.getBoundingClientRect();
      const edge = parseFloat(getComputedStyle(header).borderBottomWidth);
      const children = Array.from(
        header.querySelectorAll(
          ".titlebar-brand img, .titlebar-brand [data-slot=logo] > span, .profile-trigger, .window-control",
        ),
      ).filter((child) => getComputedStyle(child).display !== "none");
      return {
        overflow: header.scrollWidth - header.clientWidth,
        centered: children.map((child) => {
          const box = child.getBoundingClientRect();
          return Math.abs(
            box.y + box.height / 2 - (bounds.y + (bounds.height - edge) / 2),
          );
        }),
        contained: children.every((child) => {
          const box = child.getBoundingClientRect();
          return box.x >= bounds.x && box.right <= bounds.right;
        }),
      };
    });
    expect(geometry.overflow).toBe(0);
    expect(geometry.contained).toBe(true);
    for (const distance of geometry.centered)
      expect(distance).toBeLessThanOrEqual(1);
    for (const button of await page.locator(".window-controls button").all())
      await expect(button).toBeDisabled();
  });
}
