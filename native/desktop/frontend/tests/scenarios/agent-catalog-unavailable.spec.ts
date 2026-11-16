import { expect, test } from "@playwright/test";
import { FIXTURE_CATALOG_LOG_REF } from "../../src/dev/fixtures/agentCatalog";
import { agentColumn as column, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// A catalog the service refused, such as one the agent served outside the
// schema the service pins, reaches the window as a refusal. The column says
// the provider list could not be read, with the reference of the service's
// log line where the refusal carries one, rather than showing no providers.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides how the service answers.");
});

test("a refused catalog is said with the log reference it carries", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=unavailable",
  );
  const notice = column(page)
    .getByRole("status")
    .filter({ hasText: label("desktop.agent.catalog_unavailable") });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText(
    label("desktop.providers.sign_in_log_ref"),
  );
  await expect(notice.locator("code")).toHaveText(FIXTURE_CATALOG_LOG_REF);
  await expect(
    column(page).getByText(label("desktop.agent.request_failed")),
  ).toHaveCount(0);
});

test("a refused catalog without a log reference is said in words alone", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&catalog=unavailable-unreferenced",
  );
  const notice = column(page)
    .getByRole("status")
    .filter({ hasText: label("desktop.agent.catalog_unavailable") });
  await expect(notice).toBeVisible();
  await expect(
    notice.getByText(label("desktop.providers.sign_in_log_ref")),
  ).toHaveCount(0);
  await expect(notice.locator("code")).toHaveCount(0);
});
