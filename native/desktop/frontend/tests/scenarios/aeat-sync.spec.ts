import { expect, test, type Locator, type Page } from "@playwright/test";
import { DEMO_BORRADOR_YEARS } from "../../src/dev/aeatSyncFixture";
import { AEAT_SYNC_AREAS } from "../../src/shell/aeatSync";
import { seedLayout } from "../support/layout";
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

// A host call follows the click that causes it by a few turns of the event
// loop, so "never called" is held across a short window instead of read once.
async function expectNoCalls(target: Page, prefix: string) {
  const seen = await target.evaluate(
    (start: string) =>
      new Promise<string[]>((resolve) => {
        const found = () =>
          (window.__scenarioHostCalls ?? []).filter((call: string) =>
            call.startsWith(start),
          );
        const until = Date.now() + 300;
        const look = () => {
          if (found().length > 0 || Date.now() >= until) resolve(found());
          else setTimeout(look, 25);
        };
        look();
      }),
    prefix,
  );
  expect(seen).toEqual([]);
}

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
  await expectNoCalls(target, "aeatSync.start");
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
  await expectNoCalls(target, "aeatSync.start");
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
  await expectNoCalls(target, "aeatSync.start");
});

test("signed out, the page says so and offers no update; signing in shows the overview", async ({
  page: target,
}) => {
  await seedLayout(target, { layout: { page: "aeat-sync" } });
  await target.goto("/scenarios.html?scenario=signed-out&latency=0&bar=off");
  const page = target.locator(".aeat-sync-page");
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.aeat_sync.signed_out"),
  );
  await expect(page).toHaveCount(0);
  await expect(update(target.locator("body"))).toHaveCount(0);
  await target.locator("#profile-password").fill("anything");
  await target
    .locator(".sign-in")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(page).toBeVisible();
  await expect(page.locator("[data-area]")).toHaveCount(AEAT_SYNC_AREAS.length);
  await expect(update(page)).toBeEnabled();
  await expectNoCalls(target, "aeatSync.start");
});

test("waiting for the phone shows the approval and carries the update on once approved", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-phone");
  await update(page).click();
  const phone = page.getByTestId("aeat-sync-phone");
  await expect(phone).toContainText(
    label("desktop.aeat_sync.before.phone_title"),
  );
  await expect(phone).toContainText(
    label("desktop.aeat_sync.before.phone_body"),
  );
  await expect(button(phone, "desktop.aeat_sync.before.cancel")).toBeVisible();
  await expectNoCalls(target, "aeatSync.start");
  await target.evaluate(() => window.__scenarioAeatPhone?.approve());
  await expect
    .poll(() => calls(target, "aeatSync.start"))
    .toEqual(["aeatSync.start census,filed,notifications,vat,identity"]);
  await expect(phone).toHaveCount(0);
  await expect(results(page)).toBeVisible();
});

test("cancelling the wait for the phone returns to the overview and starts nothing", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-phone");
  await update(page).click();
  const phone = page.getByTestId("aeat-sync-phone");
  await button(phone, "desktop.aeat_sync.before.cancel").click();
  await expect(phone).toHaveCount(0);
  await expect(update(page)).toBeEnabled();
  await expect(page.locator("[data-area]")).toHaveCount(AEAT_SYNC_AREAS.length);
  await expectNoCalls(target, "aeatSync.start");
  await expectNoCalls(target, "aeatSyncRun");
});

test("a browser that cannot be downloaded says why, offers another try and a way back, and starts nothing", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=aeat-sync-browser-blocked&latency=0&bar=off",
  );
  await target
    .getByRole("dialog", { name: label("desktop.setup.title") })
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  const page = await reach(target);
  await update(page).click();
  const card = page.getByTestId("aeat-sync-browser");
  await button(card, "desktop.aeat_sync.before.browser_install").click();
  await expect(card.getByRole("alert")).toHaveText(
    label("desktop.setup.failure.host_unreachable"),
  );
  await expect(
    card.getByRole("button", {
      name: label("desktop.setup.action.set_up"),
      exact: true,
    }),
  ).toBeEnabled();
  await expectNoCalls(target, "aeatSync.start");
  await button(card, "desktop.aeat_sync.before.not_now").click();
  await expect(card).toHaveCount(0);
  await expect(update(page)).toBeEnabled();
  await expectNoCalls(target, "aeatSync.start");
});

test("a session that times out pauses the update until the person signs in again", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-timeout");
  await update(page).click();
  const ended = page.getByTestId("aeat-sync-ended");
  await expect(ended).toBeVisible();
  await expect(page.locator("[data-run=paused]")).toBeVisible();
  await expectNoCalls(target, "aeatSyncRun.resume");
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
  await expectNoCalls(target, "aeatSyncRun.retry");
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
  await expectNoCalls(target, "aeatSyncRun.retry");
  // Cancelling the warning leaves it unread.
  await button(
    progress(page),
    "desktop.aeat_sync.progress.warn_cancel",
  ).click();
  await expectNoCalls(target, "aeatSyncRun.retry");
  await check.click();
  await button(
    progress(page),
    "desktop.aeat_sync.progress.warn_confirm",
  ).click();
  await expect
    .poll(() => calls(target, "aeatSyncRun.retry"))
    .toEqual(["aeatSyncRun.retry notifications 3 acknowledged=true"]);
});

