import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The split between a declaration's form and the chosen box's details: the
// person arranges the details beside the form (a vertical line) or under it
// (a horizontal line) from a labelled control in the form's toolbar, and
// draws the line where they want it in either arrangement, with a pointer or
// the keyboard. Whoever never chooses gets the arrangement the window's room
// suggests. Both are the viewer's, kept in the window's own storage. However
// the window is drawn, the form keeps its least room and a box's label stays
// readable: nothing is clipped.

const SIZES = [
  { width: 1441, height: 923 },
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
];
const FORM_LEAST = 160;
const LABEL_LEAST = 120;

type Placement = "side" | "bottom";

const workspace = (target: Page) => target.locator(".declarations-workspace");
const area = (target: Page) =>
  workspace(target).locator("[role=tabpanel][data-details]");
const toggle = (target: Page, pane: "side" | "details" | "placement") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);
const details = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.details.label"),
  });
const rail = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.side.label"),
  });
const line = (target: Page) =>
  workspace(target).getByRole("separator", {
    name: label("desktop.modelo.details.resize"),
  });
const form = (target: Page) => workspace(target).locator("[data-modelo-form]");

async function openDeclaration(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
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

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

async function showPane(target: Page, pane: "side" | "details", on: boolean) {
  const control = toggle(target, pane);
  if ((await control.getAttribute("aria-pressed")) !== String(on))
    await control.click();
  await expect(control).toHaveAttribute("aria-pressed", String(on));
}

const placementOf = async (target: Page) =>
  (await area(target).getAttribute("data-details")) as Placement;

/** The details' size along the line: a width beside, a height under. */
const sizeOf = (target: Page, placement: Placement) =>
  details(target).evaluate(
    (element, across) =>
      Math.round(
        across
          ? element.getBoundingClientRect().height
          : element.getBoundingClientRect().width,
      ),
    placement === "bottom",
  );

/** Nothing in the area is clipped: the form keeps its least height, the
 * details sit inside the area, and beside them a box's label stays readable. */
async function expectFloors(target: Page, placement: Placement) {
  const room = await form(target).evaluate((element) => element.clientHeight);
  expect(room, "the form keeps its least room").toBeGreaterThanOrEqual(
    FORM_LEAST,
  );
  const geometry = await area(target).evaluate((element) => {
    const box = element.getBoundingClientRect();
    // The details are the last pane in the area, after the rail.
    const drawn = [...element.querySelectorAll("aside")]
      .at(-1)
      ?.getBoundingClientRect();
    const scroller = element.querySelector("[data-modelo-form]");
    const formBox = scroller?.getBoundingClientRect();
    const labelCell = element.querySelector(
      "[role=row] [role=gridcell]:nth-child(2)",
    );
    return {
      right: Math.round(box.right),
      bottom: Math.round(box.bottom),
      paneRight: Math.round(drawn?.right ?? 0),
      paneBottom: Math.round(drawn?.bottom ?? 0),
      paneLeft: Math.round(drawn?.left ?? 0),
      formRight: Math.round(formBox?.right ?? 0),
      label: Math.round(labelCell?.getBoundingClientRect().width ?? 0),
    };
  });
  expect(geometry.paneRight).toBeLessThanOrEqual(geometry.right);
  expect(geometry.paneBottom).toBeLessThanOrEqual(geometry.bottom);
  if (placement === "side") {
    expect(geometry.formRight).toBeLessThanOrEqual(geometry.paneLeft);
    expect(
      geometry.label,
      `a box's label is ${geometry.label}px wide beside the details`,
    ).toBeGreaterThanOrEqual(LABEL_LEAST);
  }
}

/** Moves the details' line with the keyboard and a pointer in `placement`,
 * asserting each moves it, and returns it to its default. */
async function resizeEitherWay(target: Page, placement: Placement) {
  const separator = line(target);
  await expect(separator).toHaveAttribute(
    "aria-orientation",
    placement === "side" ? "vertical" : "horizontal",
  );
  await separator.focus();
  const start = await sizeOf(target, placement);
  await target.keyboard.press("Home");
  await expect(separator).toHaveAttribute("aria-valuenow", "0");
  const least = await sizeOf(target, placement);
  await expectFloors(target, placement);
  await target.keyboard.press("End");
  await expect(separator).toHaveAttribute("aria-valuenow", "100");
  const most = await sizeOf(target, placement);
  expect(most, `the line moves from ${least}px`).toBeGreaterThan(least);
  await expectFloors(target, placement);
  await target.keyboard.press("Home");
  await target.keyboard.press(placement === "side" ? "ArrowLeft" : "ArrowUp");
  await expect.poll(() => sizeOf(target, placement)).toBeGreaterThan(least);
  await target.keyboard.press("Home");
  // A drag toward the form grows the details.
  await separator.scrollIntoViewIfNeeded();
  const box = (await separator.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await target.mouse.move(x, y);
  await target.mouse.down();
  if (placement === "side") await target.mouse.move(x - 40, y, { steps: 4 });
  else await target.mouse.move(x, y - 40, { steps: 4 });
  await target.mouse.up();
  await expect.poll(() => sizeOf(target, placement)).toBeGreaterThan(least);
  await expectFloors(target, placement);
  await separator.focus();
  await target.keyboard.press("Enter");
  await expect.poll(() => sizeOf(target, placement)).toBeCloseTo(start, 0);
}

async function choose(target: Page, placement: Placement) {
  const control = toggle(target, "placement");
  await control.focus();
  await target.keyboard.press("Enter");
  await expect(area(target)).toHaveAttribute("data-details", placement);
  await expect(control).toHaveAttribute(
    "aria-pressed",
    String(placement === "side"),
  );
}

for (const size of SIZES) {
  for (const railOn of [true, false]) {
    test(`UX-16 at ${size.width} by ${size.height} with the rail ${railOn ? "shown" : "hidden"} the details go beside or under the form and resize either way`, async ({
      page: target,
    }) => {
      await target.setViewportSize(size);
      await openDeclaration(target);
      await showPane(target, "side", railOn);
      await expect(rail(target)).toHaveCount(railOn ? 1 : 0);
      // Hidden details have nothing to arrange.
      await showPane(target, "details", false);
      await expect(toggle(target, "placement")).toHaveCount(0);
      await showPane(target, "details", true);
      const control = toggle(target, "placement");
      await expect(control).toHaveAccessibleName(
        label("desktop.modelo.details.beside"),
      );
      // The control follows the details' own in the toolbar.
      await toggle(target, "details").focus();
      await target.keyboard.press("Tab");
      await expect(control).toBeFocused();
      const first = await placementOf(target);
      await expect(control).toHaveAttribute(
        "aria-pressed",
        String(first === "side"),
      );
      await expectFloors(target, first);
      await resizeEitherWay(target, first);
      const other: Placement = first === "side" ? "bottom" : "side";
      await choose(target, other);
      await expectFloors(target, other);
      await resizeEitherWay(target, other);
      await choose(target, first);
      await expectFloors(target, first);
    });
  }

  test(`UX-16 at ${size.width} by ${size.height} the chosen arrangement and its size come back, and choosing the window's own hands it back`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    await showPane(target, "details", true);
    const first = await placementOf(target);
    const other: Placement = first === "side" ? "bottom" : "side";
    await choose(target, other);
    await line(target).focus();
    await target.keyboard.press("Home");
    await target.keyboard.press(other === "side" ? "ArrowLeft" : "ArrowUp");
    const drawn = await sizeOf(target, other);
    await openDeclaration(target);
    await expect(area(target)).toHaveAttribute("data-details", other);
    await expect(toggle(target, "placement")).toHaveAttribute(
      "aria-pressed",
      String(other === "side"),
    );
    await expect.poll(() => sizeOf(target, other)).toBeCloseTo(drawn, 0);
    await toggle(target, "placement").press("Space");
    await expect(area(target)).toHaveAttribute("data-details", first);
    await openDeclaration(target);
    await expect(area(target)).toHaveAttribute("data-details", first);
    const kept = await target.evaluate(() =>
      localStorage.getItem("cadrumo-pane-preferences"),
    );
    expect(kept ?? "").not.toMatch(/"placement":"(side|bottom)"/);
  });
}

// A wide window offers the details beside the form until the person
// chooses; stacked is then kept even there.
test("UX-16 on a wide window the details start beside the form and can be stacked", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1920, height: 1080 });
  await openDeclaration(target);
  await expect(area(target)).toHaveAttribute("data-details", "side");
  await choose(target, "bottom");
  await resizeEitherWay(target, "bottom");
});
