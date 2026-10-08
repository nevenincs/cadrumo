import { expect, test } from "@playwright/test";
import { FIXTURE_RECORDS } from "../../src/dev/fixtures/logs";
import { recordLine } from "../../src/shell/records";
import { label } from "../support/strings";

test.use({ timezoneId: "Europe/Madrid" });

for (const kind of ["missing", "unreadable", "rejected"] as const) {
  test(`manager ${kind} state preserves Python records and names its own source`, async ({
    page,
  }) => {
    await page.goto(`/scenarios.html?scenario=manager-log-${kind}&latency=0`);
    await page
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.rail.logs") })
      .click();
    const banner = page.locator(`.source-banner.state-${kind}`);
    await expect(banner).toHaveCount(1);
    await expect(banner).toHaveAttribute("data-source", "manager");
    await expect(banner).toContainText("manager:");
    if (kind === "rejected") {
      await expect(banner).toContainText(
        label("desktop.logs.rejected", { count: 2 }),
      );
    }
    await expect(page.locator('.record[data-seq="4"]')).toContainText(
      "Workbench ready",
    );
  });
}

test("log timestamps use the viewer timezone and preserve legacy wall times", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0");
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  await expect(page.locator('.record[data-seq="1"] time')).toHaveText(
    "10:14:05.120",
  );
  await expect(page.locator('.record[data-seq="4"] time')).toHaveText(
    "10:14:06.420",
  );
  await expect(page.locator('.record[data-seq="4"] time')).toHaveAttribute(
    "datetime",
    "2026-03-02T09:14:06.420Z",
  );
  await expect(page.locator('.record[data-seq="15"] time')).toHaveText(
    "2026-03-02 09:14:10,000",
  );
});

test("log diagnostics show process identity and filter correlation metadata", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0");
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const filter = page.getByLabel(label("desktop.logs.filter"));
  await filter.fill("fixture-attempt-9");
  const row = page.locator(".record");
  await expect(row).toHaveCount(1);
  await expect(row.locator(".record-process")).toHaveText("tui:4208");
  await expect(row.locator(".record-correlation")).toHaveText(
    "fixture-attempt-9",
  );
  await expect(row.locator(".record-context-summary")).toHaveText("failed");
  await row
    .getByRole("button", { name: label("desktop.logs.details") })
    .click();
  await expect(row.locator("pre")).toContainText(
    "Traceback (most recent call last):",
  );
  await expect(row.locator("pre")).toContainText('"outcome": "failed"');
  await filter.fill('"process_id":4208');
  await expect(page.locator('.record[data-seq="9"]')).toHaveCount(1);
  await expect(page.locator(".record.source-host")).toHaveCount(0);
});

test("copied log lines retain the original instant and diagnostic fields", () => {
  const record = FIXTURE_RECORDS.find((item) => item.seq === 9);
  expect(record).toBeDefined();
  expect(recordLine(record!)).toBe(
    '2026-03-02T09:14:09.245Z [ERROR] cadrumo.application.example: Step failed and was not retried | {"diagnostic_id":"fixture-attempt-9","outcome":"failed","process_id":4208,"process_role":"tui"}',
  );
});
