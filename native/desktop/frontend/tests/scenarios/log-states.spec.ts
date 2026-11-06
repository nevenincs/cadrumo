import { openLogFilters } from "../support/panel";
import { expect, test } from "@playwright/test";
import { label } from "../support/strings";
import { showTui } from "../support/tui";
import { startFromDocs, open } from "../support/scenarioShell";
import { openLogs } from "../support/scenarioLogView";

// The log's loading, empty, error and missing-file states, and the levels its fixture records list.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

test("loading: nothing is invented while the host has not answered", async ({
  page: target,
}) => {
  await open(target, "loading");
  await showTui(target);
  // The pane and its header say the same thing: the check is in flight.
  const pane = target.locator(".pane-tui");
  await expect(pane.locator("[data-slot=account-loading]")).toHaveText(
    label("desktop.signin.checking"),
  );
  await expect(target.locator("#tab-tui")).toHaveAttribute(
    "aria-description",
    label("desktop.signin.checking"),
  );
  await expect(target.locator(".docs-frame")).toHaveCount(0);
  await openLogs(target);
  await expect(target.locator(".record")).toHaveCount(0);
  await expect(target.locator(".source-banner")).toHaveCount(0);
});

test("empty: an available log with no records says so", async ({
  page: target,
}) => {
  await open(target, "empty");
  await openLogs(target);
  await expect(target.locator(".logview-list")).toContainText(
    label("desktop.logs.empty"),
  );
  await expect(target.locator(".record")).toHaveCount(0);
});

test("error: refusals are shown, not swallowed", async ({ page: target }) => {
  await open(target, "error");
  // A read the host failed is said to have failed, not to need the desktop.
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.failed"),
  );
  // The failure stays visible without exposing the transport's code.
  await expect(target.locator(".sign-in")).toContainText(
    label("desktop.signin.refused.other"),
  );
  await expect(target.locator(".sign-in")).not.toContainText("timed_out");
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await openLogs(target);
  await expect(target.locator(".source-banner.state-unreadable")).toBeVisible();
});

test("a missing log file is not an empty log", async ({ page: target }) => {
  await open(target, "logs-missing");
  await openLogs(target);
  await expect(
    target.locator('.source-banner.state-missing[data-source="python"]'),
  ).toHaveText(
    `${label("desktop.logs.source_python")}: ${label("desktop.logs.state_missing_detail")}`,
  );
  await expect(
    target.locator('.source-banner[data-source="manager"]'),
  ).toHaveCount(0);
  await expect(target.locator(".logview-list")).not.toContainText(
    label("desktop.logs.empty"),
  );
});

test("fixture records list every level, an unnamed source and a dropped count", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await openLogs(target);
  await openLogFilters(target);
  await target
    .getByLabel(label("desktop.logs.minimum_level"))
    .selectOption({ label: label("desktop.logs.level_all") });
  await target.keyboard.press("Escape");
  for (const level of ["debug", "info", "warning", "error", "critical", "none"])
    await expect(
      target.locator(`.record.level-${level}`).first(),
      level,
    ).toBeVisible();
  await expect(target.locator(".record.source-manager")).toHaveCount(1);
  await expect(target.locator(".logview-list")).toContainText(
    label("desktop.logs.dropped", { count: 3 }),
  );
});