test("in the results, an area whose outcome is unknown is read again only after the warning", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-unknown");
  await update(page).click();
  const census = results(page).locator('[data-area="census"]');
  await expect(census).toHaveAttribute("data-outcome", "unknown");
  await button(census, "desktop.aeat_sync.results.retry").click();
  await expect(census).toContainText(
    label("desktop.aeat_sync.progress.warn_unknown"),
  );
  await expectNoCalls(target, "aeatSyncResults.retry");
  // Cancelling the warning leaves it unread.
  await button(census, "desktop.aeat_sync.progress.warn_cancel").click();
  await expectNoCalls(target, "aeatSyncResults.retry");
  await button(census, "desktop.aeat_sync.results.retry").click();
  await button(census, "desktop.aeat_sync.progress.warn_confirm").click();
  await expect
    .poll(() => calls(target, "aeatSyncResults.retry"))
    .toEqual(["aeatSyncResults.retry census all acknowledged=true"]);
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

test("the census review takes over the pull that is going on and starts no second", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync-census-running");
  // The run's census item began the pull at the host; this window did not.
  await target.evaluate(() => window.__scenarioCenso!.begin());
  await update(page).click();
  await expect(results(page)).toBeVisible();
  await button(
    area(page, "census"),
    "desktop.aeat_sync.results.census_review",
  ).click();
  const band = target.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });
  await expect(target.locator(".user-profile-page")).toBeVisible();
  await expect(
    band.getByText(label("desktop.profile.censo.reading")),
  ).toBeVisible();
  expect(await target.evaluate(() => window.__scenarioCenso!.pulls())).toBe(1);
  await target.evaluate(() => window.__scenarioCenso!.reachReview());
  await expect(
    band.getByRole("button", {
      name: label("desktop.profile.censo.review_count", { count: 3 }),
    }),
  ).toBeVisible();
  expect(await target.evaluate(() => window.__scenarioCenso!.pulls())).toBe(1);
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

test("filed declarations are grouped with their record, what AEAT showed and the receipt apart", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await update(page).click();
  await expect(results(page)).toBeVisible();
  const filed = results(page).locator('[data-area="filed"]');
  for (const [match, count] of [
    ["aeat_only", 3],
    ["differing", 1],
    ["local_only", 1],
    ["matched", 2],
  ] as const) {
    await expect(filed.locator(`[data-group="${match}"]`)).toContainText(
      label(`desktop.aeat_sync.results.filed.group.${match}`, { count }),
    );
    await expect(filed.locator(`[data-match="${match}"]`)).toHaveCount(count);
  }
  await expect(filed.locator('[data-match="differing"]')).toContainText(
    label("desktop.aeat_sync.results.filed.differs.status"),
  );
  await expect(filed.locator('[data-match="local_only"]')).toContainText(
    label("desktop.aeat_sync.results.filed.aeat.none"),
  );
  await expect(filed).toContainText(
    label("desktop.aeat_sync.results.filed.receipt.confirmed"),
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
  const [latest, chosen] = DEMO_BORRADOR_YEARS;
  await expect(year.locator("option")).toHaveText(
    DEMO_BORRADOR_YEARS.map(String),
  );
  await expect(year).toHaveValue(String(latest));
  await year.selectOption(String(chosen));
  await button(borrador, "desktop.aeat_sync.results.borrador.import").click();
  await expect
    .poll(() => calls(target, "aeatSyncResults.importBorrador"))
    .toEqual([`aeatSyncResults.importBorrador ${chosen}`]);
});

// Each area is served as up to date or possibly out of date by the backend,
// by its own horizon; the page words and marks what it is served.
const HORIZONS = [
  ["notifications", 7],
  ["vat", 30],
  ["census", 90],
  ["filed", 90],
  ["identity", 90],
] as const;
const DAY = 24 * 60 * 60 * 1000;
const NOON = new Date("2026-10-29T12:00:00Z");

const dayOf = (days: number) =>
  new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(
    new Date(NOON.getTime() - days * DAY),
  );

for (const [scenario, days, state, key, icon] of [
  [
    "aeat-sync-inside-horizon",
    -1,
    "current",
    "desktop.aeat_sync.state.current",
    "check",
  ],
  [
    "aeat-sync-past-horizon",
    1,
    "possibly_stale",
    "desktop.aeat_sync.state.possibly_stale",
    "alert",
  ],
] as const)
  test(`${scenario}: each area is ${state === "current" ? "up to date" : "possibly out of date"} a day ${days < 0 ? "inside" : "past"} its horizon`, async ({
    page: target,
  }) => {
    await target.clock.setFixedTime(NOON);
    const page = await open(target, scenario);
    for (const [id, horizon] of HORIZONS) {
      const card = area(page, id);
      await expect(card, id).toHaveAttribute("data-state", state);
      await expect(card, id).toContainText(
        label(key, { date: dayOf(horizon + days) }),
      );
      await expect(card.locator("[data-icon]").first(), id).toHaveAttribute(
        "data-icon",
        icon,
      );
    }
  });
