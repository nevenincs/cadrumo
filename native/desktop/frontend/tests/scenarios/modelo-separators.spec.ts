import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Every separator the Form view of a declaration draws, in every combination
// of the rail shown or hidden and the details hidden, beside the form or
// under it, at the window sizes the app is used at. A separator sits between
// two panels that both have room, is the only line there (no other separator
// or panel border within a few pixels), lies inside the window, and is never
// inert: where it has range a pointer and the arrow keys move it, and where
// the layout leaves it too little to be worth offering it is not drawn as
// a usable control. The other views draw none of the form's.

const SIZES = [
  { width: 1441, height: 923 },
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
];
// A separator whose whole travel is less than one keyboard step is not
// worth offering.
const LEAST_TRAVEL = 24;
const DOUBLED = 8;
const DRAG = 40;

type Placement = "side" | "bottom";
type Arrangement = { rail: boolean; details: false | Placement };
const ARRANGEMENTS: Arrangement[] = [];
for (const rail of [true, false])
  for (const details of [false, "side", "bottom"] as const)
    ARRANGEMENTS.push({ rail, details });

const workspace = (target: Page) => target.locator(".declarations-workspace");
const area = (target: Page) =>
  workspace(target).locator("[role=tabpanel][data-details]");
const toggle = (target: Page, pane: "side" | "details" | "placement") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);
const lines = (target: Page) =>
  workspace(target).locator("[data-slot=resize-handle]");
const views = (target: Page) =>
  workspace(target).getByRole("tablist", {
    name: label("desktop.modelo.views.label"),
  });

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
  await target.addInitScript(() => {
    localStorage.removeItem("cadrumo-shell-layout");
  });
});

async function showPane(target: Page, pane: "side" | "details", on: boolean) {
  const control = toggle(target, pane);
  if ((await control.getAttribute("aria-pressed")) !== String(on))
    await control.click();
  await expect(control).toHaveAttribute("aria-pressed", String(on));
}

/** Puts the form view into `arrangement` through the toolbar's controls. */
async function arrange(target: Page, arrangement: Arrangement) {
  await showPane(target, "side", arrangement.rail);
  await showPane(target, "details", arrangement.details !== false);
  if (arrangement.details === false) {
    await expect(area(target)).toHaveAttribute("data-details", "closed");
    return;
  }
  if ((await area(target).getAttribute("data-details")) !== arrangement.details)
    await toggle(target, "placement").click();
  await expect(area(target)).toHaveAttribute(
    "data-details",
    arrangement.details,
  );
}

type Panels = { name: string; width: number; height: number };
type Line = {
  index: number;
  name: string;
  orientation: string;
  disabled: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  /** The panel before and after the line, as drawn. */
  before: Panels;
  after: Panels;
  /** The distance to the nearest other separator or panel border parallel
   * to this line, and the pane's size along the line's travel. */
  nearest: number;
  doubledBy: string;
  /** Whether at least 24px of the line (or all of it) is in the window as
   * the area is first drawn. */
  visible: boolean;
};

/** Measures every separator in the form view: where it is, what it sits
 * between, and what else draws a line next to it. */
