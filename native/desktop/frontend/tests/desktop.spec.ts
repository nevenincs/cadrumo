import { expect, test } from "@playwright/test";

test("front page opens a full-screen terminal without simulated output", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open TUI" }).click();
  await expect(page.locator(".xterm")).toHaveCount(1);
  const terminal = await page.locator(".terminal-page").boundingBox();
  expect(terminal?.width).toBe(page.viewportSize()?.width);
  expect(terminal?.height).toBe(page.viewportSize()?.height);
  await expect(page.locator(".xterm-rows")).toHaveText("");
  await page.getByRole("button", { name: "Back to front page" }).click();
  await expect(page.getByRole("button", { name: "Open TUI" })).toBeVisible();
});
