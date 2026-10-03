import { expect, test } from "@playwright/test";

test("terminal fills the window without fabricated browser output", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".xterm")).toHaveCount(1);
  await expect(page.getByRole("button")).toHaveCount(0);
  await expect(page.locator(".xterm-rows")).toHaveText("");
  for (const viewport of [
    { width: 1440, height: 1050 },
    { width: 640, height: 480 },
  ]) {
    await page.setViewportSize(viewport);
    const terminal = await page.locator(".terminal-surface").boundingBox();
    expect(terminal).toMatchObject({ x: 0, y: 0, ...viewport });
  }
});
