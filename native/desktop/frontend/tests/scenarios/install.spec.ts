import { expect, test } from "@playwright/test";
import { label } from "../support/strings";

for (const scope of ["user", "machine"] as const) {
  test(`scoped ${scope} installation waits for readiness and suppresses duplicate requests`, async ({
    page,
  }) => {
    await page.addInitScript(() => localStorage.clear());
    await page.clock.install();
    await page.goto("/scenarios.html?scenario=manager-recovers&latency=0");
    await page.clock.runFor(91_000);
    const button = page.getByRole("button", {
      name: label(`desktop.signin.install_${scope}_services`),
      exact: true,
    });
    await expect(button).toBeVisible();
    await button.click();
    await button.evaluate((element: HTMLButtonElement) => element.click());
    await expect(button).toHaveAttribute("aria-busy", "true");
    await expect(
      page.getByLabel(label("desktop.signin.password"), { exact: true }),
    ).toHaveCount(0);
    await page.clock.runFor(10_000);
    await expect(
      page.getByLabel(label("desktop.signin.password"), { exact: true }),
    ).toBeVisible();
    const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
    expect(
      calls.filter((call) => call === `installManager ${scope}`),
    ).toHaveLength(1);
    expect(
      calls.filter((call) => call === "startManager" || call === "signIn"),
    ).toHaveLength(0);
  });
}
