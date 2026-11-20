import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The Browser page while the host still holds the place of a superseded
// view, and while the account's status blips under an open view. The host's
// calls are the evidence of what the window asked for. Presentation evidence
// only: no host, runtime or Sede is behind them.

const rail = (target: Page) =>
  target.getByRole("navigation", { name: label("desktop.rail.label") });
const browserButton = (target: Page) =>
  rail(target).getByRole("button", {
    name: label("desktop.browser.title"),
    exact: true,
  });
const browserPage = (target: Page) =>
  target.getByRole("region", {
    name: label("desktop.browser.title"),
    exact: true,
  });
const status = (target: Page, key: string) =>
  browserPage(target)
    .getByRole("status")
    .filter({ hasText: label(key) });
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);
const count = async (target: Page, call: string) =>
  (await calls(target)).filter((made) => made === call).length;

async function start(target: Page) {
  await target.clock.install();
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(
    rail(target).getByRole("button", {
      name: label("desktop.rail.agent"),
      exact: true,
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
}
const show = async (target: Page) => {
  await browserButton(target).click();
};
const opens = (target: Page, control: string) =>
  target.evaluate((script) => {
    const handle = window.__scenarioSedeViewOpens;
    if (!handle) throw new Error("no open controls");
    new Function("handle", script)(handle);
  }, control);
const open = (target: Page) =>
  expect(
    target.evaluate(() => window.__scenarioSedeView !== undefined),
  ).resolves.toBe(true);

test("the browser panel says it is opening while the host has not answered", async ({
  page: target,
}) => {
  await start(target);
  await opens(target, "handle.holdOpens(true)");
  await show(target);
  await expect(status(target, "desktop.browser.opening")).toBeVisible();
});

test("the browser panel waits out a handover and then opens", async ({
  page: target,
}) => {
  await start(target);
  await opens(target, "handle.refuseOpens(3)");
  await show(target);
  await expect(status(target, "desktop.browser.waiting")).toBeVisible();
  await target.clock.runFor(750 * 4);
  await expect(status(target, "desktop.browser.waiting")).toHaveCount(0);
  await open(target);
  expect(await count(target, "sedeViewOpenRefused")).toBe(3);
  expect(await count(target, "sedeViewOpen")).toBe(1);
});

test("a handover that outlasts the host's bound fails with its cause, and Retry restarts the wait", async ({
  page: target,
}) => {
  await start(target);
  await opens(target, "handle.refuseOpens(Infinity)");
  await show(target);
  // Past the host's longest hold of the place (about 92 s) the budget lasts.
  await target.clock.runFor("01:30");
  await expect(status(target, "desktop.browser.waiting")).toBeVisible();
  await target.clock.runFor("00:40");
  const failed = status(target, "desktop.browser.failure.conflict");
  await expect(failed).toBeVisible();
  await opens(target, "handle.refuseOpens(1)");
  await failed
    .getByRole("button", { name: label("desktop.browser.retry") })
    .click();
  await expect(status(target, "desktop.browser.waiting")).toBeVisible();
  await target.clock.runFor(750 * 2);
  await expect(status(target, "desktop.browser.waiting")).toHaveCount(0);
  await open(target);
});

test("a status read that fails and returns for the same profile leaves the open view alone", async ({
  page: target,
}) => {
  await start(target);
  await show(target);
  await open(target);
  await expect(status(target, "desktop.browser.waiting")).toHaveCount(0);
  const at = (await calls(target)).length;
  await target.evaluate(() => window.__scenarioRuntime!.lose());
  await target.evaluate(() => window.__scenarioRuntime!.restore());
  await target.clock.runFor(2000);
  await expect(browserPage(target)).toBeVisible();
  const after = (await calls(target)).slice(at);
  expect(after.filter((call) => call === "sedeViewClose")).toEqual([]);
  expect(after.filter((call) => call === "sedeViewOpen")).toEqual([]);
  expect(after.filter((call) => call === "sedeViewOpenRefused")).toEqual([]);
});
