import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { startFromDocs, open } from "../support/scenarioShell";
import { calendarButton } from "../support/scenarioRail";

// The documentation pane: its origin and bridge, navigation controls, search, language and the palette's section.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("the documentation fixture is another origin and answers the bridge", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const frame = target.frameLocator(".docs-frame");
  await expect(frame.locator("h1")).toHaveText("Stand-in documentation");
  const docsUrl = new URL(
    (await target.locator(".docs-frame").getAttribute("src")) ?? "",
  );
  expect(docsUrl.origin).not.toBe(new URL(target.url()).origin);
  // The real bridge script answers a search through the page's controller.
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill("sign-in");
  const result = palette
    .getByRole("listbox")
    .getByRole("option", { name: /config sign-in-status/ });
  await expect(result).toBeVisible();
  await result.click();
  await expect(palette).toBeHidden();
  await expect(frame.locator("h1")).toHaveText("Second page");
});

test("the documentation pane offers visible Back and Forward controls", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.docs"), exact: true })
    .click();
  const frame = target.frameLocator(".docs-frame");
  const head = target.locator('[data-dock-header="docs"]');
  const back = head.getByRole("button", {
    name: label("desktop.action.docs_back"),
    exact: true,
  });
  const forward = head.getByRole("button", {
    name: label("desktop.action.docs_forward"),
    exact: true,
  });
  await expect(back).toBeVisible();
  await expect(forward).toBeVisible();
  await frame.getByRole("link", { name: "Second page" }).click();
  await expect(frame.locator("h1")).toHaveText("Second page");
  await back.click();
  await expect(frame.locator("h1")).toHaveText("Stand-in documentation");
  await forward.click();
  await expect(frame.locator("h1")).toHaveText("Second page");

  await calendarButton(target).click();
  await expect(back).toHaveCount(0);
  await expect(forward).toHaveCount(0);
});

test("documentation search and navigation do not depend on URL.origin", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const frame = target.frameLocator(".docs-frame");
  await expect(frame.locator("h1")).toHaveText("Stand-in documentation");
  // A custom-scheme URL reports "null" here. The fixture still serves HTTP,
  // so make that browser API behave as it does for macOS documentation URLs.
  await target.evaluate(() => {
    Object.defineProperty(URL.prototype, "origin", {
      configurable: true,
      get: () => "null",
    });
  });
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill("sign-in");
  const result = palette
    .getByRole("listbox")
    .getByRole("option", { name: /config sign-in-status/ });
  await expect(result).toBeVisible();
  await result.click();
  await expect(frame.locator("h1")).toHaveText("Second page");
});

test("the output language reaches the chrome and the documentation", async ({
  page: target,
}) => {
  await open(target, "signed-in", "&lang=es");
  await expect(target.locator("html")).toHaveAttribute("lang", "es");
  await expect(
    target.getByRole("navigation", {
      name: label("desktop.rail.label", {}, "es"),
    }),
  ).toBeVisible();
  await expect(
    target.frameLocator(".docs-frame").locator("html"),
  ).toHaveAttribute("lang", "es");
});

test("the palette's last section is the documentation's while a query searches it", async ({
  page: target,
}) => {
  // Actions are listed before the capped documentation, and the
  // documentation's section stays last, present with or without results; the
  // packaged acceptance run reads documentation results from it.
  await open(target, "empty");
  await target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.search"), exact: true })
    .click();
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.rail.logs"));
  const sections = palette.locator(".palette-results > section");
  await expect(sections).toHaveCount(2);
  await expect(sections.first().getByRole("option").first()).toContainText(
    label("desktop.rail.logs"),
  );
  await expect(sections.last().getByRole("option")).toHaveCount(0);
});
