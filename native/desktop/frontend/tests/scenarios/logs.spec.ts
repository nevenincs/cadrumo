import { openPanelTab } from "../support/panel";
import { expect, test } from "@playwright/test";
import { FIXTURE_RECORDS, generatedBatches } from "../../src/dev/fixtures/logs";
import { recordLine, recordsText } from "../../src/shell/records";
import { readFile } from "node:fs/promises";
import { label } from "../support/strings";

test.use({ timezoneId: "Europe/Madrid" });

test("reveal log location is available from the log bar and command palette", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0");
  await openPanelTab(page, "logs");
  await page
    .getByRole("button", { name: label("desktop.logs.reveal"), exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.__scenarioHostCalls?.filter((call) => call === "revealLogs")
            .length,
      ),
    )
    .toBe(1);
  await page.keyboard.press("Control+Shift+k");
  await page
    .locator(".palette")
    .getByRole("combobox")
    .fill(label("desktop.logs.reveal"));
  await page
    .getByRole("option", { name: label("desktop.logs.reveal") })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.__scenarioHostCalls?.filter((call) => call === "revealLogs")
            .length,
      ),
    )
    .toBe(2);
});

for (const kind of ["missing", "unreadable", "rejected"] as const) {
  test(`manager ${kind} state preserves Python records and names its own source`, async ({
    page,
  }) => {
    await page.goto(`/scenarios.html?scenario=manager-log-${kind}&latency=0`);
    await openPanelTab(page, "logs");
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
  await openPanelTab(page, "logs");
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
  await openPanelTab(page, "logs");
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

test("origin filter and exports distinguish all retained entries from visible entries", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0");
  await openPanelTab(page, "logs");
  await page
    .getByLabel(label("desktop.logs.origin"))
    .selectOption("python / tui:4208");
  await expect(page.locator(".record.source-host")).toHaveCount(0);
  await page.getByLabel(label("desktop.logs.filter")).fill("fixture-attempt-9");
  await expect(page.locator(".record")).toHaveCount(1);
  for (const [key, expected] of [
    [
      "desktop.logs.export_visible",
      recordsText(FIXTURE_RECORDS.filter((record) => record.seq === 9)),
    ],
    ["desktop.logs.export_all", recordsText(FIXTURE_RECORDS)],
  ]) {
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: label(key!), exact: true }).click();
    const download = await downloadPromise;
    expect(await readFile((await download.path())!, "utf8")).toBe(expected);
  }
});

for (const modifier of ["Control", "Meta"]) {
  test(`${modifier}+A selects and copies filtered entries beyond the rendered window`, async ({
    page,
  }) => {
    await page.goto(
      "/scenarios.html?scenario=signed-in&latency=0&records=1600",
    );
    await openPanelTab(page, "logs");
    await page
      .getByLabel(label("desktop.logs.minimum_level"))
      .selectOption("0");
    await expect(page.locator(".record")).toHaveCount(400);
    await page
      .getByRole("button", {
        name: label("desktop.menu.select_all"),
        exact: true,
      })
      .click();
    await page.keyboard.press("Escape");
    await page.keyboard.press(`${modifier}+a`);
    await expect(
      page.getByText(label("desktop.logs.selected", { count: 1600 })),
    ).toBeVisible();
    await page.keyboard.press(`${modifier}+c`);
    await expect(
      page.getByText(label("desktop.toast.copied"), { exact: true }),
    ).toBeVisible();
    const expected = recordsText(
      generatedBatches(1600).flatMap((batch) => batch.records),
    );
    expect(
      (await page.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
        (call) => call.startsWith("writeClipboard"),
      ),
    ).toEqual([`writeClipboard ${expected.length} characters`]);
    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", {
        name: label("desktop.logs.export_visible"),
        exact: true,
      })
      .click();
    const text = await readFile(
      (await (await downloadPromise).path())!,
      "utf8",
    );
    expect(text).toContain("Generated record 1 for");
    expect(text).toContain("Generated record 1600 for");
    expect(text).toContain("Traceback");
    await page
      .getByLabel(label("desktop.logs.filter"))
      .fill("nonexistent-record");
    await expect(
      page.getByText(label("desktop.logs.selected", { count: 1600 })),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", {
        name: label("desktop.menu.copy_visible"),
        exact: true,
      }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", {
        name: label("desktop.logs.copy_all"),
        exact: true,
      }),
    ).toBeEnabled();
  });
}
