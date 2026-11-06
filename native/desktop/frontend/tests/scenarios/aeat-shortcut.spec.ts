import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { startFromDocs, open } from "../support/scenarioShell";

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const railButton = (target: Page, key: string) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label(key), exact: true });

const externalOpens = (target: Page) =>
  target.evaluate(() =>
    (window.__scenarioHostCalls ?? []).filter((call) =>
      call.startsWith("openExternal "),
    ),
  );

test("the AEAT shortcut opens the browser page, not the system browser", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const aeat = railButton(target, "desktop.rail.aeat");
  const browser = railButton(target, "desktop.browser.title");
  await expect(browser).toHaveAttribute("aria-pressed", "false");
  await aeat.click();
  await expect(browser).toHaveAttribute("aria-pressed", "true");
  await expect(
    target.getByRole("region", {
      name: label("desktop.browser.title"),
      exact: true,
    }),
  ).toBeFocused();
  // Clicking it again keeps the browser where it is rather than closing it.
  await aeat.click();
  await expect(browser).toHaveAttribute("aria-pressed", "true");
  expect(await externalOpens(target)).toEqual([]);
});

test("the browser page is never restored at launch, and storage holds nothing of the page", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  const browser = railButton(target, "desktop.browser.title");
  await browser.click();
  await expect(browser).toHaveAttribute("aria-pressed", "true");
  const stored = () =>
    target.evaluate(() => localStorage.getItem("cadrumo-shell-layout") ?? "");
  // The page id may be saved; the sign of a page that was drawn is not.
  await expect.poll(stored).toContain('"page":"browser"');
  expect(await stored()).not.toMatch(/sede\.example|https?:|data:image/i);
  // A launch never starts a browser by itself: the saved page is not offered.
  await target.reload();
  await target.keyboard.press("Control+Backquote");
  await expect(railButton(target, "desktop.browser.title")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("the AEAT shortcut's menu opens the agency's site in the system browser", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await railButton(target, "desktop.rail.aeat").click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu.getByRole("menuitem")).toHaveCount(1);
  await menu
    .getByRole("menuitem", { name: label("desktop.browser.external") })
    .click();
  await expect
    .poll(() => externalOpens(target))
    .toEqual(["openExternal https://sede.agenciatributaria.gob.es"]);
  // The page was not opened by the menu.
  await expect(railButton(target, "desktop.browser.title")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("a shortcut the host cannot open says so", async ({ page: target }) => {
  await open(target, "error");
  await target.keyboard.press("Escape");
  await railButton(target, "desktop.rail.aeat").click({ button: "right" });
  await target
    .getByRole("menu")
    .getByRole("menuitem", { name: label("desktop.browser.external") })
    .click();
  await expect(
    target.getByText(label("desktop.toast.open_failed")),
  ).toBeVisible();
});
