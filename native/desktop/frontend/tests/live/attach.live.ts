import { expect, test } from "@playwright/test";
import { shellEntry } from "./fixture";

// The live project's first check: the page the specs receive is the desktop's
// own shell, attached over the loopback DevTools endpoint, with its agent
// column mounted. Its name keeps it out of the other projects.

test("the specs drive the desktop's own shell", async ({ page }) => {
  const endpoint = new URL(process.env.CADRUMO_AGENT_LIVE_ENDPOINT ?? "");
  expect(["127.0.0.1", "[::1]"]).toContain(endpoint.hostname);
  await page.goto("/scenarios.html?scenario=signed-in");
  expect(new URL(page.url()).origin).toBe(shellEntry().origin);
  expect(new URL(page.url()).pathname).not.toBe("/scenarios.html");
  await expect(page.locator(".pane-agent")).toBeAttached();
});