function measure(target: Page): Promise<Line[]> {
  return target.evaluate(() => {
    const root = document.querySelector(".declarations-workspace")!;
    const handles = [
      ...root.querySelectorAll<HTMLElement>("[data-slot=resize-handle]"),
    ];
    const everySeparator = [
      ...document.querySelectorAll<HTMLElement>('[role="separator"]'),
    ];
    const describe = (element: Element | null): Panels => {
      const box = element?.getBoundingClientRect();
      return {
        name:
          element?.getAttribute("aria-label") ??
          (element?.hasAttribute("data-modelo-form") ||
          element?.querySelector("[data-modelo-form]")
            ? "form"
            : "?"),
        width: Math.round(box?.width ?? 0),
        height: Math.round(box?.height ?? 0),
      };
    };
    return handles.map((handle, index) => {
      const box = handle.getBoundingClientRect();
      const vertical = handle.getAttribute("aria-orientation") === "vertical";
      const pane = handle.parentElement!;
      const aside = pane.querySelector("aside");
      const column =
        root.querySelector<HTMLElement>("[data-modelo-form]")!.parentElement!;
      // The form is the panel the pane is drawn against.
      const pairs = describe(aside);
      const formPanel = describe(
        column.querySelector("[data-modelo-form]")!.closest("div.flex-col") ??
          column,
      );
      const edge = pane.getAttribute("data-pane-edge");
      const [before, after] =
        edge === "start" ? [pairs, formPanel] : [formPanel, pairs];
      let nearest = Infinity;
      let doubledBy = "";
      const along = (a: number, b: number, c: number, d: number) =>
        Math.min(b, d) - Math.max(a, c);
      const consider = (position: number, name: string, overlap: number) => {
        if (overlap < (vertical ? box.height : box.width) / 2) return;
        const gap = Math.abs(position - (vertical ? box.x : box.y));
        if (gap < nearest) {
          nearest = gap;
          doubledBy = name;
        }
      };
      for (const other of everySeparator) {
        if (other === handle) continue;
        const o = other.getBoundingClientRect();
        if (
          vertical !==
          (other.getAttribute("aria-orientation") === "vertical")
        )
          continue;
        consider(
          vertical ? o.x : o.y,
          `separator ${other.getAttribute("aria-label") ?? other.className}`,
          vertical
            ? along(box.y, box.bottom, o.y, o.bottom)
            : along(box.x, box.right, o.x, o.right),
        );
      }
      // A panel's own border along the same axis; what a panel draws inside
      // itself is its content, not a second line between panels.
      const area = handle.closest("[role=tabpanel]")!;
      for (const element of root.querySelectorAll<HTMLElement>("*")) {
        if (element === handle || handle.contains(element)) continue;
        if (element.parentElement !== area && element.tagName !== "ASIDE")
          continue;
        const style = getComputedStyle(element);
        const o = element.getBoundingClientRect();
        const long = vertical ? o.height : o.width;
        if (long < 100 || o.width === 0 || o.height === 0) continue;
        const edges: [number, number][] = vertical
          ? [
              [parseFloat(style.borderLeftWidth), o.left],
              [parseFloat(style.borderRightWidth), o.right],
            ]
          : [
              [parseFloat(style.borderTopWidth), o.top],
              [parseFloat(style.borderBottomWidth), o.bottom],
            ];
        for (const [width, position] of edges) {
          if (!(width > 0)) continue;
          consider(
            position,
            `border of ${element.tagName.toLowerCase()}.${String(element.className).slice(0, 40)}`,
            vertical
              ? along(box.y, box.bottom, o.y, o.bottom)
              : along(box.x, box.right, o.x, o.right),
          );
        }
      }
      return {
        index,
        name: handle.getAttribute("aria-label") ?? "",
        orientation: handle.getAttribute("aria-orientation") ?? "",
        disabled: handle.getAttribute("aria-disabled"),
        x: Math.round(box.x * 10) / 10,
        y: Math.round(box.y * 10) / 10,
        width: box.width,
        height: box.height,
        before,
        after,
        nearest: Math.round(nearest * 10) / 10,
        doubledBy,
        visible:
          Math.min(box.bottom, window.innerHeight) - Math.max(box.top, 0) >=
            Math.min(box.height, 24) &&
          Math.min(box.right, window.innerWidth) - Math.max(box.left, 0) >=
            Math.min(box.width, 24),
      };
    });
  });
}

/** The size of the pane a line controls, along its travel. */
const paneSize = (target: Page, name: string) =>
  workspace(target)
    .getByRole("separator", { name })
    .evaluate((handle) => {
      const aside = handle.parentElement!.querySelector("aside")!;
      const box = aside.getBoundingClientRect();
      return Math.round(
        handle.getAttribute("aria-orientation") === "vertical"
          ? box.width
          : box.height,
      );
    });

type Travel = {
  least: number;
  most: number;
  keyboard: boolean;
  pointer: boolean;
};

/** Moves the line to its least and most by keyboard, then tries a pointer
 * and an arrow key from the least; leaves the pane at its default. */
