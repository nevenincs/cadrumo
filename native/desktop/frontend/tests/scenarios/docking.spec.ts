import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

const header = (page: Page, pane: string) =>
  page.locator(`[data-dock-header="${pane}"]`);
const content = (page: Page, pane: string) =>
  page.locator(`[data-dock-pane="${pane}"]`);
async function arrange(page: Page, pane: string, key: string) {
  await header(page, pane)
    .getByRole("button", { name: label("desktop.dock.arrange"), exact: true })
    .click();
  await page.getByRole("menuitem", { name: label(key), exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (localStorage.getItem("cadrumo-shell-layout")) return;
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({
        prefs: { orientation: "row", order: "docs" },
        layout: {
          page: "docs",
          docsShown: true,
          tuiShown: false,
          agentShown: false,
          panelOpen: true,
          tab: "console",
        },
      }),
    );
  });
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&window=port",
  );
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.rail.tui") })
    .click();
  await expect(header(page, "console")).toBeVisible();
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.getByRole("main")).toBeVisible();
});

test("tabs, splits and floating keep one mounted terminal", async ({
  page,
}) => {
  const terminal = content(page, "console").locator(".terminal-host");
  await terminal.evaluate((element) =>
    element.setAttribute("data-retained", "yes"),
  );
  await arrange(page, "console", "desktop.dock.tab");
  await expect(header(page, "console").getByRole("tab")).toHaveCount(2);
  await expect(content(page, "docs")).toBeHidden();
  for (const direction of ["left", "right", "top", "bottom"]) {
    await arrange(page, "console", `desktop.dock.${direction}`);
    const source = await content(page, "console").boundingBox();
    const target = await content(page, "docs").boundingBox();
    expect(source).not.toBeNull();
    expect(target).not.toBeNull();
    if (direction === "left") expect(source!.x).toBeLessThan(target!.x);
    if (direction === "right") expect(source!.x).toBeGreaterThan(target!.x);
    if (direction === "top") expect(source!.y).toBeLessThan(target!.y);
    if (direction === "bottom") expect(source!.y).toBeGreaterThan(target!.y);
  }
  await arrange(page, "console", "desktop.dock.float");
  await expect(
    page.getByRole("main").locator('[data-dock-header="console"]'),
  ).toBeVisible();
  const move = header(page, "console").getByRole("button", {
    name: label("desktop.dock.move"),
  });
  await move.focus();
  const before = await content(page, "console").boundingBox();
  await page.keyboard.press("ArrowRight");
  expect((await content(page, "console").boundingBox())!.x).toBeGreaterThan(
    before!.x,
  );
  await arrange(page, "console", "desktop.dock.dock");
  await expect(terminal).toHaveAttribute("data-retained", "yes");
  await expect(page.locator('[data-terminal="console"]')).toHaveCount(1);
});

test("dragging a tab into another group moves it without duplication", async ({
  page,
}) => {
  await page.locator("#tab-console").dragTo(page.locator("#tab-docs"));
  await expect(header(page, "console").getByRole("tab")).toHaveCount(2);
  await expect(page.locator("#tab-console")).toHaveCount(1);
  await expect(content(page, "console")).toBeVisible();
  await header(page, "console")
    .getByRole("tab", { name: label("desktop.pane.docs"), exact: true })
    .click();
  await expect(content(page, "docs")).toBeVisible();
  await expect(content(page, "console")).toBeHidden();
});

test("native fullscreen restores the saved split and expansion is separate", async ({
  page,
}) => {
  const before = await content(page, "docs").boundingBox();
  await arrange(page, "docs", "desktop.dock.fullscreen");
  await expect(page.locator(".titlebar")).toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await expect(content(page, "tui")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator(".titlebar")).not.toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await expect(content(page, "tui")).toBeVisible();
  expect(await content(page, "docs").boundingBox()).toEqual(before);
  await page.keyboard.press("F11");
  await expect(page.locator(".titlebar")).toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await page.keyboard.press("F11");
  await expect(page.locator(".titlebar")).not.toHaveAttribute(
    "data-fullscreen",
    "",
  );
  expect(
    await page.evaluate(() => window.__scenarioWindow!.actions()),
  ).toContain("toggle_fullscreen");
  await arrange(page, "docs", "desktop.dock.expand");
  await expect(content(page, "tui")).toBeHidden();
  await expect(page.locator(".titlebar")).not.toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await header(page, "docs")
    .getByRole("button", { name: label("desktop.dock.restore"), exact: true })
    .click();
  expect(await content(page, "docs").boundingBox()).toEqual(before);
  await arrange(page, "docs", "desktop.dock.fullscreen");
  await page.keyboard.press("ControlOrMeta+Shift+Digit1");
  await expect(content(page, "console")).toBeVisible();
  await expect(content(page, "console").locator("textarea")).toBeFocused();
  await expect(page.locator(".titlebar")).toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await page.keyboard.press("Escape");
  expect(await content(page, "docs").boundingBox()).toEqual(before);
});

