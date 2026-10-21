import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { openLogFilters, openPanelTab, panelToggle } from "../support/panel";
import { label } from "../support/strings";
import type { LogLevel } from "../../src/ipc/contract";

const open = (page: Page, logLevel: LogLevel = "INFO") =>
  page.goto(
    `/scenarios.html?scenario=user-profile&latency=0&bar=off&logLevel=${logLevel}`,
  );
const rail = (page: Page, key: string) =>
  page.locator(".rail").getByRole("button", { name: label(key), exact: true });
const saved = (page: Page) =>
  page.evaluate(
    () =>
      JSON.parse(localStorage.getItem("cadrumo-shell-layout") ?? "{}").layout,
  );

test("fresh windows show one profile title and no workspace terminal", async ({
  page,
}) => {
  await open(page);
  await expect(page.locator(".user-profile-page")).toBeVisible();
  await expect(page.locator(".pane-tui")).toBeHidden();
  await expect(
    page.getByRole("heading", {
      name: label("desktop.profile.title"),
      exact: true,
    }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("button", {
      name: label("desktop.profile.maximize"),
      exact: true,
    }),
  ).toHaveCount(1);
  await expect(page.locator(".pane-agent")).toBeVisible();
  await expect(page.locator("section.panel")).toBeHidden();
});

test("profile filters, sections and maximization survive reload without saving search text", async ({
  page,
}) => {
  await open(page);
  const profile = page.locator(".user-profile-page");
  await expect(profile).toContainText("Soler Vidal");
  await profile
    .getByLabel(label("desktop.profile.sections"), { exact: true })
    .selectOption("contact");
  await profile
    .getByLabel(label("desktop.profile.filter"), { exact: true })
    .selectOption("saved");
  await page
    .getByRole("button", {
      name: label("desktop.profile.maximize"),
      exact: true,
    })
    .click();
  await expect(profile.getByRole("navigation")).toBeVisible();
  await expect(
    profile.getByRole("combobox", {
      name: label("desktop.profile.sections"),
      exact: true,
    }),
  ).toBeHidden();
  await profile.getByRole("searchbox").fill("private search");
  await page.reload();
  await expect(profile).toBeVisible();
  await expect(profile.getByRole("searchbox")).toHaveValue("");
  await expect(
    profile.getByLabel(label("desktop.profile.filter"), { exact: true }),
  ).toHaveValue("saved");
  await expect(
    profile.getByRole("navigation").locator('[aria-current="page"]'),
  ).toHaveText("Contact and fiscal address");
  await expect(page.locator(".pane-agent")).toBeHidden();
  expect(await saved(page)).toMatchObject({
    page: "profile",
    maximized: "docs",
    profileView: { section: "contact", filter: "saved" },
  });
  expect(JSON.stringify(await saved(page))).not.toContain("private search");
});

for (const level of ["0", "2", "4"]) {
  test(`log level ${level} and the open Logs tab survive reload and reset`, async ({
    page,
  }) => {
    await open(page);
    await openPanelTab(page, "logs");
    await openLogFilters(page);
    const select = page.getByLabel(label("desktop.logs.minimum_level"), {
      exact: true,
    });
    await select.selectOption(level);
    await page.reload();
    await expect(page.locator("section.panel")).toBeVisible();
    await expect(
      page.getByRole("tab", { name: label("desktop.rail.logs") }),
    ).toHaveAttribute("aria-selected", "true");
    await openLogFilters(page);
    await expect(select).toHaveValue(level);
    await page
      .getByRole("button", {
        name: label("desktop.action.logs_reset"),
        exact: true,
      })
      .click();
    await expect(select).toHaveValue("1");
    await page.reload();
    await openLogFilters(page);
    await expect(select).toHaveValue("1");
    await expect.poll(() => saved(page)).toMatchObject({ logLevel: null });
    await page.keyboard.press("Escape");
    await panelToggle(page).click();
    await page.reload();
    await expect(page.locator("section.panel")).toBeHidden();
  });
}

for (const selection of ["errors", "record"] as const) {
  test(`${selection} pins an explicit log level even when it matches the host default`, async ({
    page,
  }) => {
    const selectedLevel = selection === "errors" ? 3 : 1;
    await open(page, selection === "errors" ? "ERROR" : "INFO");
    await openPanelTab(page, "logs");
    await openLogFilters(page);
    const minimum = page.getByLabel(label("desktop.logs.minimum_level"), {
      exact: true,
    });
    await expect(minimum).toHaveValue(String(selectedLevel));
    await expect.poll(() => saved(page)).toMatchObject({ logLevel: null });
    await page.keyboard.press("Escape");
    if (selection === "errors") {
      await page.keyboard.press("Control+Shift+k");
      await page
        .locator(".palette")
        .getByRole("combobox", { name: label("desktop.palette.label") })
        .fill(label("desktop.action.logs_errors"));
      await page
        .getByRole("listbox")
        .getByRole("option", {
          name: label("desktop.action.logs_errors"),
          exact: true,
        })
        .click();
    } else {
      await page.locator('.record[data-seq="4"]').click({ button: "right" });
      await page
        .getByRole("menuitem", {
          name: label("desktop.menu.only_level", { level: "info" }),
          exact: true,
        })
        .click();
    }
    await expect
      .poll(() => saved(page))
      .toMatchObject({ logLevel: selectedLevel });
    await open(page, "DEBUG");
    await openPanelTab(page, "logs");
    await openLogFilters(page);
    await expect(minimum).toHaveValue(String(selectedLevel));
    await page
      .getByRole("button", {
        name: label("desktop.action.logs_reset"),
        exact: true,
      })
      .click();
    await expect(minimum).toHaveValue("0");
    await expect.poll(() => saved(page)).toMatchObject({ logLevel: null });
    await page.reload();
    await openLogFilters(page);
    await expect(minimum).toHaveValue("0");
  });
}

test("text and logger filters keep following the host default until a level is selected", async ({
  page,
}) => {
  await open(page);
  await openPanelTab(page, "logs");
  await page
    .getByRole("searchbox", { name: label("desktop.logs.filter"), exact: true })
    .fill("Workbench");
  await openLogFilters(page);
  await page
    .getByLabel(label("desktop.logs.logger"), { exact: true })
    .selectOption({ index: 1 });
  await expect.poll(() => saved(page)).toMatchObject({ logLevel: null });
  await open(page, "WARNING");
  await openPanelTab(page, "logs");
  await openLogFilters(page);
  await expect(
    page.getByLabel(label("desktop.logs.minimum_level"), { exact: true }),
  ).toHaveValue("2");
});

test("calendar page and list view survive reload", async ({ page }) => {
  await page.setViewportSize({ width: 720, height: 900 });
  await open(page);
  await rail(page, "desktop.calendar.title").click();
  const list = page.getByRole("radio", {
    name: label("desktop.calendar.view_list"),
    exact: true,
  });
  await list.click();
  await page.reload();
  await expect(list).toBeChecked();
  await expect(page.locator(".pane-tui")).toBeHidden();
  await expect
    .poll(() => saved(page))
    .toMatchObject({ page: "calendar", calendarView: "list" });
});

test("saved workspace choices are respected and malformed settings fall back", async ({
  page,
}) => {
  await seedLayout(page, {
    layout: { page: "docs", tuiShown: true, agentShown: false },
  });
  await open(page);
  await expect(page.locator(".pane-tui")).toBeVisible();
  await page.goto("about:blank");
  await page.addInitScript(() =>
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({
        prefs: 8,
        layout: {
          page: "unknown",
          tuiShown: "yes",
          panelOpen: "true",
          logLevel: 99,
          profileView: { filter: "unknown", expanded: null },
        },
      }),
    ),
  );
  await open(page);
  await expect(page.locator(".user-profile-page")).toBeVisible();
  await expect(page.locator(".pane-tui")).toBeHidden();
  await expect(page.locator("section.panel")).toBeHidden();
});
