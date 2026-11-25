import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

const header = (page: Page, pane: string) =>
  page.locator(`[data-dock-header="${pane}"]`);
const content = (page: Page, pane: string) =>
  page.locator(`[data-dock-pane="${pane}"]`);
const consoleOpens = (page: Page) =>
  page.evaluate(() =>
    (window.__scenarioHostCalls ?? []).filter((call) =>
      call.startsWith("openTerminal console "),
    ),
  );
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

test("the floating panel's move handle says how it moves on a press and announces a keyboard move", async ({
  page,
}) => {
  await arrange(page, "console", "desktop.dock.float");
  const move = header(page, "console").getByRole("button", {
    name: label("desktop.dock.move"),
  });
  const before = (await content(page, "console").boundingBox())!;
  const hint = page
    .locator('[data-slot="toast"]')
    .filter({ hasText: label("desktop.dock.move_hint") });
  await expect(hint).toHaveCount(0);
  // A press that drags nothing leaves the panel where it is and says how the
  // handle moves it.
  await move.click();
  await expect(hint).toBeVisible();
  expect(await content(page, "console").boundingBox()).toEqual(before);
  // A drag moves the panel and is no press.
  await page.reload();
  await expect(move).toBeVisible();
  await expect(hint).toHaveCount(0);
  const handle = (await move.boundingBox())!;
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    handle.x + handle.width / 2 + 60,
    handle.y + handle.height / 2 + 40,
    { steps: 4 },
  );
  await page.mouse.up();
  const dragged = (await content(page, "console").boundingBox())!;
  expect(dragged.x).toBeGreaterThan(before.x);
  await expect(hint).toHaveCount(0);
  // Enter, a keyboard press, says it too; an arrow moves the panel and the
  // move is announced.
  await move.focus();
  await page.keyboard.press("Enter");
  await expect(hint).toBeVisible();
  await page.keyboard.press("ArrowDown");
  expect((await content(page, "console").boundingBox())!.y).toBeGreaterThan(
    dragged.y,
  );
  await expect(
    page.getByRole("status").filter({
      hasText: label("desktop.dock.drag_moved", {
        pane: label("desktop.rail.console"),
      }),
    }),
  ).toHaveCount(1);
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
  const title = (await page
    .locator("#tab-docs [data-dock-title]")
    .boundingBox())!;
  await page.mouse.move(title.x + title.width / 2, title.y + title.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    title.x + title.width + 20,
    title.y + title.height + 24,
  );
  const ghost = page.locator("[data-dock-drag-ghost]");
  await expect(ghost).toBeVisible();
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await expect(ghost).toHaveCount(0);
  await expect(page.locator(".titlebar")).toHaveAttribute(
    "data-fullscreen",
    "",
  );
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

for (const side of ["left", "right", "top", "bottom", "centre"] as const) {
  test(`title pointer previews and places a ${side} drop`, async ({
    page,
  }, testInfo) => {
    const title = page.locator("#tab-console [data-dock-title]");
    const source = (await title.boundingBox())!;
    const target = (await content(page, "docs").boundingBox())!;
    const x =
      target.x +
      target.width * (side === "left" ? 0.05 : side === "right" ? 0.95 : 0.5);
    const y =
      target.y +
      target.height * (side === "top" ? 0.05 : side === "bottom" ? 0.95 : 0.5);
    await page.mouse.move(
      source.x + source.width / 2,
      source.y + source.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(x, y, { steps: 12 });
    await page.screenshot({ path: testInfo.outputPath(`${side}.png`) });
    await expect(page.locator("[data-dock-drag-ghost]")).toBeVisible();
    const preview = page.locator("[data-dock-drop-preview]");
    await expect(preview).toBeVisible();
    const rect = (await preview.boundingBox())!;
    const midX = target.x + target.width / 2;
    const midY = target.y + target.height / 2;
    if (side === "left")
      expect(rect.x + rect.width).toBeLessThanOrEqual(midX + 6);
    if (side === "right") expect(rect.x).toBeGreaterThanOrEqual(midX - 6);
    if (side === "top")
      expect(rect.y + rect.height).toBeLessThanOrEqual(midY + 6);
    if (side === "bottom") expect(rect.y).toBeGreaterThanOrEqual(midY - 32);
    if (side === "centre") {
      expect(rect.width).toBeGreaterThan(target.width * 0.8);
      expect(rect.height).toBeGreaterThan(target.height * 0.8);
    }
    await page.mouse.up();
    await expect(preview).toHaveCount(0);
    if (side === "centre") {
      await expect(header(page, "console").getByRole("tab")).toHaveCount(2);
    } else {
      const a = (await content(page, "console").boundingBox())!;
      const b = (await content(page, "docs").boundingBox())!;
      if (side === "left") expect(a.x + a.width).toBeLessThanOrEqual(b.x + 1);
      if (side === "right")
        expect(a.x).toBeGreaterThanOrEqual(b.x + b.width - 1);
      if (side === "top") expect(a.y + a.height).toBeLessThanOrEqual(b.y + 1);
      if (side === "bottom")
        expect(a.y).toBeGreaterThanOrEqual(b.y + b.height - 1);
    }
  });
}

async function dragTitle(
  page: Page,
  pane: string,
  target: string,
  fraction: number,
) {
  const title = (await page
    .locator(`#tab-${pane} [data-dock-title]`)
    .boundingBox())!;
  const destination = (await page.locator(`#tab-${target}`).boundingBox())!;
  await page.mouse.move(title.x + title.width / 2, title.y + title.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    destination.x + destination.width * fraction,
    destination.y + destination.height / 2,
    { steps: 12 },
  );
}

test("strip insertion orders both ways and Escape restores an inactive title", async ({
  page,
}) => {
  await arrange(page, "console", "desktop.dock.tab");
  const tabs = page
    .locator("#tab-console")
    .locator("xpath=ancestor::*[@role='tablist']")
    .getByRole("tab");
  const order = () => tabs.evaluateAll((items) => items.map((item) => item.id));
  const original = await order();
  for (const placement of ["before", "after"] as const) {
    await dragTitle(
      page,
      "console",
      "docs",
      placement === "before" ? 0.2 : 0.8,
    );
    const line = page.locator(`[data-dock-insertion="${placement}"]`);
    await expect(line).toBeVisible();
    const bounds = (await line.boundingBox())!;
    expect(bounds.width).toBeLessThan(bounds.height / 2);
    await page.mouse.up();
    expect(await order()).toEqual(
      placement === "before"
        ? ["tab-console", "tab-docs"]
        : ["tab-docs", "tab-console"],
    );
  }
  await page.locator("#tab-docs").click();
  await expect(page.locator("#tab-docs")).toBeFocused();
  const before = await order();
  await dragTitle(page, "console", "docs", 0.2);
  await expect(page.locator("[data-dock-drag-ghost]")).toBeVisible();
  const source = (await page.locator("#tab-console").boundingBox())!;
  await page.mouse.move(
    source.x + source.width / 2,
    source.y + source.height / 2,
  );
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await expect(page.locator("[data-dock-drag-ghost]")).toHaveCount(0);
  await expect(page.locator("#tab-docs")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.locator("#tab-docs")).toBeFocused();
  expect(await order()).toEqual(before);
  expect(original).toHaveLength(2);
});

test("keyboard arrangement offers pointer destinations and moves the same terminal", async ({
  page,
}) => {
  await expect.poll(() => consoleOpens(page)).toHaveLength(1);
  const terminal = content(page, "console").locator(".terminal-host");
  await terminal.evaluate((element) =>
    element.setAttribute("data-retained", "yes"),
  );
  await page.locator("#tab-console").press("Shift+F10");
  await page.locator('[data-dock-target-menu="docs"]').press("ArrowRight");
  for (const intent of [
    "left",
    "right",
    "top",
    "bottom",
    "tab",
    "before",
    "after",
  ]) {
    await expect(
      page.locator(`[data-dock-intent="${intent}"][data-dock-target="docs"]`),
    ).toBeAttached();
  }
  const item = page.locator(
    '[data-dock-intent="tab"][data-dock-target="docs"]',
  );
  await item.focus();
  await page.keyboard.press("Enter");
  await expect(header(page, "console").getByRole("tab")).toHaveCount(2);
  await expect(terminal).toHaveAttribute("data-retained", "yes");
  expect(await consoleOpens(page)).toHaveLength(1);
});

test("reset from the arrangement menu and palette preserves the current page and terminal", async ({
  page,
}) => {
  await expect.poll(() => consoleOpens(page)).toHaveLength(1);
  const terminal = content(page, "console").locator(".terminal-host");
  await terminal.evaluate((element) =>
    element.setAttribute("data-retained", "yes"),
  );
  await arrange(page, "console", "desktop.dock.float");
  const action = label("desktop.dock.reset_layout");
  await arrange(page, "console", "desktop.dock.reset_layout");
  const description = page.getByText(
    label("desktop.dock.reset_layout_description"),
    { exact: true },
  );
  await expect(description).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    header(page, "console").getByRole("button", {
      name: label("desktop.dock.move"),
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  await page.locator('.palette [data-slot="command-input"]').fill(action);
  await page
    .locator(".palette")
    .getByRole("option")
    .filter({ hasText: action })
    .click();
  await expect(description).toBeVisible();
  await page.getByRole("button", { name: action, exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = JSON.parse(localStorage.getItem("cadrumo-shell-layout")!);
        return [
          state.layout.page,
          state.prefs.order,
          state.layout.docking?.floating ?? [],
        ];
      }),
    )
    .toEqual(["docs", "tui", []]);
  await expect(terminal).toHaveAttribute("data-retained", "yes");
  expect(await consoleOpens(page)).toHaveLength(1);
});
