import { expect, test } from "@playwright/test";

test("TUI owns the workspace; docs and optional console remain independent", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Textual workbench" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Understand each step." }),
  ).toBeVisible();
  await expect(page.locator(".xterm")).toHaveCount(1);
  await page.getByRole("button", { name: "Toggle console panel" }).click();
  await expect(
    page.getByRole("tab", { name: "Python console" }),
  ).toHaveAttribute("data-state", "active");
  await expect(page.locator(".xterm")).toHaveCount(2);
  await page.getByRole("tab", { name: "Logs" }).click();
  await expect(
    page.getByText("Frontend opened. Native environment is not connected."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear view" }).click();
  await expect(page.getByText("No events in this view.")).toBeVisible();
  await page.getByRole("tab", { name: "Python console" }).click();
  await page.getByRole("button", { name: "Close console panel" }).click();
  await expect(page.locator(".xterm")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Python console", exact: true })
    .click();
  await expect(page.locator(".xterm")).toHaveCount(2);
  const separator = page.getByRole("separator", {
    name: "Resize console panel",
  });
  const previous = Number(await separator.getAttribute("aria-valuenow"));
  await separator.focus();
  await page.keyboard.press("ArrowUp");
  await expect(separator).toHaveAttribute(
    "aria-valuenow",
    String(previous + 24),
  );
  await page
    .getByRole("button", { name: "How your records become tax figures" })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "A bank transaction means nothing on its own",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close documentation" }).click();
  await page.keyboard.press("Control+k");
  await page.getByRole("textbox", { name: "Search workspace" }).fill("welcome");
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Your records. A clearer picture." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("bundled documentation and navigation work offline", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await expect(page.locator(".xterm")).toHaveCount(1);
  await context.setOffline(true);
  await page.getByRole("button", { name: "User documentation" }).click();
  await page
    .getByRole("textbox", { name: "Search documentation" })
    .fill("bank transaction");
  await page
    .getByRole("button", { name: "How your records become tax figures" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tracing a number back to the law" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Editing and checking a calculation" })
    .click();
  await expect(page.locator(".prose h1")).toContainText("Editing");
  await page.getByRole("button", { name: "Welcome", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your records. A clearer picture." }),
  ).toBeVisible();
});

test("desktop and narrow layouts stay within their viewport", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page.locator(".xterm")).toHaveCount(1);
  await page.screenshot({
    path: testInfo.outputPath("desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle console panel" }).click();
  await expect(page.locator(".xterm")).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath("console.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Welcome", exact: true }).click();
  await page.getByRole("button", { name: "Close documentation" }).click();
  await page.getByRole("button", { name: "Close console panel" }).click();
  await page.screenshot({
    path: testInfo.outputPath("welcome.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 520, height: 800 });
  await page
    .getByRole("button", { name: "Textual workbench", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Textual workbench" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("narrow.png"),
    fullPage: true,
  });
});
