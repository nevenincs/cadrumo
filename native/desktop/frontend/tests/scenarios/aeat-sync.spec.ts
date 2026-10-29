import { expect, test, type Locator, type Page } from "@playwright/test";
import { AEAT_SYNC_AREAS } from "../../src/shell/aeatSync";
import { label } from "../support/strings";

// The AEAT data page draws what the host serves for each area: whether it
// was ever brought, how current it is and the counts beside it. An update
// from it checks what it needs, goes on in view and ends in its results.

async function open(target: Page, scenario: string) {
  await target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  return reach(target);
}

async function reach(target: Page) {
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  const input = target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") });
  await expect(input).toBeFocused();
  await input.fill("aeat-sync");
  await target.keyboard.press("Enter");
  const page = target.locator(".aeat-sync-page");
  await expect(page).toBeVisible();
  return page;
}

const area = (page: Locator, id: string) => page.locator(`[data-area="${id}"]`);
const update = (page: Locator) =>
  page.getByRole("button", {
    name: label("desktop.aeat_sync.bring_all"),
    exact: true,
  });
const done = (page: Locator) =>
  page.getByRole("button", {
    name: label("desktop.aeat_sync.progress.done_all"),
    exact: true,
  });
const progress = (page: Locator) => page.locator(".aeat-sync-progress");
const results = (page: Locator) => page.getByTestId("aeat-sync-results");
const button = (scope: Locator, key: string, values = {}) =>
  scope.getByRole("button", { name: label(key, values), exact: true });
const calls = (target: Page, prefix: string) =>
  target.evaluate(
    (start: string) =>
      (window.__scenarioHostCalls ?? []).filter((call: string) =>
        call.startsWith(start),
      ),
    prefix,
  );

test("the page names its six areas and their states from what is served", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await expect(page.locator("[data-area]")).toHaveCount(AEAT_SYNC_AREAS.length);
  const states: Record<string, string> = {
    census: "current",
    filed: "possibly_stale",
    notifications: "possibly_stale",
    vat: "never_brought",
    borrador: "unavailable",
    identity: "current",
  };
  for (const [id, state] of Object.entries(states))
    await expect(area(page, id), id).toHaveAttribute("data-state", state);
  await expect(area(page, "vat")).toContainText(
    label("desktop.aeat_sync.state.never_brought"),
  );
  await expect(area(page, "borrador")).toContainText(
    label("desktop.aeat_sync.state.unavailable"),
  );
  await expect(area(page, "notifications")).toContainText(
    label("desktop.aeat_sync.count.unread_notifications", { count: 3 }),
  );
  await expect(area(page, "filed")).toContainText(
    label("desktop.aeat_sync.count.filed_differing", { count: 1 }),
  );
});

test("a card carries its name, and only the actions that apply", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await expect(
    area(page, "census").getByRole("heading", {
      name: label("desktop.aeat_sync.area.census.name"),
    }),
  ).toBeVisible();
  // The Borrador is imported from a file, never updated from AEAT.
  const borrador = area(page, "borrador");
  await expect(
    borrador.getByRole("button", {
      name: label("desktop.aeat_sync.update_area", {
        area: label("desktop.aeat_sync.area.borrador.name"),
      }),
    }),
  ).toHaveCount(0);
  await expect(
    borrador.getByRole("button", {
      name: label("desktop.aeat_sync.results.borrador.import"),
    }),
  ).toBeEnabled();
});

test("one action brings everything and each area can be updated on its own", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  await expect
    .poll(() => calls(target, "aeatSync.start"))
    .toEqual(["aeatSync.start census,filed,notifications,vat,identity"]);
  await done(page).click();
  await button(area(page, "notifications"), "desktop.aeat_sync.update_area", {
    area: label("desktop.aeat_sync.area.notifications.name"),
  }).click();
  await expect
    .poll(() => calls(target, "aeatSync.start"))
    .toEqual([
      "aeatSync.start census,filed,notifications,vat,identity",
      "aeatSync.start notifications",
    ]);
});

test("nothing brought yet shows every area as never brought, not as empty", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-never");
  for (const id of AEAT_SYNC_AREAS)
    await expect(area(page, id), id).toHaveAttribute(
      "data-state",
      "never_brought",
    );
});

