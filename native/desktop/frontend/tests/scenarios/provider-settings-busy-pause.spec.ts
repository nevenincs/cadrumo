import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The provider status is the service's own store read and waits on nothing:
// its busy answer only means the host has not yet admitted the service, which
// takes a moment. The settings ask it again after a short pause, not the
// agent catalog's long ones, so the lanes are drawn soon after the host
// admits the service.

const DRAWN_AFTER_RELEASE_MS = 600;

const pane = (target: Page) => target.locator(".pane-agent");

const providers = (target: Page) =>
  pane(target).getByRole("region", { name: label("desktop.providers.title") });

const busyReads = async (target: Page) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) => call === "providerStatusBusy",
  ).length;

test("provider settings answered busy for a while are drawn within 600 ms of the host's admission", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const door = pane(target).getByRole("button", {
    name: label("desktop.agent.settings"),
  });
  await expect(door).toBeVisible();
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.holdSettingsBusy(),
  );
  await door.click();
  // The status is answered busy more than once while the hold lasts.
  await expect
    .poll(() => busyReads(target), { timeout: 8_000 })
    .toBeGreaterThanOrEqual(2);
  await expect(providers(target).locator("[data-provider]")).toHaveCount(0);

  const released = await target.evaluate(() => {
    window.__scenarioProviderSignIn!.releaseSettingsBusy();
    return performance.now();
  });
  await expect(
    providers(target).locator("[data-provider]").first(),
  ).toBeVisible({ timeout: 6_000 });
  const drawn = await target.evaluate(() => performance.now());
  expect(drawn - released).toBeLessThanOrEqual(DRAWN_AFTER_RELEASE_MS);
});
