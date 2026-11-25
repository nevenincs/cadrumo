import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The panes around a declaration's form: the To do and Outline rail at its
// start and the chosen box's details beside or under it. Each is shown and
// hidden from the form's toolbar and resized by its separator, with a pointer
// or the keyboard; the arrangement is the viewer's, kept in the window's own
// storage, and an unreadable store opens the panes at their defaults. The
// offers above the form stay as the viewer left them. At every window size
// the header's next action, the pane controls and the form stay on screen
// and the form keeps room to work.

const STORE = "cadrumo-pane-preferences";
const FORM_ROOM = 150;
const workspace = (target: Page) => target.locator(".declarations-workspace");
const toggle = (target: Page, pane: "side" | "details") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);
const separator = (target: Page, key: string) =>
  workspace(target).getByRole("separator", { name: label(key) });
const rail = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.side.label"),
  });
const details = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.details.label"),
  });
const form = (target: Page) => workspace(target).locator("[data-modelo-form]");
const views = (target: Page) =>
  workspace(target).getByRole("tablist", {
    name: label("desktop.modelo.views.label"),
  });

async function openDeclaration(target: Page, extra = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`,
  );
  await target.locator("[data-rail=declarations]").click();
  await target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]")
    .filter({ hasText: "Modelo 130" })
    .first()
    .dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
}

// Every load starts from the shell's default page, so a declaration opened
// again is opened from the list; the panes' preferences are left as they were.
test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

const width = (pane: Locator) =>
  pane.evaluate((element) => element.getBoundingClientRect().width);
const height = (pane: Locator) =>
  pane.evaluate((element) => element.getBoundingClientRect().height);
const formRoom = (target: Page) =>
  form(target).evaluate((element) => element.clientHeight);

test("UX-03 the hidden prior-values offer stays hidden after a view change and on the next opening", async ({
  page: target,
}) => {
  await openDeclaration(target);
  const offer = workspace(target).locator("section[data-prior-values]");
  const entries = offer.locator("li");
  await expect(entries.first()).toBeVisible();
  await offer
    .getByRole("button", { name: label("desktop.modelo.statements.hide") })
    .click();
  await expect(entries).toHaveCount(0);
  await views(target)
    .getByRole("tab", { name: label("workspace.modelo.step.review") })
    .click();
  await views(target)
    .getByRole("tab", { name: label("desktop.modelo.view.form") })
    .click();
  await expect(offer).toBeVisible();
  await expect(entries).toHaveCount(0);
  await openDeclaration(target);
  await expect(offer).toBeVisible();
  await expect(entries).toHaveCount(0);
  await offer
    .getByRole("button", { name: label("desktop.modelo.statements.show") })
    .click();
  await expect(entries.first()).toBeVisible();
});

for (const size of [
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
]) {
  test(`UX-04 at ${size.width} by ${size.height} the form keeps room to work, with the details shown or hidden`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    // The details start shown only where the form keeps its room beside
    // them; the offer above the form scrolls on its own to its control.
    expect(await formRoom(target)).toBeGreaterThanOrEqual(FORM_ROOM);
    const hide = workspace(target)
      .locator("section[data-prior-values]")
      .getByRole("button", { name: label("desktop.modelo.statements.hide") });
    await hide.focus();
    await expect(hide).toBeInViewport();
    await expect(workspace(target).locator("header").first()).toBeInViewport();
    await expect(toggle(target, "details")).toBeInViewport();
    if ((await details(target).count()) === 0)
      await toggle(target, "details").click();
    await expect(details(target)).toBeVisible();
    expect(await height(details(target))).toBeGreaterThanOrEqual(1);
    expect(await formRoom(target)).toBeGreaterThanOrEqual(FORM_ROOM);
  });
}

test("UX-05 the rail and the details each have a separator, and both are hidden and shown from the toolbar by keyboard", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1440, height: 1050 });
  await openDeclaration(target);
  await expect(separator(target, "desktop.modelo.side.resize")).toBeVisible();
  await expect(
    separator(target, "desktop.modelo.details.resize"),
  ).toBeVisible();
  for (const [pane, pane$] of [
    ["side", rail],
    ["details", details],
  ] as const) {
    await expect(pane$(target)).toBeVisible();
    await expect(toggle(target, pane)).toHaveAttribute("aria-pressed", "true");
    await toggle(target, pane).focus();
    await target.keyboard.press("Enter");
    await expect(pane$(target)).toHaveCount(0);
    await expect(toggle(target, pane)).toHaveAttribute("aria-pressed", "false");
  }
  await expect(toggle(target, "side")).toHaveAccessibleName(
    label("desktop.modelo.side.label"),
  );
  await expect(toggle(target, "details")).toHaveAccessibleName(
    label("desktop.modelo.details.show"),
  );
  // Hidden is the viewer's choice and comes back with the declaration.
  await openDeclaration(target);
  await expect(rail(target)).toHaveCount(0);
  await expect(details(target)).toHaveCount(0);
  await toggle(target, "side").press("Space");
  await expect(rail(target)).toBeVisible();
  await toggle(target, "details").click();
  await expect(details(target)).toBeVisible();
});

test("UX-05 the rail is resized by its separator with the keyboard and a pointer, inside its bounds, and keeps its width", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1440, height: 1050 });
  await openDeclaration(target);
  const line = separator(target, "desktop.modelo.side.resize");
  const start = await width(rail(target));
  await line.focus();
  await target.keyboard.press("ArrowRight");
  await expect.poll(() => width(rail(target))).toBeGreaterThan(start);
  await target.keyboard.press("End");
  const most = await width(rail(target));
  await expect(line).toHaveAttribute("aria-valuenow", "100");
  await target.keyboard.press("ArrowRight");
  expect(await width(rail(target))).toBe(most);
  await target.keyboard.press("Home");
  const least = await width(rail(target));
  expect(least).toBeLessThan(start);
  await expect(line).toHaveAttribute("aria-valuenow", "0");
  // A drag sets the edge where the pointer leaves it.
  const box = (await line.boundingBox())!;
  await target.mouse.move(box.x, box.y + box.height / 2);
  await target.mouse.down();
  await target.mouse.move(box.x + 60, box.y + box.height / 2, { steps: 4 });
  await target.mouse.up();
  const dragged = await width(rail(target));
  expect(dragged).toBeGreaterThan(least + 40);
  await openDeclaration(target);
  await expect.poll(() => width(rail(target))).toBeCloseTo(dragged, 0);
  // Enter returns the default.
  await separator(target, "desktop.modelo.side.resize").focus();
  await target.keyboard.press("Enter");
  await expect.poll(() => width(rail(target))).toBeCloseTo(start, 0);
});

test("UX-05 the details beside the form are resized by width and keep it", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1920, height: 1080 });
  await openDeclaration(target);
  await expect(workspace(target).locator("[data-details=side]")).toHaveCount(1);
  const line = separator(target, "desktop.modelo.details.resize");
  const start = await width(details(target));
  await line.focus();
  await target.keyboard.press("ArrowLeft");
  await expect.poll(() => width(details(target))).toBeGreaterThan(start);
  const grown = await width(details(target));
  await openDeclaration(target);
  await expect.poll(() => width(details(target))).toBeCloseTo(grown, 0);
});

test("UX-05 the details under the form are resized by height and never crowd the form out", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1024, height: 900 });
  await openDeclaration(target);
  await expect(workspace(target).locator("[data-details=bottom]")).toHaveCount(
    1,
  );
  const line = separator(target, "desktop.modelo.details.resize");
  const start = await height(details(target));
  await line.focus();
  await target.keyboard.press("ArrowUp");
  await expect.poll(() => height(details(target))).toBeGreaterThan(start);
  await target.keyboard.press("End");
  await expect(line).toHaveAttribute("aria-valuenow", "100");
  await expect(form(target)).toBeInViewport();
  expect(await formRoom(target)).toBeGreaterThanOrEqual(FORM_ROOM);
  await target.keyboard.press("Home");
  expect(await height(details(target))).toBeLessThan(start);
  expect(await formRoom(target)).toBeGreaterThanOrEqual(FORM_ROOM);
});

for (const size of [
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
]) {
  test(`UX-06 at ${size.width} by ${size.height} the To do and Outline rail stays reachable`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    const opener = toggle(target, "side");
    await expect(opener).toBeInViewport();
    await expect(opener).toHaveAccessibleName(
      new RegExp(label("desktop.modelo.side.label")),
    );
    if ((await rail(target).count()) === 0) await opener.click();
    await expect(rail(target)).toBeVisible();
    await expect(
      rail(target).getByRole("tab", {
        name: label("desktop.modelo.side.outline"),
      }),
    ).toBeVisible();
    expect(await formRoom(target)).toBeGreaterThanOrEqual(FORM_ROOM);
  });
}

test("UX-06 in a narrow pane the rail starts hidden and its control opens it", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 900, height: 600 });
  await openDeclaration(target);
  await expect(rail(target)).toHaveCount(0);
  await expect(toggle(target, "side")).toHaveAttribute("aria-pressed", "false");
  await toggle(target, "side").focus();
  await target.keyboard.press("Enter");
  await expect(rail(target)).toBeVisible();
});

for (const size of [
  { width: 1920, height: 1080 },
  { width: 1280, height: 768 },
  { width: 1024, height: 600 },
  { width: 900, height: 480 },
  { width: 720, height: 480 },
]) {
  test(`at ${size.width} by ${size.height} the header, the pane controls and the form stay on screen`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    const next = workspace(target)
      .locator("header")
      .first()
      .getByRole("button", {
        name: label("workspace.modelo.next_button.fill"),
      });
    await expect(next).toBeInViewport();
    for (const pane of ["side", "details"] as const)
      await expect(toggle(target, pane)).toBeInViewport();
    await expect(form(target)).toBeInViewport();
    expect(await formRoom(target)).toBeGreaterThan(0);
    // The form scrolls in its own region; the page itself never does.
    const page = await target.evaluate(() => ({
      scroll: document.scrollingElement?.scrollHeight ?? 0,
      view: window.innerHeight,
    }));
    expect(page.scroll).toBeLessThanOrEqual(page.view);
  });
}

test("an unreadable store opens the panes at their defaults", async ({
  page: target,
}) => {
  await target.addInitScript((store) => {
    localStorage.setItem(store, "{not json");
  }, STORE);
  await target.setViewportSize({ width: 1440, height: 1050 });
  await openDeclaration(target);
  await expect(rail(target)).toBeVisible();
  await expect(details(target)).toBeVisible();
  await toggle(target, "side").click();
  await expect(rail(target)).toHaveCount(0);
});

test("a stored size outside a pane's bounds is drawn inside them", async ({
  page: target,
}) => {
  await target.addInitScript((store) => {
    localStorage.setItem(
      store,
      JSON.stringify({
        version: 1,
        panes: {
          "modelo.workspace.side": { open: true, side: 4000, bottom: "x" },
          "modelo.workspace.details": { open: "yes", side: 3 },
        },
      }),
    );
  }, STORE);
  await target.setViewportSize({ width: 1440, height: 1050 });
  await openDeclaration(target);
  const area = await workspace(target)
    .locator("[role=tabpanel][data-details]")
    .evaluate((element) => element.clientWidth);
  expect(await width(rail(target))).toBeLessThanOrEqual(area * 0.4 + 1);
  await expect(details(target)).toBeVisible();
});