async function travel(target: Page, line: Line): Promise<Travel> {
  const handle = workspace(target).getByRole("separator", { name: line.name });
  await handle.scrollIntoViewIfNeeded();
  await handle.focus();
  await target.keyboard.press("Home");
  const least = await paneSize(target, line.name);
  await target.keyboard.press("End");
  const most = await paneSize(target, line.name);
  await target.keyboard.press("Home");
  // The key that grows the pane: toward the form for a pane drawn against
  // the end, away from it for the rail.
  const rail = line.name === label("desktop.modelo.side.resize");
  const grow =
    line.orientation === "vertical"
      ? rail
        ? "ArrowRight"
        : "ArrowLeft"
      : "ArrowUp";
  await target.keyboard.press(grow);
  const keyed = await paneSize(target, line.name);
  await target.keyboard.press("Home");
  // A short window scrolls the workspace as a whole, and the line moves with
  // the pane's size: bring it into the window before taking hold of it.
  await handle.scrollIntoViewIfNeeded();
  const box = (await handle.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await target.mouse.move(x, y);
  await target.mouse.down();
  if (line.orientation === "vertical")
    await target.mouse.move(rail ? x + DRAG : x - DRAG, y, { steps: 4 });
  else await target.mouse.move(x, y - DRAG, { steps: 4 });
  await target.mouse.up();
  const dragged = await paneSize(target, line.name);
  await handle.focus();
  await target.keyboard.press("Enter");
  return {
    least,
    most,
    keyboard: keyed > least,
    pointer: dragged > least,
  };
}

const soft = expect.configure({ soft: true });

for (const size of SIZES) {
  for (const arrangement of ARRANGEMENTS) {
    const name = `${size.width} by ${size.height}, rail ${arrangement.rail ? "shown" : "hidden"}, details ${arrangement.details === false ? "hidden" : arrangement.details === "side" ? "beside" : "under"}`;
    test(`separators: ${name}`, async ({ page: target }) => {
      await target.setViewportSize(size);
      await openDeclaration(target);
      await arrange(target, arrangement);
      const drawn = await measure(target);

      // One separator for each pane that is drawn, and none for a hidden one.
      expect(
        drawn.map((line) => line.name).sort(),
        "the separators drawn",
      ).toEqual(
        [
          ...(arrangement.rail ? [label("desktop.modelo.side.resize")] : []),
          ...(arrangement.details !== false
            ? [label("desktop.modelo.details.resize")]
            : []),
        ].sort(),
      );

      for (const line of drawn) {
        const where = `${name}: ${line.name}`;
        // Between two panels that both have room.
        for (const panel of [line.before, line.after])
          soft(
            panel.width > 0 && panel.height > 0,
            `${where}: the ${panel.name} panel is ${panel.width} by ${panel.height}`,
          ).toBe(true);
        // Not doubled by another separator or a panel's border.
        soft(
          line.nearest,
          `${where}: doubled by ${line.doubledBy}`,
        ).toBeGreaterThan(DOUBLED);
        // Inside the window, once the workspace scrolls to it.
        const handle = workspace(target).getByRole("separator", {
          name: line.name,
        });
        await handle.scrollIntoViewIfNeeded();
        const at = (await handle.boundingBox())!;
        soft(at.x, `${where}: left`).toBeGreaterThanOrEqual(0);
        soft(at.y, `${where}: top`).toBeGreaterThanOrEqual(0);
        soft(at.x + at.width, `${where}: right`).toBeLessThanOrEqual(
          size.width,
        );
        soft(at.y + at.height, `${where}: bottom`).toBeLessThanOrEqual(
          size.height,
        );
        // A pointer lands on it: nothing else covers its middle.
        const covered = await handle.evaluate((element) => {
          const box = element.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.x + box.width / 2,
            box.y + box.height / 2,
          );
          return hit === element || element.contains(hit);
        });
        soft(covered, `${where}: covered by another element`).toBe(true);
        // Never inert: it moves where it has range, and where it has too
        // little it is not offered as a usable control.
        const moved = await travel(target, line);
        const range = moved.most - moved.least;
        if (range >= LEAST_TRAVEL) {
          soft(moved.keyboard, `${where}: arrow key moves it`).toBe(true);
          soft(moved.pointer, `${where}: drag moves it`).toBe(true);
        } else {
          soft(
            line.disabled,
            `${where}: has ${range}px of travel and is neither absent nor aria-disabled`,
          ).toBe("true");
        }
      }
    });
  }

  test(`separators: ${size.width} by ${size.height}, the other views draw none of the form's`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    await arrange(target, { rail: true, details: "bottom" });
    expect(await lines(target).count()).toBeGreaterThan(0);
    for (const key of [
      "workspace.modelo.step.review",
      "workspace.modelo.filing.title",
    ]) {
      await views(target)
        .getByRole("tab", { name: label(key) })
        .click();
      await expect(area(target)).toHaveCount(0);
      await expect(lines(target), key).toHaveCount(0);
      await expect(workspace(target).getByRole("separator"), key).toHaveCount(
        0,
      );
    }
  });
}
