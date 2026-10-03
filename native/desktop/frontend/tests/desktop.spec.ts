import { expect, test } from "@playwright/test";

test("front page contains only the product name", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button")).toHaveCount(0);
  await expect(page.locator("img")).toHaveCount(0);
});