test("a status that cannot be read says so and offers another try", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-unavailable");
  await expect(page.getByTestId("aeat-sync-error")).toContainText(
    label("desktop.aeat_sync.unavailable"),
  );
  await expect(page.locator("[data-area]")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: label("desktop.aeat_sync.retry") }),
  ).toBeVisible();
});

test("an update goes from the overview to its progress and then to its results", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  // Nothing blocks, so the checks are only passed through.
  await expect(page.locator("[data-run=running]")).toBeVisible();
  await expect(results(page)).toBeVisible();
  await expect(done(page)).toBeVisible();
  // Every part came out in order, so the results speak alone.
  await expect(progress(page)).toHaveCount(0);
  await done(page).click();
  await expect(area(page, "census")).toHaveAttribute("data-state", "current");
  await expect(results(page)).toHaveCount(0);
});

test("a running update is shown again when the page is, and stops when asked", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-running");
  await update(page).click();
  await expect(page.locator("[data-run=running]")).toBeVisible();
  // Another page, then back: the update is still in view.
  await target
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(target.locator(".user-profile-page")).toBeVisible();
  await expect(target.locator(".aeat-sync-page")).toHaveCount(0);
  const again = await reach(target);
  await expect(again.locator("[data-run=running]")).toBeVisible();
  await expect(update(again)).toHaveCount(0);
  await button(again, "desktop.aeat_sync.progress.stop").click();
  await expect(again.locator("[data-run=stopped]")).toBeVisible();
  expect(await calls(target, "aeatSyncRun.stop")).toHaveLength(1);
  // What was reached is in the results, and the parts not reached say so.
  await expect(results(again)).toBeVisible();
  await expect(progress(again).locator('[data-area="vat"]')).toContainText(
    label("desktop.aeat_sync.progress.not_started"),
  );
  await done(again).click();
  await expect(update(again)).toBeEnabled();
});

test("a missing secure browser is installed in the page and the update then goes on", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=aeat-sync-browser&latency=0&bar=off",
  );
  await target
    .getByRole("dialog", { name: label("desktop.setup.title") })
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  const page = await reach(target);
  await update(page).click();
  const card = page.getByTestId("aeat-sync-browser");
  await expect(card).toContainText(
    label("desktop.aeat_sync.before.browser_title"),
  );
  expect(await calls(target, "aeatSync.start")).toHaveLength(0);
  await button(card, "desktop.aeat_sync.before.browser_install").click();
  await card
    .getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "180 MB" }),
    })
    .click();
  // The setup finishes on the scenario's cue; the update then goes by itself.
  for (let step = 0; step < 40; step += 1) {
    if ((await calls(target, "aeatSync.start")).length > 0) break;
    await target.evaluate(() => window.__scenarioSetup?.step("browser"));
    await target.waitForTimeout(50);
  }
  await expect
    .poll(() => calls(target, "aeatSync.start"))
    .toEqual(["aeatSync.start census,filed,notifications,vat,identity"]);
  await expect(results(page)).toBeVisible();
});

test("AEAT access that is not set up leads to the access editor", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-access");
  await update(page).click();
  const card = page.getByTestId("aeat-sync-access");
  await expect(card).toBeVisible();
  expect(await calls(target, "aeatSync.start")).toHaveLength(0);
  await button(card, "desktop.aeat_sync.before.access_open").click();
  await expect(
    target.getByRole("dialog", {
      name: label("desktop.profile.action.aeat_access"),
      exact: true,
    }),
  ).toBeVisible();
});

test("leaving the checks asks nothing of the host", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-access");
  await update(page).click();
  await button(
    page.getByTestId("aeat-sync-access"),
    "desktop.aeat_sync.before.not_now",
  ).click();
  await expect(area(page, "census")).toBeVisible();
  expect(await calls(target, "aeatSync.start")).toHaveLength(0);
});

test("a session that times out pauses the update until the person signs in again", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-timeout");
  await update(page).click();
  const ended = page.getByTestId("aeat-sync-ended");
  await expect(ended).toBeVisible();
  await expect(page.locator("[data-run=paused]")).toBeVisible();
  expect(await calls(target, "aeatSyncRun.resume")).toHaveLength(0);
  await button(ended, "desktop.aeat_sync.before.ended_sign_in").click();
  await expect.poll(() => calls(target, "aeatSyncRun.resume")).toHaveLength(1);
  await expect(done(page)).toBeVisible();
  await expect(ended).toHaveCount(0);
});