test("the tab strip owns pane titles and layout controls without duplicate rows", async ({
  page,
}, testInfo) => {
  for (const pane of ["docs", "tui"]) {
    await expect(
      content(page, pane).locator('[data-slot="pane-header"]'),
    ).toHaveCount(0);
    await expect(header(page, pane).getByRole("tab")).toHaveCount(1);
    await expect(
      header(page, pane).getByRole("button", {
        name: label("desktop.dock.expand"),
        exact: true,
      }),
    ).toHaveCount(1);
    await expect(
      header(page, pane).getByRole("button", {
        name: label("desktop.dock.close"),
        exact: true,
      }),
    ).toHaveCount(1);
  }
  await page.screenshot({
    path: testInfo.outputPath("single-pane-chrome.png"),
  });
});

test("restoring a pane's size leaves native fullscreen on until explicitly exited", async ({
  page,
}) => {
  await arrange(page, "docs", "desktop.dock.fullscreen");
  await header(page, "docs")
    .getByRole("button", { name: label("desktop.dock.restore"), exact: true })
    .click();
  await expect(content(page, "tui")).toBeVisible();
  await expect(page.locator(".titlebar")).toHaveAttribute(
    "data-fullscreen",
    "",
  );
  await arrange(page, "docs", "desktop.dock.exit_fullscreen");
  await expect(page.locator(".titlebar")).not.toHaveAttribute(
    "data-fullscreen",
    "",
  );
});

test("expanded tab groups follow the selected pane and restore the workspace for layout moves", async ({
  page,
}) => {
  await arrange(page, "console", "desktop.dock.tab");
  await arrange(page, "console", "desktop.dock.expand");
  await expect(content(page, "tui")).toBeHidden();
  await page.locator("#tab-docs").click();
  await expect(content(page, "docs")).toBeVisible();
  await expect(content(page, "console")).toBeHidden();
  await expect(content(page, "tui")).toBeHidden();
  await page.locator("#tab-console").click();
  await expect(content(page, "console")).toBeVisible();
  await expect(content(page, "docs")).toBeHidden();
  await arrange(page, "console", "desktop.dock.right");
  await expect(content(page, "docs")).toBeVisible();
  await expect(content(page, "tui")).toBeVisible();
  await arrange(page, "console", "desktop.dock.expand");
  await arrange(page, "console", "desktop.dock.float");
  await expect(
    header(page, "console").getByRole("button", {
      name: label("desktop.dock.move"),
    }),
  ).toBeVisible();
  await expect(content(page, "docs")).toBeVisible();
});

test("floating bounds survive reload and each dimension resizes independently", async ({
  page,
}, testInfo) => {
  await arrange(page, "console", "desktop.dock.float");
  const before = await content(page, "console").boundingBox();
  const handles = page.getByRole("separator", {
    name: `${label("desktop.dock.resize")}: ${label("desktop.rail.console")}`,
    exact: true,
  });
  // The floating pair is independently keyboard accessible.
  const horizontal = handles.filter({ visible: true }).last();
  await horizontal.press("ArrowUp");
  expect((await content(page, "console").boundingBox())!.width).toBe(
    before!.width,
  );
  expect((await content(page, "console").boundingBox())!.height).toBeLessThan(
    before!.height,
  );
  await handles.first().press("ArrowLeft");
  expect((await content(page, "console").boundingBox())!.width).toBeLessThan(
    before!.width,
  );
  const bounds = await content(page, "console").boundingBox();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          JSON.parse(localStorage.getItem("cadrumo-shell-layout")!).layout
            .docking.floating.length,
      ),
    )
    .toBe(1);
  await page.reload();
  await expect(
    header(page, "console").getByRole("button", {
      name: label("desktop.dock.move"),
    }),
  ).toBeVisible();
  expect(await content(page, "console").boundingBox()).toEqual(bounds);
  await page.screenshot({
    path: testInfo.outputPath("floating-workspace.png"),
  });
});

test("rail drops reopen the same panel and tab activation transfers keyboard focus", async ({
  page,
}) => {
  await header(page, "console")
    .getByRole("button", { name: label("desktop.dock.close"), exact: true })
    .click();
  await expect(content(page, "console")).toBeHidden();
  const rail = page.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  await rail
    .getByRole("button", { name: label("desktop.panel.label"), exact: false })
    .dragTo(page.locator("#tab-docs"));
  await expect(content(page, "console")).toBeVisible();
  await expect(page.locator('[data-terminal="console"]')).toHaveCount(1);
  await page.locator("#tab-console").press("Enter");
  await expect(content(page, "console").locator("textarea")).toBeFocused();
});
