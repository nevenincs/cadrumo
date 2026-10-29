import { expect, test, type Page } from "@playwright/test";
import { AEAT_SYNC_AREAS } from "../../src/shell/aeatSync";
import { label } from "../support/strings";

// The AEAT data overview draws what the host serves for each area: whether
// it was ever brought, how current it is and the counts beside it.

async function open(target: Page, scenario: string) {
  await target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
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

const area = (page: ReturnType<Page["locator"]>, id: string) =>
  page.locator(`[data-area="${id}"]`);

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

test("one action brings everything and each area can be updated on its own", async ({
  page: target,
}) => {
  const page = await open(target, "aeat-sync");
  await page
    .getByRole("button", { name: label("desktop.aeat_sync.bring_all") })
    .click();
  await expect
    .poll(() =>
      target.evaluate(() =>
        (window.__scenarioHostCalls ?? []).filter((call: string) =>
          call.startsWith("aeatSync.start"),
        ),
      ),
    )
    .toEqual(["aeatSync.start census,filed,notifications,vat,identity"]);
  await area(page, "notifications")
    .getByRole("button", {
      name: label("desktop.aeat_sync.update_area", {
        area: label("desktop.aeat_sync.area.notifications.name"),
      }),
    })
    .click();
  await expect
    .poll(() =>
      target.evaluate(
        () => (window.__scenarioHostCalls ?? []).slice(-1)[0] ?? "",
      ),
    )
    .toBe("aeatSync.start notifications");
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