test("parts that failed are shown and read again only when asked", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-partial");
  await update(page).click();
  await expect(page.locator("[data-run=done]")).toContainText(
    label("desktop.aeat_sync.progress.done_problems"),
  );
  await expect(results(page)).toBeVisible();
  expect(await calls(target, "aeatSyncRun.retry")).toHaveLength(0);
  await button(progress(page), "desktop.aeat_sync.progress.try_again_for", {
    name: label("desktop.aeat_sync.area.identity.name"),
  }).click();
  await expect
    .poll(() => calls(target, "aeatSyncRun.retry"))
    .toEqual(["aeatSyncRun.retry identity 2 acknowledged=false"]);
});

test("a part whose outcome is unknown is read again only after the warning", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-unknown");
  await update(page).click();
  const name = label("desktop.aeat_sync.area.notifications.name");
  await expect(
    progress(page).locator('[data-area="notifications"]'),
  ).toHaveAttribute("data-outcome", "unknown");
  const check = button(
    progress(page),
    "desktop.aeat_sync.progress.check_again_for",
    { name },
  );
  await check.click();
  await expect(progress(page)).toContainText(
    label("desktop.aeat_sync.progress.warn_unknown"),
  );
  expect(await calls(target, "aeatSyncRun.retry")).toHaveLength(0);
  // Cancelling the warning leaves it unread.
  await button(
    progress(page),
    "desktop.aeat_sync.progress.warn_cancel",
  ).click();
  expect(await calls(target, "aeatSyncRun.retry")).toHaveLength(0);
  await check.click();
  await button(
    progress(page),
    "desktop.aeat_sync.progress.warn_confirm",
  ).click();
  await expect
    .poll(() => calls(target, "aeatSyncRun.retry"))
    .toEqual(["aeatSyncRun.retry notifications 3 acknowledged=true"]);
});

test("an update that finds nothing new says so in its results", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-quiet");
  await update(page).click();
  await expect(results(page)).toBeVisible();
  await expect(progress(page)).toHaveCount(0);
  await expect(results(page)).toContainText(
    label("desktop.aeat_sync.results.nothing_new"),
  );
  await expect(done(page)).toBeVisible();
});

test("the results lead on to the census review", async ({ page: target }) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  await expect(results(page)).toBeVisible();
  await button(
    area(page, "census"),
    "desktop.aeat_sync.results.census_review",
  ).click();
  await expect(target.locator(".user-profile-page")).toBeVisible();
});

test("the results lead on to the AEAT browser", async ({ page: target }) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  await expect(results(page)).toBeVisible();
  await button(
    area(page, "notifications"),
    "desktop.aeat_sync.results.notifications.open",
  ).click();
  await expect(
    target.getByRole("region", {
      name: label("desktop.browser.title"),
      exact: true,
    }),
  ).toBeVisible();
});

test("filed declarations show the served counts while no row is served", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-counts");
  await update(page).click();
  await expect(results(page)).toBeVisible();
  const filed = results(page).locator('[data-area="filed"]');
  for (const [match, count] of [
    ["matched", 9],
    ["aeat_only", 2],
    ["local_only", 1],
    ["differing", 1],
  ] as const)
    await expect(filed).toContainText(
      label(`desktop.aeat_sync.results.filed.group.${match}`, { count }),
    );
  await expect(filed).not.toContainText(
    label("desktop.aeat_sync.results.filed.empty"),
  );
});

test("a notification shows its date and no sender", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  const list = results(page).locator('[data-area="notifications"]');
  await expect(list).toContainText("Requerimiento de información");
  await expect(list).not.toContainText("Agencia Tributaria");
});

test("the Borrador import is for the year the person chooses", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  const borrador = results(page).locator('[data-area="borrador"]');
  const year = borrador.getByRole("combobox", {
    name: label("desktop.aeat_sync.results.borrador.year"),
  });
  const previous = new Date().getFullYear() - 1;
  await expect(year).toHaveValue(String(previous));
  await year.selectOption(String(previous - 1));
  await button(borrador, "desktop.aeat_sync.results.borrador.import").click();
  await expect
    .poll(() => calls(target, "aeatSyncResults.importBorrador"))
    .toEqual([`aeatSyncResults.importBorrador ${previous - 1}`]);
});
