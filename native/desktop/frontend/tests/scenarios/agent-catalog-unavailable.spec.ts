import { expect, test, type Page } from "@playwright/test";
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

declare global {
  interface Window {
    /** The refusal the made-up catalogue read answers, while one is set. */
    __catalogRefusal?: string | null;
  }
}

/** Opens the column with the catalogue read answering `code` while the
 * agent is ready, until the spec clears it. */
async function openRefusing(page: Page, code: string) {
  await page.addInitScript((code) => {
    window.__catalogRefusal = code;
    window.__fixtureProviderCatalogRead = async () => {
      const refusal = window.__catalogRefusal;
      if (refusal) throw Object.assign(new Error(refusal), { code: refusal });
    };
  }, code);
  await page.clock.install();
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
}

const catalogReads = (page: Page) =>
  page.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentProviderCatalog",
      ).length,
  );

/** Two minutes on the page's clock: whatever the column had scheduled has
 * run. */
async function pass(page: Page) {
  for (let step = 0; step < 12; step++) {
    await page.clock.fastForward("00:10");
    await page.waitForTimeout(20);
  }
}

// A catalogue read that answers where the person's setup stands, while the
// agent itself is ready, is said as that state over the composer, never left
// blank. A state that moves on by itself offers no control and is read again
// when the person comes back to the window; nothing asks on a timer.
for (const [code, words] of [
  ["agent_signed_out", "desktop.agent.service_signed_out"],
  ["agent_service_not_ready", "desktop.agent.service_starting"],
  ["agent_reconnecting", "desktop.account.reconnecting"],
] as const)
  test(`a catalogue read answering ${code} says so, waits without a timer and is read again when the person comes back`, async ({
    page,
  }) => {
    await openRefusing(page, code);
    const notice = column(page)
      .getByRole("status")
      .filter({ hasText: label(words) });
    await expect(notice).toBeVisible();
    await expect(
      notice.getByRole("button", { name: label("desktop.agent.retry") }),
    ).toHaveCount(0);
    const asked = await catalogReads(page);
    await pass(page);
    expect(await catalogReads(page)).toBe(asked);
    await page.evaluate(() => {
      window.__catalogRefusal = null;
      window.dispatchEvent(new Event("focus"));
    });
    await expect.poll(() => catalogReads(page)).toBe(asked + 1);
    await expect(notice).toHaveCount(0);
  });

test("a catalogue not there yet says so with asking again, which reads it at once", async ({
  page,
}) => {
  await openRefusing(page, "agent_catalog_unavailable");
  const notice = column(page)
    .getByRole("status")
    .filter({ hasText: label("desktop.agent.catalog_unavailable") });
  await expect(notice).toBeVisible();
  const asked = await catalogReads(page);
  await pass(page);
  expect(await catalogReads(page)).toBe(asked);
  await page.evaluate(() => {
    window.__catalogRefusal = null;
  });
  await notice
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect.poll(() => catalogReads(page)).toBe(asked + 1);
  await expect(notice).toHaveCount(0);
});

test("a catalogue read that faults keeps its error notice with asking again", async ({
  page,
}) => {
  await openRefusing(page, "agent_gateway_503");
  const notice = column(page)
    .getByRole("alert")
    .filter({ hasText: label("desktop.agent.request_failed") });
  await expect(notice).toBeVisible();
  // A fault is not a state that moves on by itself: coming back asks nothing.
  const asked = await catalogReads(page);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await pass(page);
  expect(await catalogReads(page)).toBe(asked);
  await page.evaluate(() => {
    window.__catalogRefusal = null;
  });
  await notice
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect.poll(() => catalogReads(page)).toBe(asked + 1);
  await expect(notice).toHaveCount(0);
});
